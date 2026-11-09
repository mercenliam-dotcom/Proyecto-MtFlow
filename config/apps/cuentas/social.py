"""OAuth/OIDC mediante Authlib; sin unión de cuentas basada en el correo."""
import re
import time
import hashlib
import hmac
from collections.abc import Mapping
from urllib.parse import urlsplit

from authlib.integrations.django_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from joserfc.errors import JoseError
from requests.exceptions import RequestException
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from web.limites import _admitir
from .forms_cliente import RegistroClienteForm
from .models import IdentidadSocial, Usuario

NOMBRES = {"google": "Google", "facebook": "Facebook"}
TTL = 600


def disponibles():
    try:
        base = urlsplit(settings.SOCIAL_AUTH_BASE_URL)
    except ValueError:
        return []
    seguro = base.scheme == "https" or (settings.DEBUG and base.scheme == "http" and base.hostname in ("localhost", "127.0.0.1"))
    if not seguro or not base.netloc or base.username or base.password or base.path or base.query or base.fragment:
        return []
    resultado = []
    for p in NOMBRES:
        if getattr(settings, p.upper()+"_CLIENT_ID") and getattr(settings, p.upper()+"_CLIENT_SECRET"):
            if p != "facebook" or re.fullmatch(r"v\d+\.\d+", settings.FACEBOOK_API_VERSION):
                resultado.append(p)
    return resultado


def contexto(request):
    return {"proveedores_sociales": [{"codigo": p, "nombre": NOMBRES[p]} for p in disponibles()]}


def cliente_oauth(proveedor):
    if proveedor not in disponibles():
        raise Http404
    oauth = OAuth()
    opciones = dict(client_id=getattr(settings, proveedor.upper()+"_CLIENT_ID"), client_secret=getattr(settings, proveedor.upper()+"_CLIENT_SECRET"), client_kwargs={"scope": "openid email profile", "timeout": 10, "code_challenge_method": "S256"})
    if proveedor == "google":
        opciones["server_metadata_url"] = "https://accounts.google.com/.well-known/openid-configuration"
    else:
        v = settings.FACEBOOK_API_VERSION
        opciones.update(authorize_url=f"https://www.facebook.com/{v}/dialog/oauth", access_token_url=f"https://graph.facebook.com/{v}/oauth/access_token", api_base_url=f"https://graph.facebook.com/{v}/", client_kwargs={"scope": "email public_profile", "timeout": 10, "token_endpoint_auth_method": "client_secret_post"})
    return oauth.register(proveedor, **opciones)


def fallo(request, texto="No se pudo completar el acceso. Intenta nuevamente."):
    messages.error(request, texto)
    return redirect("cuentas:social_conexiones" if request.user.is_authenticated else "cuentas:login")


@never_cache
@sensitive_post_parameters("actual")
@require_POST
def iniciar(request, proveedor):
    cliente = cliente_oauth(proveedor)
    if not _admitir(request, "acceso_social", 15, 600):
        return fallo(request, "Demasiados intentos. Espera unos minutos antes de volver a intentar.")
    vincular = request.POST.get("accion") == "vincular"
    if vincular:
        if not request.user.is_authenticated or not request.user.check_password(request.POST.get("actual", "")):
            return fallo(request, "Para vincular, inicia sesión y confirma tu contraseña actual de MTFlow.")
    elif request.user.is_authenticated:
        return fallo(request, "Para añadir un acceso, usa la opción Vincular de tu perfil.")
    request.session.pop("social_pendiente", None)
    request.session["social_flujo"] = {"proveedor": proveedor, "hora": time.time(), "usuario": request.user.pk if vincular else None, "firma": request.user.get_session_auth_hash() if vincular else None}
    try:
        return cliente.authorize_redirect(request, settings.SOCIAL_AUTH_BASE_URL+reverse("cuentas:social_callback", args=[proveedor]))
    except (OAuthError, JoseError, RequestException, ValueError):
        request.session.pop("social_flujo", None)
        return fallo(request)


def identidad(cliente, request, proveedor):
    # Authlib valida state, nonce y la firma/issuer/audiencia del ID token de Google.
    token = cliente.authorize_access_token(request)
    if not isinstance(token, Mapping):
        raise ValueError("Respuesta de autorización inválida")
    if proveedor == "google":
        if not token.get("id_token"):
            raise ValueError("Falta ID token")
        datos = token["userinfo"]
        if not isinstance(datos, Mapping):
            raise ValueError("Perfil inválido")
        if datos.get("email_verified") is not True:
            raise ValueError("Correo sin verificar")
        uid = datos.get("sub")
    else:
        prueba = hmac.new(settings.FACEBOOK_CLIENT_SECRET.encode(), token["access_token"].encode(), hashlib.sha256).hexdigest()
        respuesta = cliente.get("me", token=token, params={"fields": "id,first_name,last_name,email", "appsecret_proof": prueba})
        respuesta.raise_for_status()
        datos = respuesta.json()
        if not isinstance(datos, Mapping):
            raise ValueError("Perfil inválido")
        uid = datos.get("id")
    if not isinstance(uid, str) or not uid or len(uid) > 255:
        raise ValueError("Identificador inválido")
    # Nunca conservar tokens ni el perfil completo en la sesión/base de datos.
    return {"proveedor": proveedor, "identificador": uid,
            "email": str(datos.get("email") or "")[:254],
            "nombre": str(datos.get("given_name", datos.get("first_name", "")))[:60],
            "apellido": str(datos.get("family_name", datos.get("last_name", "")))[:60]}


@never_cache
@require_GET
def callback(request, proveedor):
    cliente = cliente_oauth(proveedor)
    flujo = request.session.pop("social_flujo", {})
    if flujo.get("proveedor") != proveedor or time.time()-flujo.get("hora", 0) > TTL:
        return fallo(request, "El intento de acceso venció. Inicia el proceso nuevamente.")
    uid = flujo.get("usuario")
    if uid is not None:
        if not request.user.is_authenticated or request.user.pk != uid or not constant_time_compare(flujo.get("firma", ""), request.user.get_session_auth_hash()):
            return fallo(request, "La sesión cambió. Vuelve a iniciar la vinculación desde tu perfil.")
    elif request.user.is_authenticated:
        return fallo(request, "La sesión cambió. Inicia el proceso nuevamente.")
    try:
        datos = identidad(cliente, request, proveedor)
    except (OAuthError, JoseError, RequestException, KeyError, TypeError, ValueError):
        return fallo(request, "No se pudo verificar el acceso o se canceló la autorización. Puedes volver a intentarlo.")
    existente = IdentidadSocial.objects.select_related("usuario").filter(proveedor=proveedor, identificador=datos["identificador"]).first()
    if uid is not None:
        try:
            with transaction.atomic():
                IdentidadSocial.objects.get_or_create(usuario=request.user, proveedor=proveedor, identificador=datos["identificador"])
        except IntegrityError:
            return fallo(request, "Ese acceso ya está vinculado. No se modificó ninguna cuenta.")
        messages.success(request, f"Tu cuenta de {NOMBRES[proveedor]} quedó vinculada.")
        return redirect("cuentas:social_conexiones")
    if existente:
        if not existente.usuario.is_active:
            return fallo(request, "No se pudo ingresar con esta cuenta. Contacta al estudio.")
        login(request, existente.usuario, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("clientes:inicio" if existente.usuario.es_cliente else "nucleo:inicio")
    if datos["email"] and Usuario.objects.filter(email__iexact=datos["email"]).exists():
        return fallo(request, "Ya existe una cuenta con ese correo. Ingresa con tu contraseña de MTFlow y vincula este acceso desde tu perfil.")
    request.session.cycle_key()
    request.session["social_pendiente"] = {**datos, "hora": time.time()}
    return redirect("cuentas:social_completar")


@never_cache
@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def completar(request):
    if request.user.is_authenticated:
        return redirect("cuentas:perfil")
    datos = request.session.get("social_pendiente", {})
    if datos.get("proveedor") not in disponibles() or time.time()-datos.get("hora", 0) > TTL:
        request.session.pop("social_pendiente", None)
        return fallo(request, "El registro venció. Vuelve a ingresar con Google o Facebook.")
    form = RegistroClienteForm(request.POST if request.method == "POST" else None, initial={k: datos[k] for k in ("email", "nombre", "apellido")})
    if datos["email"]:
        form.fields["email"].disabled = True
    status = 200
    if request.method == "POST":
        status = 400
        if not _admitir(request, "registro_social", 10, 600):
            form.add_error(None, "Demasiados intentos. Espera unos minutos.")
            status = 429
        elif form.is_valid():
            try:
                with transaction.atomic():
                    usuario = form.save()
                    IdentidadSocial.objects.create(usuario=usuario, proveedor=datos["proveedor"], identificador=datos["identificador"])
            except (IntegrityError, ValidationError):
                form.add_error(None, "No pudimos crear la cuenta. Revisa si ya tienes una cuenta y vincula el acceso desde su perfil.")
                status = 409
            else:
                request.session.pop("social_pendiente", None)
                login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("clientes:inicio")
    return render(request, "cuentas/social_completar.html", {"form": form, "proveedor": NOMBRES[datos["proveedor"]]}, status=status)


@login_required
@never_cache
@sensitive_post_parameters("actual")
@require_http_methods(["GET", "POST"])
def conexiones(request):
    if request.method == "POST":
        if not _admitir(request, "desvincular_social", 10, 600) or not request.user.check_password(request.POST.get("actual", "")):
            return fallo(request, "Confirma tu contraseña actual de MTFlow para desvincular el acceso.")
        IdentidadSocial.objects.filter(usuario=request.user, proveedor=request.POST.get("proveedor")).delete()
        messages.success(request, "Acceso desvinculado. Tu cuenta y tus solicitudes se conservan.")
        return redirect("cuentas:social_conexiones")
    return render(request, "cuentas/social_conexiones.html", {"vinculadas": request.user.identidades_sociales.all()})

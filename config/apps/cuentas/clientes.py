"""Portal de cliente: consultas limitadas a la cuenta autenticada."""
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods
from web.models import Postulacion, Imagen
from web.limites import _admitir
from .models import Rol, PerfilCliente
from .permisos import rol_requerido
from .forms_cliente import RegistroClienteForm, DatosClienteForm, ContactoClienteForm

solo_cliente = rol_requerido(Rol.USUARIO)


@sensitive_post_parameters("password1", "password2")
@never_cache
@require_http_methods(["GET", "POST"])
def registro(request):
    if request.user.is_authenticated:
        return redirect("nucleo:inicio")
    form = RegistroClienteForm(request.POST if request.method == "POST" else None)
    status = 200
    if request.method == "POST":
        status = 400
        if not _admitir(request, "registro_cliente", 5, 3600):
            form.add_error(None, "Se alcanzó el límite de intentos de registro. Inténtalo dentro de una hora.")
            status = 429
        elif form.is_valid():
            try:
                with transaction.atomic():
                    usuario = form.save()
            except (IntegrityError, ValidationError):
                form.add_error(None, "No pudimos crear la cuenta con esos datos. Revisa el nombre de usuario y el correo.")
                status = 409
            else:
                login(request, usuario)
                messages.success(request, "Tu cuenta está lista. Las solicitudes que envíes con esta sesión aparecerán aquí.")
                return redirect("clientes:inicio")
    response = render(request, "clientes/registro.html", {"form": form}, status=status)
    if status == 429:
        response["Retry-After"] = "3600"
    return response


def propias(user):
    return Postulacion.objects.filter(cuenta_cliente=user).select_related("tatuadora__usuario", "contacto")


@solo_cliente
@never_cache
@require_GET
def inicio(request):
    pagina = Paginator(propias(request.user).order_by("-creada_en", "-pk"), 12).get_page(request.GET.get("pagina"))
    return render(request, "clientes/inicio.html", {"pagina": pagina})


@solo_cliente
@never_cache
@require_GET
def detalle(request, referencia):
    p = get_object_or_404(propias(request.user), referencia=referencia)
    # Plantilla propia sin predicciones, notas, historial interno ni formularios de gestión.
    return render(request, "clientes/detalle.html", {"solicitud": p, "imagenes": p.imagen_set.order_by("orden"), "sesiones": p.sesiones.all()})


@solo_cliente
@never_cache
@require_GET
def imagen(request, referencia, orden):
    p = get_object_or_404(propias(request.user), referencia=referencia)
    im = get_object_or_404(Imagen, postulacion=p, orden=orden)
    raiz = Path(settings.MEDIA_ROOT).resolve()
    archivo = (raiz / im.url).resolve()
    if raiz not in archivo.parents or not archivo.is_file() or archivo.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        raise Http404
    return FileResponse(archivo.open("rb"), content_type="image/png" if archivo.suffix.lower() == ".png" else "image/jpeg")


@solo_cliente
@never_cache
@sensitive_post_parameters("datos-actual")
@require_http_methods(["GET", "POST"])
def perfil(request):
    contacto = PerfilCliente.objects.filter(usuario=request.user).first() or PerfilCliente(usuario=request.user)
    datos = DatosClienteForm(request.POST if request.method == "POST" else None, instance=request.user, prefix="datos")
    preferencias = ContactoClienteForm(request.POST if request.method == "POST" else None, instance=contacto, prefix="contacto")
    status = 200
    if request.method == "POST":
        status = 400
        validos = datos.is_valid(), preferencias.is_valid()
        if all(validos):
            try:
                with transaction.atomic():
                    usuario = datos.save(commit=False)
                    # Solo editar datos personales: nunca guardar roles de una instancia desactualizada.
                    usuario.save(update_fields=["nombre", "apellido", "email"])
                    preferencias.save()
            except IntegrityError:
                datos.add_error(None, "No se guardaron los cambios. El correo puede estar ocupado; revisa los datos.")
                status = 409
            else:
                messages.success(request, "Perfil actualizado. Los datos de solicitudes anteriores se conservan como fueron enviados.")
                return redirect("clientes:perfil")
    return render(request, "clientes/perfil.html", {"datos": datos, "preferencias": preferencias}, status=status)

import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from apps.nucleo.redirecciones import destino_seguro

from .forms import (
    CambiarMiContrasenaForm,
    CrearCuentaForm,
    EditarCuentaForm,
    LoginForm,
    RestablecerContrasenaForm,
)
from .models import Usuario
from .permisos import solo_admin

log = logging.getLogger("mtflow.seguridad")


# ---------------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------------
@sensitive_post_parameters("password")
@csrf_protect
@never_cache
@require_http_methods(["GET", "POST"])
def ingresar(request):
    if request.user.is_authenticated:
        return redirect("nucleo:inicio")
    destino = request.POST.get("next") or request.GET.get("next") or ""
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.usuario)  # rota el id de sesión (anti session fixation)
        log.info("Inicio de sesión usuario=%s", form.usuario.nombre_usuario)
        return redirect(destino_seguro(request, destino, "nucleo:inicio"))
    return render(request, "cuentas/login.html", {"form": form, "next": destino})


@require_POST
def salir(request):
    # Solo por POST con token CSRF: un enlace o imagen externa no puede cerrar la sesión.
    logout(request)
    return redirect("cuentas:login")


@sensitive_post_parameters("actual", "password1", "password2")
@login_required
@require_http_methods(["GET", "POST"])
def mi_contrasena(request):
    form = CambiarMiContrasenaForm(request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        update_session_auth_hash(request, usuario)  # cierra las otras sesiones abiertas
        messages.success(request, "Tu contraseña se actualizó.")
        return redirect("nucleo:inicio")
    return render(request, "cuentas/mi_contrasena.html", {"form": form})


# ---------------------------------------------------------------------------
# Gestión de cuentas (solo administradores)
# ---------------------------------------------------------------------------
@solo_admin
@require_http_methods(["GET"])
def lista(request):
    cuentas = Usuario.objects.select_related("creado_por").order_by("-is_active", "rol", "nombre")
    return render(request, "cuentas/lista.html", {"cuentas": cuentas})


@sensitive_post_parameters("password1", "password2")
@solo_admin
@require_http_methods(["GET", "POST"])
def crear(request):
    form = CrearCuentaForm(data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        cuenta = form.save(creado_por=request.user)
        log.info("Cuenta creada usuario=%s rol=%s por=%s",
                 cuenta.nombre_usuario, cuenta.rol, request.user.nombre_usuario)
        messages.success(
            request,
            f"Cuenta «{cuenta.nombre_usuario}» creada. Deberá cambiar la contraseña en su primer ingreso.",
        )
        return redirect("cuentas:lista")
    return render(request, "cuentas/form.html", {"form": form, "titulo": "Crear cuenta"})


@solo_admin
@require_http_methods(["GET", "POST"])
def editar(request, uuid):
    cuenta = get_object_or_404(Usuario, uuid=uuid)
    form = EditarCuentaForm(data=request.POST or None, instance=cuenta, editor=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log.info("Cuenta editada usuario=%s por=%s", cuenta.nombre_usuario, request.user.nombre_usuario)
        messages.success(request, "Cuenta actualizada.")
        return redirect("cuentas:lista")
    return render(request, "cuentas/form.html",
                  {"form": form, "titulo": f"Editar cuenta: {cuenta.nombre_usuario}", "cuenta": cuenta})


@sensitive_post_parameters("password1", "password2")
@solo_admin
@require_http_methods(["GET", "POST"])
def restablecer(request, uuid):
    cuenta = get_object_or_404(Usuario, uuid=uuid)
    if cuenta.pk == request.user.pk:
        return redirect("cuentas:mi_contrasena")
    form = RestablecerContrasenaForm(cuenta, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        log.info("Contraseña restablecida usuario=%s por=%s",
                 cuenta.nombre_usuario, request.user.nombre_usuario)
        messages.success(request, f"Se asignó una contraseña temporal a «{cuenta.nombre_usuario}».")
        return redirect("cuentas:lista")
    return render(request, "cuentas/form.html",
                  {"form": form, "titulo": f"Restablecer contraseña: {cuenta.nombre_usuario}"})

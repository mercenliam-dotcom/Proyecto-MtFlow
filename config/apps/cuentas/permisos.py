from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Rol


def rol_requerido(*roles):
    """
    Restringe una vista a ciertos roles. Se verifica en el SERVIDOR en cada
    petición: ocultar un botón en la plantilla no es una medida de seguridad.
    """
    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_active or request.user.rol not in roles:
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


solo_admin = rol_requerido(Rol.ADMIN)


class ForzarCambioContrasenaMiddleware:
    """Mientras la contraseña sea temporal, solo se permite cambiarla o salir."""

    PERMITIDAS = ("cuentas:mi_contrasena", "cuentas:logout")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.debe_cambiar_contrasena:
            from django.urls import resolve, Resolver404
            try:
                nombre = resolve(request.path_info).view_name
            except Resolver404:
                nombre = ""
            if nombre not in self.PERMITIDAS:
                return redirect("cuentas:mi_contrasena")
        return self.get_response(request)

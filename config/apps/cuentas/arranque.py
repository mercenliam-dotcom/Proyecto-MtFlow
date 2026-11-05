"""Cuenta de desarrollo solicitada por el usuario y limpieza en producción."""
import asyncio
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured
from django.db.models.deletion import ProtectedError, RestrictedError

log = logging.getLogger("mtflow.seguridad")


def preparar_admin_entorno(using="default"):
    from .models import Rol, Usuario
    usuarios = Usuario.objects.db_manager(using)
    if not settings.DEBUG:
        # Solo se borran cuentas identificadas como predeterminadas, aunque se
        # hayan renombrado. Un administrador real llamado admin no se modifica.
        for usuario in usuarios.filter(es_admin_desarrollo=True):
            try:
                usuario.delete(using=using)
            except (ProtectedError, RestrictedError) as exc:
                # No perder propuestas/historial para eliminar la cuenta. Impedir
                # acceso y detener el arranque hasta resolver las dependencias.
                usuario.is_active = False
                usuario.set_unusable_password()
                usuario.save(using=using, update_fields=["is_active", "password"])
                raise ImproperlyConfigured(
                    "La cuenta predeterminada de desarrollo tiene datos vinculados. "
                    "Se deshabilitó; reasigna sus dependencias y elimínala antes de iniciar producción."
                ) from exc
        return

    existente = usuarios.filter(nombre_usuario="admin").first()
    if existente is not None and not existente.es_admin_desarrollo:
        # Nunca sustituir una cuenta legítima ni su contraseña.
        return
    if existente is None:
        existente, _ = usuarios.get_or_create(nombre_usuario="admin", defaults={
            "email": "admin-desarrollo@example.test", "nombre": "Admin", "apellido": "Desarrollo",
            "rol": Rol.ADMIN, "is_superuser": True, "is_active": True,
            "es_tatuadora": False, "es_admin_desarrollo": True,
            "debe_cambiar_contrasena": False, "password": make_password("admin"),
        })
    if not existente.es_admin_desarrollo:
        return
    cambios = []
    for campo, valor in {"rol": Rol.ADMIN, "is_superuser": True, "is_active": True,
                         "debe_cambiar_contrasena": False}.items():
        if getattr(existente, campo) != valor:
            setattr(existente, campo, valor)
            cambios.append(campo)
    if not existente.check_password("admin"):
        existente.set_password("admin")
        cambios.append("password")
    if cambios:
        existente.save(using=using, update_fields=cambios)


def despues_de_migrar(sender, using="default", **kwargs):
    preparar_admin_entorno(using=using)


class ArranqueASGI:
    """Ejecutar el arranque síncrono en un hilo, una vez por proceso ASGI."""
    def __init__(self, aplicacion):
        self.aplicacion = aplicacion
        self._preparado = False
        self._lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if not self._preparado:
            async with self._lock:
                if not self._preparado:
                    await sync_to_async(preparar_admin_entorno, thread_sensitive=True)()
                    self._preparado = True
        return await self.aplicacion(scope, receive, send)

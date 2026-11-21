"""Imagen de referencia «pendiente»: queda guardada mientras se completa la solicitud.

Problema que resuelve: si el envío fallaba (un dato mal escrito, un correo sin
verificar), el navegador devolvía la página con el campo de archivo vacío y había
que volver a elegir la imagen.

Ahora, apenas la imagen se valida (al elegirla o al enviar), se guarda en
media_privado/pendientes/ con un token aleatorio que solo vale para la sesión del
navegador que la subió. Los reintentos usan ese token. La imagen se descarta al
completar la solicitud, al quitarla o al reemplazarla; las abandonadas se borran
solas después de PENDIENTE_HORAS.
"""
import os
import secrets
import time
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.nucleo.imagenes import validar_imagen

CLAVE_SESION = "imagenes_pendientes"
CARPETA = "pendientes"
PENDIENTE_HORAS = 24
MAXIMO_POR_SESION = 5


def _carpeta():
    ruta = Path(settings.MEDIA_ROOT) / CARPETA
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _registro(request):
    return dict(request.session.get(CLAVE_SESION, {}))


def _ruta(token, datos):
    return _carpeta() / f"{token}.{datos['ext']}"


def _limpiar_vencidas():
    limite = time.time() - PENDIENTE_HORAS * 3600
    for archivo in _carpeta().iterdir():
        try:
            if archivo.is_file() and archivo.stat().st_mtime < limite:
                archivo.unlink()
        except OSError:
            pass


def guardar(request, validada):
    """Guarda la imagen ya validada y devuelve su token."""
    _limpiar_vencidas()
    token = secrets.token_urlsafe(18)
    ext = "jpg" if validada.formato == "JPEG" else "png"
    validada.archivo.seek(0)
    datos = {"ext": ext, "nombre": (validada.nombre_original or f"referencia.{ext}")[:120], "ts": time.time()}
    _ruta(token, datos).write_bytes(validada.archivo.read())
    validada.archivo.seek(0)
    registro = _registro(request)
    registro[token] = datos
    # Solo se conservan las más recientes de esta sesión.
    for viejo in sorted(registro, key=lambda t: registro[t]["ts"])[:-MAXIMO_POR_SESION]:
        descartar_token(registro, viejo)
    request.session[CLAVE_SESION] = registro
    return token


def datos(request, token):
    registro = _registro(request)
    info = registro.get(token or "")
    if not info or not _ruta(token, info).is_file():
        return None
    return info


def cargar(request, token):
    """Devuelve la ImagenValidada guardada con ese token, o None si no existe en esta sesión."""
    info = datos(request, token)
    if not info:
        return None
    contenido = _ruta(token, info).read_bytes()
    tipo = "image/jpeg" if info["ext"] == "jpg" else "image/png"
    return validar_imagen(SimpleUploadedFile(info["nombre"], contenido, content_type=tipo))


def descartar_token(registro, token):
    info = registro.pop(token, None)
    if info:
        try:
            os.remove(_ruta(token, info))
        except OSError:
            pass


def descartar(request, token):
    registro = _registro(request)
    descartar_token(registro, token)
    request.session[CLAVE_SESION] = registro


@never_cache
@require_GET
def ver(request, token):
    """Vista previa de la imagen pendiente; solo para la sesión que la subió."""
    info = datos(request, token)
    if not info:
        raise Http404
    respuesta = FileResponse(open(_ruta(token, info), "rb"), content_type="image/jpeg" if info["ext"] == "jpg" else "image/png")
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta

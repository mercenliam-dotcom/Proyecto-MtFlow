import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .firmas import leer_ruta_firmada


@login_required
@require_GET
def inicio(request):
    return render(request, "nucleo/inicio.html")


@login_required
@require_GET
def archivo(request, token):
    """Sirve un archivo privado solo si el token firmado es válido y no ha caducado."""
    ruta_relativa = leer_ruta_firmada(token)
    if not ruta_relativa:
        raise Http404
    raiz = Path(settings.MEDIA_ROOT).resolve()
    ruta = (raiz / ruta_relativa).resolve()
    # Impide salir de MEDIA_ROOT con "../" aunque la firma fuera válida.
    if raiz not in ruta.parents or not ruta.is_file():
        raise Http404
    tipo, _ = mimetypes.guess_type(ruta.name)
    if tipo not in ("image/jpeg", "image/png"):
        raise Http404
    respuesta = FileResponse(open(ruta, "rb"), content_type=tipo)
    respuesta["Content-Disposition"] = "inline"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta

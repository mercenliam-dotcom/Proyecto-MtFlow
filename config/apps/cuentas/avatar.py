"""Foto de perfil: subir, quitar y mostrar. Privada: solo la ve la persona y el equipo."""
import io
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, ImageOps

from apps.nucleo.imagenes import validar_imagen
from .models import Usuario, Rol

LADO = 320  # px de la imagen guardada (cuadrada)


def _almacen():
    return FileSystemStorage(location=settings.MEDIA_ROOT)


def _cuadrada(validada):
    """Recorta al centro en cuadrado y reduce a LADO px; conserva transparencia en PNG."""
    img = Image.open(io.BytesIO(validada.archivo.read()))
    img = ImageOps.fit(img, (LADO, LADO), method=Image.Resampling.LANCZOS)
    salida = io.BytesIO()
    if validada.formato == "PNG":
        img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB").save(salida, format="PNG", optimize=True)
        ext = "png"
    else:
        img.convert("RGB").save(salida, format="JPEG", quality=90, optimize=True)
        ext = "jpg"
    return ContentFile(salida.getvalue()), ext


def _borrar(ruta):
    if ruta and ruta.startswith("avatares/"):
        _almacen().delete(ruta)


@login_required
@require_POST
def subir(request):
    archivo = request.FILES.get("avatar")
    if not archivo:
        messages.error(request, "Elige una imagen JPG o PNG.")
        return redirect("cuentas:perfil")
    try:
        # Un ícono puede ser plano o pequeño: no se exige nitidez y basta con 64 px.
        contenido, ext = _cuadrada(validar_imagen(archivo, exigir_nitidez=False, lado_min=64))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("cuentas:perfil")
    anterior = request.user.avatar
    ruta = _almacen().save(f"avatares/{request.user.uuid.hex}/{uuid.uuid4().hex}.{ext}", contenido)
    Usuario.objects.filter(pk=request.user.pk).update(avatar=ruta)
    _borrar(anterior)
    messages.success(request, "Foto de perfil actualizada.")
    return redirect("cuentas:perfil")


@login_required
@require_POST
def quitar(request):
    _borrar(request.user.avatar)
    Usuario.objects.filter(pk=request.user.pk).update(avatar="")
    messages.success(request, "Foto de perfil quitada.")
    return redirect("cuentas:perfil")


@login_required
@require_GET
def imagen(request, usuario):
    dueno = get_object_or_404(Usuario, uuid=usuario, is_active=True)
    if dueno.pk != request.user.pk and request.user.rol != Rol.ADMIN:
        raise Http404
    raiz = Path(settings.MEDIA_ROOT).resolve()
    archivo = (raiz / dueno.avatar).resolve() if dueno.avatar else None
    if not archivo or not dueno.avatar.startswith("avatares/") or raiz not in archivo.parents or not archivo.is_file():
        raise Http404
    respuesta = FileResponse(open(archivo, "rb"), content_type="image/png" if archivo.suffix == ".png" else "image/jpeg")
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=86400"  # la URL cambia (?v=) al reemplazar la foto
    return respuesta

"""
Validación estricta de imágenes subidas.

Regla: solo se aceptan imágenes JPG y PNG reales. Todo lo demás se rechaza:
documentos (PDF, Word), videos (MP4, MOV, WEBM), GIF y PNG animados, WebP,
HEIC, SVG (puede contener scripts) y cualquier archivo disfrazado con una
extensión falsa.

No se confía en nada que declare el cliente:
  - la EXTENSIÓN del nombre se puede cambiar  (video.mp4 -> video.jpg)
  - el Content-Type lo escribe el navegador o el atacante
Por eso la decisión se toma leyendo el CONTENIDO real del archivo.

Validaciones, en orden (de la más barata a la más cara):
  1. Tamaño en bytes (antes de leer nada)
  2. Nombre: extensión .jpg/.jpeg/.png, sin caracteres de control
  3. Firma binaria ("número mágico") de JPEG o PNG
  4. Decodificación completa con Pillow (detecta archivos truncados o
     manipulados) con límite de píxeles (anti bomba de descompresión)
  5. Formato decodificado == formato de la extensión
  6. Sin animación (descarta APNG)
  7. Dimensiones mínimas y máximas
  8. Nitidez mínima (filtro de calidad previo a la inferencia)

Finalmente la imagen se RE-CODIFICA desde los píxeles: el archivo que se
guarda es uno nuevo generado por nosotros. Así se eliminan metadatos EXIF
(que pueden incluir coordenadas GPS del cliente) y cualquier contenido
"políglota" escondido después de los datos de imagen.
"""
from __future__ import annotations

import io
import os
import unicodedata
import uuid
import warnings
from dataclasses import dataclass

import numpy as np
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

FIRMA_JPEG = b"\xff\xd8\xff"
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"

EXTENSIONES = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
}
TIPOS_ACEPTADOS_HTML = "image/jpeg,image/png"  # solo pista para el navegador


def configurar_campo_imagen(campo):
    """El navegador muestra y comprueba el mismo límite de peso que el servidor."""
    campo.widget.attrs["data-max-bytes"] = settings.IMAGEN_MAX_BYTES


def _validar_dimensiones(ancho, alto):
    if ancho * alto > settings.IMAGEN_MAX_PIXELES:
        raise ValidationError("La imagen tiene demasiados píxeles.", code="bomba")
    if min(ancho, alto) < settings.IMAGEN_LADO_MIN_PX:
        raise ValidationError(
            f"La imagen es demasiado pequeña: el lado menor debe medir al menos "
            f"{settings.IMAGEN_LADO_MIN_PX} píxeles.", code="pequena",
        )
    if max(ancho, alto) > settings.IMAGEN_LADO_MAX_PX:
        raise ValidationError(
            f"La imagen es demasiado grande: el lado mayor no puede superar "
            f"{settings.IMAGEN_LADO_MAX_PX} píxeles.", code="grande",
        )

# Firmas de formatos que la gente intenta subir con frecuencia, para dar un
# mensaje claro. No es la defensa: la defensa es que solo pasan JPEG y PNG.
_FIRMAS_CONOCIDAS = [
    (b"%PDF", "un documento PDF"),
    (b"PK\x03\x04", "un documento comprimido (Word, Excel, ZIP)"),
    (b"\xd0\xcf\x11\xe0", "un documento de Office antiguo"),
    (b"GIF87a", "un GIF"),
    (b"GIF89a", "un GIF"),
    (b"\x1a\x45\xdf\xa3", "un video (WebM/MKV)"),
    (b"RIFF", "un archivo WebP, AVI o WAV"),
    (b"<svg", "un SVG"),
    (b"<?xml", "un archivo XML/SVG"),
    (b"<!DOCTYPE", "una página HTML"),
    (b"<html", "una página HTML"),
]


@dataclass
class ImagenValidada:
    archivo: ContentFile        # imagen re-codificada, lista para guardar
    formato: str                # "JPEG" o "PNG"
    ancho_px: int
    alto_px: int
    nitidez: float
    nombre_original: str


def _es_video_iso(cabecera: bytes) -> bool:
    # MP4, MOV, 3GP, HEIC/AVIF: caja "ftyp" en los bytes 4..8
    return len(cabecera) >= 12 and cabecera[4:8] == b"ftyp"


def _describir_formato(cabecera: bytes) -> str | None:
    if _es_video_iso(cabecera):
        return "un video o una imagen HEIC/AVIF"
    inicio = cabecera.lstrip()[:16].lower()
    for firma, descripcion in _FIRMAS_CONOCIDAS:
        if cabecera.startswith(firma) or inicio.startswith(firma.lower()):
            return descripcion
    return None


def _nombre_limpio(nombre: str) -> str:
    nombre = os.path.basename(nombre or "")
    if not nombre or len(nombre) > 200:
        raise ValidationError("El nombre del archivo no es válido.", code="nombre")
    if any(unicodedata.category(c).startswith("C") for c in nombre):
        raise ValidationError("El nombre del archivo contiene caracteres no permitidos.", code="nombre")
    return nombre


def calcular_nitidez(img: Image.Image) -> float:
    """
    Varianza del laplaciano sobre la imagen en escala de grises, reducida a
    un máximo de 1024 px por lado para que el valor no dependa de la
    resolución. Mismo cálculo que usa revisar_dataset.py.
    """
    gris = img.convert("L")
    gris.thumbnail((1024, 1024))
    a = np.asarray(gris, dtype=np.float32)
    if a.shape[0] < 3 or a.shape[1] < 3:
        return 0.0
    lap = (
        a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4.0 * a[1:-1, 1:-1]
    )
    return float(lap.var())



def _decodificar(datos: bytes, formato_real: str) -> Image.Image:
    with warnings.catch_warnings():
        # Superar el límite de píxeles se trata como error, no como aviso.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(datos)) as prueba:
            if prueba.format != formato_real:
                raise ValidationError("El contenido de la imagen no es válido.", code="formato")
            # 6. Sin animación (descarta APNG)
            if getattr(prueba, "is_animated", False) or getattr(prueba, "n_frames", 1) > 1:
                raise ValidationError("No se aceptan imágenes animadas ni videos.", code="animada")
            _validar_dimensiones(*prueba.size)
            prueba.verify()  # recorre el archivo completo y valida su estructura
        img = Image.open(io.BytesIO(datos))
        try:
            img.load()  # decodifica todos los píxeles
        except BaseException:
            img.close()
            raise
    return img

def validar_imagen(archivo) -> ImagenValidada:
    """Valida un archivo subido y devuelve la imagen re-codificada, o lanza ValidationError."""
    # 1. Tamaño
    tamano = getattr(archivo, "size", None)
    if tamano is None:
        raise ValidationError("No se recibió ningún archivo.", code="vacio")
    if tamano == 0:
        raise ValidationError("El archivo está vacío.", code="vacio")
    if tamano > settings.IMAGEN_MAX_BYTES:
        mb = settings.IMAGEN_MAX_BYTES // (1024 * 1024)
        raise ValidationError(f"La imagen supera el máximo de {mb} MB.", code="tamano")

    # 2. Nombre y extensión
    nombre = _nombre_limpio(getattr(archivo, "name", ""))
    extension = os.path.splitext(nombre)[1].lower()
    if extension not in EXTENSIONES:
        raise ValidationError(
            "Solo se aceptan imágenes en formato JPG o PNG.", code="extension"
        )
    formato_esperado = EXTENSIONES[extension]

    # 3. Firma binaria real
    archivo.seek(0)
    datos = archivo.read(settings.IMAGEN_MAX_BYTES + 1)
    archivo.seek(0)
    if len(datos) > settings.IMAGEN_MAX_BYTES:
        raise ValidationError("La imagen supera el tamaño máximo permitido.", code="tamano")
    cabecera = datos[:32]
    if cabecera.startswith(FIRMA_JPEG):
        formato_real = "JPEG"
    elif cabecera.startswith(FIRMA_PNG):
        formato_real = "PNG"
    else:
        que_es = _describir_formato(cabecera)
        detalle = f" El archivo parece ser {que_es}." if que_es else ""
        raise ValidationError(
            "El archivo no es una imagen JPG o PNG válida." + detalle, code="firma"
        )

    # 5 (anticipado). La extensión debe corresponder al contenido.
    if formato_real != formato_esperado:
        raise ValidationError(
            "La extensión del archivo no corresponde a su contenido.", code="extension_falsa"
        )

    # 4. Decodificación completa con límite de píxeles
    Image.MAX_IMAGE_PIXELS = settings.IMAGEN_MAX_PIXELES
    try:
        img = _decodificar(datos, formato_real)
    except ValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError("La imagen tiene demasiados píxeles.", code="bomba")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValidationError("La imagen está dañada o no se puede leer.", code="corrupta")

    try:
        # Sin EXIF de orientación, exif_transpose() antes copiaba toda la foto.
        ImageOps.exif_transpose(img, in_place=True)
        ancho, alto = img.size
        nitidez = calcular_nitidez(img)
        if nitidez < settings.IMAGEN_NITIDEZ_MIN:
            raise ValidationError(
                "La imagen está demasiado borrosa para analizarla. Sube una foto más nítida.",
                code="borrosa",
            )
        # Se conserva la imagen validada para la tatuadora, sin metadatos ni
        # cambios de resolución/calidad respecto de la versión anterior.
        modo = "RGB" if formato_real == "JPEG" else "RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB"
        limpia = img if img.mode == modo else img.convert(modo)
        try:
            with io.BytesIO() as salida:
                if formato_real == "JPEG":
                    limpia.save(salida, format="JPEG", quality=92, optimize=True)
                    ext = "jpg"
                else:
                    limpia.save(salida, format="PNG", optimize=True)
                    ext = "png"
                contenido = salida.getvalue()
        finally:
            if limpia is not img:
                limpia.close()
        return ImagenValidada(
            archivo=ContentFile(contenido, name=f"{uuid.uuid4().hex}.{ext}"),
            formato=formato_real, ancho_px=ancho, alto_px=alto,
            nitidez=round(nitidez, 2), nombre_original=nombre,
        )
    finally:
        img.close()

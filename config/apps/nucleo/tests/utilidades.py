"""Generadores de archivos de prueba: imágenes válidas y archivos maliciosos."""
import io

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def imagen_bytes(formato="JPEG", tamano=(400, 300), nitida=True, modo="RGB", exif=None):
    if nitida:
        rng = np.random.default_rng(42)
        arr = rng.integers(0, 255, size=(tamano[1], tamano[0], 3), dtype=np.uint8)
        img = Image.fromarray(arr, "RGB")
    else:
        img = Image.new("RGB", tamano, (180, 160, 150))  # color plano: nitidez 0
    if modo != "RGB":
        img = img.convert(modo)
    buf = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    img.save(buf, format=formato, **kwargs)
    return buf.getvalue()


def subido(nombre, contenido, tipo="image/jpeg"):
    return SimpleUploadedFile(nombre, contenido, content_type=tipo)


def jpg_valido(nombre="referencia.jpg", **kw):
    return subido(nombre, imagen_bytes("JPEG", **kw), "image/jpeg")


def png_valido(nombre="referencia.png", **kw):
    return subido(nombre, imagen_bytes("PNG", **kw), "image/png")


def png_animado():
    rng = np.random.default_rng(1)
    cuadros = [Image.fromarray(rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)) for _ in range(3)]
    buf = io.BytesIO()
    cuadros[0].save(buf, format="PNG", save_all=True, append_images=cuadros[1:], duration=100, loop=0)
    return buf.getvalue()


def gif_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (1, 2, 3)).save(buf, format="GIF")
    return buf.getvalue()


def webp_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (1, 2, 3)).save(buf, format="WEBP")
    return buf.getvalue()


MP4_FALSO = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 2000
MOV_FALSO = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  " + b"\x00" * 2000
WEBM_FALSO = b"\x1a\x45\xdf\xa3" + b"\x00" * 2000
PDF_FALSO = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n" + b"0" * 2000
DOCX_FALSO = b"PK\x03\x04" + b"\x00" * 2000
SVG_CON_SCRIPT = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
HTML_CON_SCRIPT = b"<!DOCTYPE html><html><script>alert(document.cookie)</script></html>"

"""Dónde se guardan las imágenes de referencia que envían los clientes.

Una carpeta general y, dentro, una carpeta por tatuadora (no una por solicitud):

    media_privado/referencias/<tatuadora>/MT-1A2B3C4D_valentina-soto_2026-11-11.jpg

El nombre del archivo lleva el código corto de la solicitud, el nombre de quien
la envió y la fecha, para reconocerla a simple vista. La base de datos guarda
esta misma ruta relativa en ``Imagen.url``; con un bucket S3 la ruta se usa
tal cual como clave del objeto.
"""
from pathlib import PurePosixPath

from django.utils import timezone
from django.utils.text import slugify

CARPETA = "referencias"


def carpeta_tatuadora(tatuadora):
    """Nombre de usuario de la cuenta: único y estable aunque cambie el nombre visible."""
    return slugify(tatuadora.usuario.nombre_usuario)[:60] or f"tatuadora-{tatuadora.pk}"


def ruta_referencia(tatuadora, referencia, nombre_cliente, nombre_archivo, fecha=None):
    codigo = "MT-" + referencia.hex[:8].upper()
    cliente = slugify(nombre_cliente)[:40].strip("-") or "cliente"
    fecha = (fecha or timezone.localdate()).isoformat()
    extension = PurePosixPath(nombre_archivo).suffix.lower() or ".jpg"
    return f"{CARPETA}/{carpeta_tatuadora(tatuadora)}/{codigo}_{cliente}_{fecha}{extension}"

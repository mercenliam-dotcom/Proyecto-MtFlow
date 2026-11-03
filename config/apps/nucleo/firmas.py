"""
URLs firmadas para archivos privados.

Las imágenes de referencia son datos personales (Ley 19.628 / Ley 21.719).
No se publican en una carpeta pública con una ruta adivinable como
/media/postulacion/15/imagen1.jpg. En su lugar la ruta interna se firma
criptográficamente (HMAC con SECRET_KEY) y caduca a los pocos minutos:

    /archivo/<token-firmado>/

Si alguien altera un solo carácter del token, la firma deja de calzar y la
vista responde 404. Si el enlace se filtra, deja de servir al caducar.
"""
from django.conf import settings
from django.core import signing
from django.urls import reverse

_SAL = "mtflow.archivo-privado"


def firmar_ruta(ruta_relativa: str) -> str:
    return signing.dumps(ruta_relativa, salt=_SAL, compress=True)


def leer_ruta_firmada(token: str) -> str | None:
    try:
        return signing.loads(token, salt=_SAL, max_age=settings.URL_FIRMADA_SEGUNDOS)
    except signing.BadSignature:  # incluye SignatureExpired
        return None


def url_archivo(ruta_relativa: str) -> str:
    return reverse("nucleo:archivo", args=[firmar_ruta(ruta_relativa)])

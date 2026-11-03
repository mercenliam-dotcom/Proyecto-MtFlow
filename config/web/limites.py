"""Límite de solicitudes antes de decodificar imágenes o consumir inferencias."""
import hashlib
from django.conf import settings
from django.core.cache import cache
from apps.cuentas.seguridad import ip_cliente


def admitir_cotizacion(request):
    clave = "cotizacion:" + hashlib.sha256(ip_cliente(request).encode()).hexdigest()
    ventana = settings.COTIZACION_VENTANA_SEGUNDOS
    if cache.add(clave, 1, ventana):
        return True
    try:
        total = cache.incr(clave)
    except ValueError:
        return cache.add(clave, 1, ventana)
    return total <= settings.COTIZACION_MAX_INTENTOS

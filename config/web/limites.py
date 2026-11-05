"""Límite de solicitudes antes de decodificar imágenes o consumir inferencias."""
import hashlib
from django.conf import settings
from django.core.cache import cache
from apps.cuentas.seguridad import ip_cliente


def admitir_cotizacion(request):
    return _admitir(request, "cotizacion", settings.COTIZACION_MAX_INTENTOS,
                    settings.COTIZACION_VENTANA_SEGUNDOS)


def admitir_analisis(request):
    return _admitir(request, "analisis", settings.ANALISIS_MAX_INTENTOS,
                    settings.ANALISIS_VENTANA_SEGUNDOS)


def _admitir(request, prefijo, maximo, ventana):
    clave = prefijo + ":" + hashlib.sha256(ip_cliente(request).encode()).hexdigest()
    if cache.add(clave, 1, ventana):
        return True
    try:
        total = cache.incr(clave)
    except ValueError:
        return cache.add(clave, 1, ventana)
    return total <= maximo

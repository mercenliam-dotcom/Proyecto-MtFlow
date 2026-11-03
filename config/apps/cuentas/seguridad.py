"""
Bloqueo temporal por intentos fallidos de inicio de sesión (fuerza bruta).

Se cuentan los fallos por nombre de usuario y por dirección IP. Al llegar a
LOGIN_MAX_INTENTOS se bloquea durante LOGIN_BLOQUEO_SEGUNDOS. El mensaje al
usuario es siempre el mismo, exista o no la cuenta, para no revelar qué
nombres de usuario son válidos.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("mtflow.seguridad")


def ip_cliente(request) -> str:
    # Detrás de Cloud Run la IP real llega en X-Forwarded-For. Solo se confía
    # en ese encabezado si hay un proxy delante (CONFIAR_EN_PROXY); si no,
    # cualquiera podría inventarlo para esquivar el bloqueo por IP. Se toma el
    # ÚLTIMO valor, que es el que agrega el proxy; los anteriores los puede
    # escribir el cliente.
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada and settings.CONFIAR_EN_PROXY:
        return reenviada.split(",")[-1].strip()[:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def _clave(tipo: str, valor: str) -> str:
    resumen = hashlib.sha256(valor.lower().encode()).hexdigest()[:32]
    return f"login:{tipo}:{resumen}"


def esta_bloqueado(nombre_usuario: str, ip: str) -> bool:
    maximo = settings.LOGIN_MAX_INTENTOS
    return (
        cache.get(_clave("u", nombre_usuario), 0) >= maximo
        or cache.get(_clave("ip", ip), 0) >= maximo * 4
    )


def registrar_fallo(nombre_usuario: str, ip: str) -> None:
    for clave in (_clave("u", nombre_usuario), _clave("ip", ip)):
        cache.add(clave, 0, settings.LOGIN_BLOQUEO_SEGUNDOS)
        try:
            cache.incr(clave)
        except ValueError:
            cache.set(clave, 1, settings.LOGIN_BLOQUEO_SEGUNDOS)
    log.warning("Inicio de sesión fallido usuario=%r ip=%s", nombre_usuario[:30], ip)


def limpiar_fallos(nombre_usuario: str) -> None:
    cache.delete(_clave("u", nombre_usuario))

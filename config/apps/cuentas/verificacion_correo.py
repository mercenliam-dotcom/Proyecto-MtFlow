"""Revisión automática del correo mientras se escribe (sin servicios pagados).

Se consulta el DNS para confirmar que el dominio recibe correo (registros MX):
rechaza dominios inexistentes y sugiere los errores típicos («gmial.com» →
«gmail.com»). Si el DNS no responde (sin internet), no bloquea.

Límite: ningún método gratuito confirma que la casilla exacta exista (Gmail y
Outlook no lo revelan); eso solo se sabe enviando un correo. Aquí se valida el
dominio, que es donde ocurren la mayoría de los errores de escritura.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .seguridad import ip_cliente

log = logging.getLogger("mtflow.seguridad")

MAX_REVISIONES_HORA_IP = 120

ERRORES_TIPICOS = {
    "gmial.com": "gmail.com", "gmal.com": "gmail.com", "gmai.com": "gmail.com", "gmail.co": "gmail.com",
    "gamil.com": "gmail.com", "gmail.cl": "gmail.com", "hotmial.com": "hotmail.com", "hotmal.com": "hotmail.com",
    "hotmail.co": "hotmail.com", "outlok.com": "outlook.com", "outllok.com": "outlook.com", "yaho.com": "yahoo.com",
    "yahoo.co": "yahoo.com", "icloud.co": "icloud.com",
}


# Proveedores conocidos: no se consultan (más rápido y no dependen de la red).
CONOCIDOS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.cl", "hotmail.es", "outlook.com", "outlook.cl", "outlook.es",
    "live.com", "live.cl", "msn.com", "yahoo.com", "yahoo.es", "ymail.com", "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "inacapmail.cl", "inacap.cl", "uc.cl", "uchile.cl", "usach.cl",
}


def _dns_confiable():
    """Algunas redes (filtros escolares, wifi de eventos) responden «no existe» a todo.
    Si el DNS ni siquiera encuentra gmail.com, no se puede confiar en él: no se bloquea."""
    guardado = cache.get("dns_confiable")
    if guardado is not None:
        return guardado
    try:
        import dns.resolver
        dns.resolver.resolve("gmail.com", "MX", lifetime=4)
        confiable = True
    except Exception:  # noqa: BLE001 — cualquier fallo significa «no confiable»
        confiable = False
    cache.set("dns_confiable", confiable, 600)
    return confiable


def _normalizar(email):
    return (email or "").strip().lower()


# ---------------------------------------------------------------------------
# 1. Dominio
# ---------------------------------------------------------------------------
def revisar_dominio(email):
    """Devuelve un mensaje de error en español, o "" si el dominio recibe correo."""
    dominio = _normalizar(email).rsplit("@", 1)[-1]
    if dominio in ERRORES_TIPICOS:
        return f"Revisa el correo: ¿quisiste decir «{email.rsplit('@', 1)[0]}@{ERRORES_TIPICOS[dominio]}»?"
    if not getattr(settings, "VERIFICACION_DNS_ACTIVA", True) or dominio in CONOCIDOS:
        return ""
    clave = "dominio_correo:" + hashlib.sha256(dominio.encode()).hexdigest()
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado
    try:
        import dns.exception
        import dns.resolver
        try:
            dns.resolver.resolve(dominio, "MX", lifetime=4)
            mensaje = ""
        except dns.resolver.NoAnswer:
            # Sin MX, el correo se entrega al registro A del dominio (RFC 5321).
            dns.resolver.resolve(dominio, "A", lifetime=4)
            mensaje = ""
    except ImportError:
        log.warning("dnspython no está instalado: no se verifica el dominio del correo")
        return ""
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        if not _dns_confiable():
            log.warning("El DNS de esta red no es confiable; el correo se acepta sin revisar el dominio")
            return ""
        mensaje = f"El dominio «{dominio}» no existe o no recibe correos. Revisa que esté bien escrito."
    except (dns.exception.Timeout, dns.resolver.NoNameservers, dns.resolver.NoResolverConfiguration, OSError):
        log.warning("No se pudo consultar el DNS del dominio de un correo; se acepta sin verificar")
        return ""  # sin conexión no se bloquea a nadie; el código igual confirma la casilla
    cache.set(clave, mensaje, 24 * 3600)
    return mensaje


def validar_dominio_correo(valor):
    """Validador para campos de correo de los formularios."""
    mensaje = revisar_dominio(valor)
    if mensaje:
        raise ValidationError(mensaje, code="dominio_correo")


def sugerencia(email):
    """Correo corregido si el dominio es un error típico; si no, ""."""
    usuario, _, dominio = _normalizar(email).rpartition("@")
    return f"{usuario}@{ERRORES_TIPICOS[dominio]}" if usuario and dominio in ERRORES_TIPICOS else ""


@require_GET
def vista_revisar(request):
    """La usa revisar-correo.js al escribir. El formulario lo vuelve a validar al enviar."""
    email = (request.GET.get("email") or "").strip()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "mensaje": "Escribe un correo válido, por ejemplo nombre@correo.cl."})
    clave = "revisar_correo:" + ip_cliente(request)
    if cache.get(clave, 0) >= MAX_REVISIONES_HORA_IP:
        return JsonResponse({"ok": True, "mensaje": ""})  # sin bloquear: el servidor revisa igual al enviar
    cache.set(clave, cache.get(clave, 0) + 1, 3600)
    mensaje = revisar_dominio(email)
    return JsonResponse({"ok": not mensaje, "mensaje": mensaje, "sugerencia": sugerencia(email)})

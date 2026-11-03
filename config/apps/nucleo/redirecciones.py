"""
Redirecciones seguras (protección contra "open redirect").

Un atacante puede enviar un enlace como
    https://mtflow.cl/cuentas/ingresar/?next=https://sitio-falso.com
para que, tras iniciar sesión en el sitio real, la víctima termine en una
copia falsa. Por eso NUNCA se redirige a un destino que venga del usuario
sin validarlo antes.
"""
from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme


def destino_seguro(request, destino, por_defecto):
    """Devuelve `destino` solo si es una ruta interna del propio sitio."""
    if destino and url_has_allowed_host_and_scheme(
        url=destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        # Además se exige que sea una ruta relativa (empieza con "/" pero no "//").
        if destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
            return destino
    return resolve_url(por_defecto)

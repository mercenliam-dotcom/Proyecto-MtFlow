from django.conf import settings
import secrets


class CabecerasSeguridadMiddleware:
    """
    Agrega a todas las respuestas las cabeceras que Django no pone por sí solo.

    - Content-Security-Policy: el navegador solo ejecuta scripts y estilos
      servidos por nuestro propio dominio. Un texto inyectado en una plantilla
      no puede cargar un script externo ni incrustar un video o un iframe.
    - Permissions-Policy: la página no puede pedir cámara, micrófono ni ubicación.
    - Cache-Control en páginas autenticadas: el navegador no guarda copias de
      páginas con datos personales.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = getattr(settings, "CONTENT_SECURITY_POLICY", "")

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(24)
        response = self.get_response(request)
        if self.csp:
            csp = self.csp
            if request.path.startswith("/panel/agenda/") or request.path == "/cotizacion/":
                csp = csp.replace("style-src 'self'", "style-src 'self' 'nonce-" + request.csp_nonce + "'")
                # FullCalendar incluye su fuente de iconos dentro del archivo local.
                if "font-src" not in csp:
                    csp = csp.rstrip("; ") + "; font-src 'self' data:;"
            response.setdefault("Content-Security-Policy", csp)
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            response["Cache-Control"] = "no-store"
        return response

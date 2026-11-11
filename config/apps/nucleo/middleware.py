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


class LimiteArchivosMiddleware:
    """Máximo de archivos por envío: 3 en general y 10 solo al agregar fotos al portafolio.
    DATA_UPLOAD_MAX_NUMBER_FILES fija el tope absoluto (10) al leer el formulario."""
    GENERAL = 3
    POR_VISTA = {"nucleo:portafolio_nuevo": 10}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, vista, args, kwargs):
        # Va antes de CsrfViewMiddleware: aquí se lee el formulario por primera vez, así
        # un envío con demasiados archivos recibe un mensaje claro y no una página de error.
        if request.method != "POST" or not request.content_type.startswith("multipart/"):
            return None
        from django.contrib import messages
        from django.core.exceptions import TooManyFilesSent
        from django.http import HttpResponseBadRequest
        from django.shortcuts import redirect
        nombre = request.resolver_match.view_name if request.resolver_match else ""
        limite = self.POR_VISTA.get(nombre, self.GENERAL)
        try:
            cantidad = sum(len(lista) for _, lista in request.FILES.lists())
        except TooManyFilesSent:
            cantidad = limite + 1
        if cantidad <= limite:
            return None
        aviso = f"Puedes subir hasta {limite} fotografías a la vez. Elige menos archivos e inténtalo de nuevo."
        if nombre in self.POR_VISTA and hasattr(request, "_messages"):
            messages.error(request, aviso)
            return redirect(request.path)
        return HttpResponseBadRequest(aviso)

"""Páginas de error propias: nunca muestran trazas ni detalles internos."""
from django.shortcuts import render
from django.conf import settings
from django.http import Http404


def _error(request, codigo, titulo, texto):
    return render(request, "error.html",
                  {"codigo": codigo, "titulo": titulo, "texto": texto}, status=codigo)


def error_400(request, exception=None):
    return _error(request, 400, "Solicitud no válida", "La solicitud no se pudo procesar.")


def error_403(request, exception=None):
    return _error(request, 403, "Acceso denegado", "No tienes permiso para ver esta página.")


def error_404(request, exception=None):
    return _error(request, 404, "Página no encontrada", "La dirección no existe o el enlace caducó.")


def error_500(request):
    return _error(request, 500, "Error interno", "Ocurrió un problema. Intenta nuevamente en unos minutos.")


def csrf_failure(request, reason=""):
    return _error(request, 403, "No pudimos validar el envío", "Tu sesión o el formulario pudo haber caducado. Abre nuevamente la página antes de volver a enviar los datos.")


def vista_previa(request, codigo):
    if not settings.DEBUG or codigo not in (400, 403, 404, 500, 503):
        raise Http404
    if codigo == 503:
        return _error(request, 503, "Servicio no disponible", "No pudimos conectar con el servicio. Conserva tus datos y vuelve a intentar en unos minutos.")
    return {400:error_400,403:error_403,404:error_404,500:error_500}[codigo](request)

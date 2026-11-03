"""Páginas de error propias: nunca muestran trazas ni detalles internos."""
from django.shortcuts import render


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

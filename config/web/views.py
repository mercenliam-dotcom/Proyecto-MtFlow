import logging

from django.conf import settings
from django.db import DatabaseError, transaction
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.clasificacion.catalogo import ESTILOS
from apps.clasificacion.cliente_ml import clasificar
from apps.clasificacion.views import _miniatura_data_uri
from .forms import CotizacionForm
from .limites import admitir_cotizacion
from .recepcion import recibir_una_vez, TatuadoraNoDisponible

log = logging.getLogger("mtflow.seguridad")


def portafolio(request):
    descripciones = ["La fuerza del negro y el espacio", "Historias que se vuelven tinta", "Trazos orgánicos y digitales", "Palabras con identidad", "Sutileza en cada línea", "Ritmo, simetría y composición", "Formas que siguen el cuerpo"]
    trabajos = [{"estilo": nombre, "descripcion": descripcion} for nombre, descripcion in zip(
        (nombre for codigo, nombre in ESTILOS.items() if codigo != "E-99"), descripciones)]
    return render(request, "web/portafolio.html", {"trabajos": trabajos})


def horarios(request):
    return render(request, "web/horarios.html")


@transaction.non_atomic_requests
@never_cache
@require_http_methods(["GET", "POST"])
def cotizacion(request):
    contexto = {}
    estado = 200
    if request.method == "POST" and not admitir_cotizacion(request):
        contexto["limite"] = True
        form = CotizacionForm()
        estado = 429
    else:
        form = CotizacionForm(request.POST if request.method == "POST" else None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            datos = form.cleaned_data
            try:
                recepcion = recibir_una_vez(datos, form.validada, datos["envio"], clasificar)
            except TatuadoraNoDisponible:
                form.add_error("tatuadora", "La tatuadora seleccionada no está habilitada. Revisa las opciones antes de enviar.")
                estado = 400
            except (OSError, DatabaseError):
                log.error("Recepción no completada por un error de almacenamiento o base de datos")
                form.add_error(None, "No pudimos guardar tu propuesta. Inténtalo nuevamente con la misma página; no confirmaremos la recepción hasta guardarla completa.")
                estado = 503
            else:
                contexto.update(referencia=recepcion.postulacion.referencia, repetida=recepcion.repetida)
                if not recepcion.repetida:
                    form.validada.archivo.seek(0)
                    contexto.update(
                        estimacion=recepcion.estimacion,
                        miniatura=_miniatura_data_uri(form.validada.archivo.read()),
                        resumen={clave: datos[clave] for clave in ("nombre", "email", "telefono", "idea")},
                        error_ml=recepcion.postulacion.estado_ml == "NO_DISPONIBLE",
                    )
                    contexto["resumen"]["tatuadora"] = datos["tatuadora"].nombre_publico
                    resultado = recepcion.resultado_ml
                    if resultado:
                        contexto.update(
                            estilo=ESTILOS[resultado.estilo_sugerido],
                            simulado=resultado.version_modelo.startswith("simulado"),
                            revision_ml=resultado.estilo_sugerido == "E-99" or resultado.confianza_maxima < settings.UMBRAL_REVISION,
                        )
        elif request.method == "POST":
            estado = 400
    contexto["form"] = form
    respuesta = render(request, "web/cotizacion.html", contexto, status=estado)
    if estado == 429:
        respuesta["Retry-After"] = str(settings.COTIZACION_VENTANA_SEGUNDOS)
    return respuesta

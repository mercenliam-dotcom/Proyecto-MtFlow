from django.shortcuts import render
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.clasificacion.catalogo import ESTILOS
from apps.clasificacion.cliente_ml import clasificar, ServicioMLNoDisponible
from apps.clasificacion.views import _miniatura_data_uri
from .forms import CotizacionForm
from .precios import estimar
from .limites import admitir_cotizacion


def portafolio(request):
    descripciones = ["La fuerza del negro y el espacio", "Historias que se vuelven tinta", "Trazos orgánicos y digitales", "Palabras con identidad", "Sutileza en cada línea", "Ritmo, simetría y composición", "Formas que siguen el cuerpo"]
    trabajos = [{"estilo": nombre, "descripcion": descripcion} for nombre, descripcion in zip(
        (nombre for codigo, nombre in ESTILOS.items() if codigo != "E-99"), descripciones)]

    return render(request, "web/portafolio.html", {"trabajos": trabajos})

def horarios(request):
    return render(request, "web/horarios.html")

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
            contenido = form.validada.archivo.read()
            contexto.update(estimacion=estimar(datos), miniatura=_miniatura_data_uri(contenido),
                            resumen={"nombre": datos["nombre"], "email": datos["email"], "telefono": datos["telefono"],
                                     "idea": datos["idea"], "tatuadora": dict(form.fields["tatuadora"].choices)[datos["tatuadora"]]})
            if datos["analizar"]:
                try:
                    resultado = clasificar(contenido, form.validada.archivo.name,
                                           "image/jpeg" if form.validada.formato == "JPEG" else "image/png")
                except ServicioMLNoDisponible:
                    contexto["error_ml"] = True
                else:
                    contexto["estilo"] = ESTILOS[resultado.estilo_sugerido]
                    contexto["simulado"] = resultado.version_modelo.startswith("simulado")
                    contexto["revision_ml"] = resultado.estilo_sugerido == "E-99" or resultado.confianza_maxima < settings.UMBRAL_REVISION
        elif request.method == "POST":
            estado = 400
    contexto["form"] = form
    respuesta = render(request, "web/cotizacion.html", contexto, status=estado)
    if estado == 429:
        respuesta["Retry-After"] = str(settings.COTIZACION_VENTANA_SEGUNDOS)
    return respuesta

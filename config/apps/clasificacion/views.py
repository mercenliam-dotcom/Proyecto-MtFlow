import base64
import io

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from PIL import Image

from .catalogo import ESTILOS, recomendar
from .cliente_ml import ServicioMLNoDisponible, clasificar
from .forms import ImagenReferenciaForm


def _miniatura_data_uri(contenido: bytes) -> str:
    """Miniatura en memoria para mostrar en pantalla, sin guardar el archivo."""
    img = Image.open(io.BytesIO(contenido))
    img.thumbnail((480, 480))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@login_required
@require_http_methods(["GET", "POST"])
def probar(request):
    """
    Prueba del identificador de estilos: valida la imagen, la envía al
    servicio de inferencia y muestra el vector de confianzas con la
    recomendación. En esta versión NO se guarda nada (no hay datos de
    clientes involucrados); el guardado llega con el formulario de postulación.
    """
    form = ImagenReferenciaForm(request.POST or None, request.FILES or None)
    contexto = {"form": form}
    if request.method == "POST" and form.is_valid():
        v = form.validada
        contenido = v.archivo.read()
        tipo = "image/jpeg" if v.formato == "JPEG" else "image/png"
        contexto["imagen"] = v
        contexto["miniatura"] = _miniatura_data_uri(contenido)
        try:
            resultado = clasificar(contenido, v.archivo.name, tipo)
        except ServicioMLNoDisponible:
            contexto["error_servicio"] = True
        else:
            contexto["resultado"] = resultado
            contexto["simulado"] = resultado.version_modelo.startswith("simulado")
            # Si las confianzas suman menos de 1, el modelo omitió los estilos
            # bajo su umbral: esos se muestran como "< 40 %", no como 0 %.
            parcial = sum(resultado.confianzas.values()) < 0.99
            contexto["filas"] = [
                {"codigo": c, "nombre": ESTILOS[c], "porcentaje": round(p * 100, 1),
                 "no_informado": parcial and p == 0}
                for c, p in resultado.ordenadas()
            ]
            contexto["recomendacion"] = recomendar(
                resultado.estilo_sugerido, resultado.confianza_maxima
            )
            contexto["estilo_nombre"] = ESTILOS[resultado.estilo_sugerido]
            contexto["confianza_pct"] = round(resultado.confianza_maxima * 100, 1)
    return render(request, "clasificacion/probar.html", contexto)

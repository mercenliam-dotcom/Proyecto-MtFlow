import logging

from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.clasificacion.catalogo import ESTILOS
from apps.clasificacion.cliente_ml import clasificar, ServicioMLNoDisponible
from apps.clasificacion.forms import ImagenReferenciaForm
from apps.clasificacion.views import _miniatura_data_uri
from .forms import CotizacionForm
from .limites import admitir_cotizacion, admitir_analisis
from .recepcion import recibir_una_vez, TatuadoraNoDisponible, EnvioAjeno

log = logging.getLogger("mtflow.seguridad")


@transaction.non_atomic_requests
@never_cache
@require_http_methods(["POST"])
def analizar_referencia(request):
    """Vista previa pública: solo procesa la imagen y no guarda propuestas."""
    if not admitir_analisis(request):
        respuesta = JsonResponse({"error": "Has analizado varias imágenes. Espera unos minutos antes de volver a intentarlo."}, status=429)
        respuesta["Retry-After"] = str(settings.ANALISIS_VENTANA_SEGUNDOS)
        return respuesta
    form = ImagenReferenciaForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": " ".join(str(error) for errores in form.errors.values() for error in errores)}, status=400)
    validada = form.validada
    try:
        resultado = clasificar(validada.archivo.read(), validada.archivo.name,
                               "image/jpeg" if validada.formato == "JPEG" else "image/png")
    except ServicioMLNoDisponible:
        return JsonResponse({"error": "El análisis no está disponible en este momento. Puedes reintentarlo o enviar tu propuesta para revisión."}, status=503)
    return JsonResponse({
        "estilo_sugerido": resultado.estilo_sugerido,
        "nombre": ESTILOS[resultado.estilo_sugerido],
        "simulado": resultado.version_modelo.startswith("simulado"),
        "motivo_abstencion": resultado.motivo_abstencion,
    })


DESCRIPCIONES_ESTILO = {
    "Alto contraste": "La fuerza del negro y el espacio", "Anime": "Historias que se vuelven tinta",
    "Cibersigilismo": "Trazos orgánicos y digitales", "Lettering": "Palabras con identidad",
    "Línea fina": "Sutileza en cada línea", "Ornamentos": "Ritmo, simetría y composición",
    "Tribal / Neotribal": "Formas que siguen el cuerpo", "El estudio": "Nuestro espacio y el día a día",
}
ESTUDIO = "El estudio"  # fotos sin estilo: el estudio, el equipo, el espacio
FOTOS_POR_PAGINA = 24


def _publicados():
    from .models import TrabajoPortafolio
    return (TrabajoPortafolio.objects.filter(
        visible=True, autorizacion_publicacion=True, tatuadora__activa=True,
        tatuadora__usuario__is_active=True, tatuadora__usuario__es_tatuadora=True)
        .select_related("estilo", "tatuadora__usuario").order_by("-publicado_en", "-pk"))


def _grupos(publicados):
    """Un grupo por estilo del catálogo (aunque aún no tenga fotos) y otro para el estudio."""
    from django.db.models import Count
    from django.utils.text import slugify
    cantidades = dict(publicados.order_by().values_list("estilo__nombre").annotate(n=Count("pk")))
    nombres = [n for c, n in ESTILOS.items() if c != "E-99"]
    nombres += sorted(n for n in cantidades if n and n not in nombres)  # p. ej. «Fuera de catálogo»
    nombres.append(ESTUDIO)
    grupos = []
    for nombre in nombres:
        cantidad = cantidades.get(None if nombre == ESTUDIO else nombre, 0)
        filtro = {"estilo__isnull": True} if nombre == ESTUDIO else {"estilo__nombre": nombre}
        grupos.append({"slug": slugify(nombre), "nombre": nombre, "descripcion": DESCRIPCIONES_ESTILO.get(nombre, ""),
                       "cantidad": cantidad, "portada": publicados.filter(**filtro).first() if cantidad else None,
                       "filtro": filtro})
    # Sin fotos del estudio no se muestra una tarjeta vacía para él.
    return [g for g in grupos if g["nombre"] != ESTUDIO or g["cantidad"]]


def portafolio(request):
    publicados = _publicados()
    grupos = _grupos(publicados)
    return render(request, "web/portafolio.html", {
        "grupos": grupos, "total": sum(g["cantidad"] for g in grupos),
        "destacados": publicados.filter(en_carrusel=True)[:12],
    })


def catalogo(request):
    """Todas las fotos publicadas, filtrables por estilo y paginadas."""
    from django.core.paginator import Paginator
    publicados = _publicados()
    grupos = _grupos(publicados)
    elegido = next((g for g in grupos if g["slug"] == request.GET.get("estilo")), None)
    fotos = publicados.filter(**elegido["filtro"]) if elegido else publicados
    pagina = Paginator(fotos, FOTOS_POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(request, "web/catalogo.html", {
        "grupos": [g for g in grupos if g["cantidad"]], "elegido": elegido, "pagina": pagina,
        "total": sum(g["cantidad"] for g in grupos),
    })


def horarios(request):
    return redirect("nucleo:agenda")


@transaction.non_atomic_requests
@never_cache
@require_http_methods(["GET", "POST"])
def cotizacion(request):
    contexto = {}
    estado = 200
    cuenta = request.user if request.user.is_authenticated and request.user.es_cliente else None
    inicial = {}
    if cuenta:
        inicial = {"nombre": cuenta.nombre, "primer_apellido": cuenta.apellido, "email": cuenta.email}
        perfil = getattr(cuenta, "perfil_cliente", None)
        if perfil:
            inicial.update({campo: getattr(perfil, campo) for campo in ("segundo_apellido", "telefono", "canal_preferido", "usuario_social")})
    if request.method == "POST" and not admitir_cotizacion(request):
        contexto["limite"] = True
        form = CotizacionForm(initial=inicial, cuenta=cuenta)
        estado = 429
    else:
        form = CotizacionForm(request.POST if request.method == "POST" else None, request.FILES or None, initial=inicial, cuenta=cuenta)
        if request.method == "POST" and form.is_valid():
            datos = form.cleaned_data
            try:
                recepcion = recibir_una_vez(datos, form.validada, datos["envio"], clasificar, cuenta_cliente=cuenta)
            except EnvioAjeno:
                form.add_error(None, "Este formulario ya fue enviado desde otra sesión. Abre una nueva cotización para continuar.")
                estado = 409
            except TatuadoraNoDisponible:
                form.add_error("tatuadora", "La tatuadora seleccionada no está habilitada. Revisa las opciones antes de enviar.")
                estado = 400
            except (OSError, DatabaseError):
                log.error("Recepción no completada por un error de almacenamiento o base de datos")
                form.add_error(None, "No pudimos guardar tu propuesta. Inténtalo nuevamente con la misma página; no confirmaremos la recepción hasta guardarla completa.")
                estado = 503
            else:
                contexto.update(referencia=recepcion.postulacion.referencia, codigo=recepcion.postulacion.codigo, repetida=recepcion.repetida)
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
                            motivo_abstencion=resultado.motivo_abstencion,
                        )
        elif request.method == "POST":
            estado = 400
    contexto["form"] = form
    if cuenta:
        canal = form["canal_preferido"].value() or "correo"
        contexto["datos_cuenta"] = {
            "nombre": " ".join(filter(None, (form[c].value() for c in ("nombre", "primer_apellido", "segundo_apellido")))),
            "email": form["email"].value(), "telefono": form["telefono"].value(),
            "canal": dict(form.fields["canal_preferido"].choices).get(canal, "Correo"),
            "usuario_social": form["usuario_social"].value() if canal in ("instagram", "tiktok") else "",
        }
    respuesta = render(request, "web/cotizacion.html", contexto, status=estado)
    if estado == 429:
        respuesta["Retry-After"] = str(settings.COTIZACION_VENTANA_SEGUNDOS)
    return respuesta

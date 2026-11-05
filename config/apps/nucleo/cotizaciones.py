"""Consulta privada de las propuestas dirigidas a la tatuadora autenticada."""
from decimal import Decimal
from pathlib import Path
import re

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido, solo_admin
from .forms_cotizaciones import FiltrosEquipo
from apps.nucleo.firmas import url_archivo
from web.models import Imagen, Postulacion, Prediccion


def propias(user):
    # También los administradores ven solo sus propuestas en «Mis cotizaciones».
    # La gestión global se consulta en la bandeja del equipo, exclusiva de ADMIN.
    return Postulacion.objects.filter(tatuadora__usuario=user).select_related("cliente", "tatuadora__usuario")


def nombre_estado(estado):
    return estado.replace("_", " ").capitalize()


def precio_legible(propuesta):
    if propuesta.precio_sugerido is None:
        return "Revisión personalizada"
    return "$" + f"{propuesta.precio_sugerido:,}".replace(",", ".") + " CLP"


@rol_requerido(Rol.ADMIN, Rol.USUARIO)
@never_cache
@require_GET
def lista(request):
    return _lista(request, propias(request.user))


@solo_admin
@never_cache
@require_GET
def equipo(request):
    propuestas = Postulacion.objects.select_related("cliente", "tatuadora__usuario")
    return _lista(request, propuestas, es_equipo=True)


def _lista(request, propuestas, es_equipo=False):
    estados = [(estado, nombre_estado(estado)) for estado in propuestas.order_by("estado").values_list("estado", flat=True).distinct()]
    estado = request.GET.get("estado", "")
    if estado not in {valor for valor, _ in estados}:
        estado = ""
    total = propuestas.count()
    form = None
    status = 200
    if es_equipo:
        form = FiltrosEquipo(request.GET or None, propuestas=propuestas, estados=estados)
        if form.is_bound:
            if form.is_valid():
                propuestas = form.filtrar(propuestas)
            else:
                propuestas = propuestas.none()
                status = 400
    elif estado:
        propuestas = propuestas.filter(estado=estado)
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    pagina = Paginator(propuestas.order_by("-creada_en", "-pk"), 20).get_page(request.GET.get("pagina"))
    for propuesta in pagina:
        propuesta.estado_legible = nombre_estado(propuesta.estado)
        propuesta.precio_legible = precio_legible(propuesta)
    return render(request, "cotizaciones/lista.html", {
        "pagina": pagina, "total": total, "estados": estados, "estado": estado,
        "es_equipo": es_equipo, "form_filtros": form, "filtros_query": filtros.urlencode(),
        "titulo": "Cotizaciones del equipo" if es_equipo else "Mis cotizaciones",
        "detalle_nombre": "nucleo:equipo_cotizacion_detalle" if es_equipo else "nucleo:cotizacion_detalle",
    }, status=status)


@rol_requerido(Rol.ADMIN, Rol.USUARIO)
@never_cache
@require_GET
def detalle(request, referencia):
    return _detalle(request, referencia, propias(request.user))


@solo_admin
@never_cache
@require_GET
def equipo_detalle(request, referencia):
    return _detalle(request, referencia, Postulacion.objects.select_related("cliente", "tatuadora__usuario"), es_equipo=True)


def _detalle(request, referencia, propuestas, es_equipo=False):
    propuesta = get_object_or_404(propuestas, referencia=referencia)
    propuesta.precio_legible = precio_legible(propuesta)
    # Las propuestas de la rama SQL consolidan estos campos en descripción.
    # Se presentan como información de la propuesta, sin exponer etiquetas internas.
    datos = re.fullmatch(r"IDEA: (.*) \| COLOR: (negro|color) \| DETALLE: (normal|alto) \| COVER-UP: (True|False)", propuesta.descripcion, re.S)
    propuesta.idea_legible = datos[1] if datos else propuesta.descripcion
    opciones = None
    if datos:
        opciones = {
            "color": "Negro y grises" if datos[2] == "negro" else "Con color",
            "detalle": "Simple o intermedio" if datos[3] == "normal" else "Alto",
            "cobertura": "Sí" if datos[4] == "True" else "No",
        }
    predicciones = Prediccion.objects.select_related("estilo_sugerido").prefetch_related(
        "confianzaestilo_set__estilo",
    ).order_by("-generada_en", "-pk")
    imagenes = Imagen.objects.filter(postulacion=propuesta).order_by("orden", "pk").prefetch_related(
        Prefetch("prediccion_set", queryset=predicciones, to_attr="predicciones"),
    )
    referencias = []
    raiz = Path(settings.MEDIA_ROOT).resolve()
    for imagen in imagenes:
        ruta = (raiz / imagen.url).resolve()
        disponible = raiz in ruta.parents and ruta.is_file() and ruta.suffix.lower() in (".jpg", ".jpeg", ".png")
        prediccion = imagen.predicciones[0] if imagen.predicciones else None
        filas = []
        simulado = False
        confianza = None
        if prediccion:
            simulado = prediccion.version_modelo.startswith("simulado")
            confianzas = list(prediccion.confianzaestilo_set.all())
            parcial = not simulado and sum(f.confianza for f in confianzas if f.estilo.codigo != "E-99") < Decimal(".99")
            for fila in sorted(confianzas, key=lambda f: (-f.confianza, f.estilo.codigo)):
                if fila.estilo.codigo != "E-99":
                    filas.append({
                        "nombre": fila.estilo.nombre,
                        "porcentaje": (fila.confianza * 100).quantize(Decimal(".1")),
                        "omitida": parcial and fila.confianza == 0,
                    })
            if prediccion.estilo_sugerido.codigo != "E-99":
                confianza = (prediccion.confianza_maxima * 100).quantize(Decimal(".1"))
        referencias.append({
            "imagen": imagen, "url": url_archivo(imagen.url) if disponible else None,
            "prediccion": prediccion, "filas": filas, "simulado": simulado, "confianza": confianza,
        })
    return render(request, "cotizaciones/detalle.html", {
        "propuesta": propuesta, "referencias": referencias,
        "estado_legible": nombre_estado(propuesta.estado),
        "opciones": opciones, "es_equipo": es_equipo,
    })

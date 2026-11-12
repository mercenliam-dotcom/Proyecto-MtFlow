"""Consulta privada de las propuestas dirigidas a la tatuadora autenticada."""
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Prefetch, OuterRef, Subquery, F
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido, solo_admin
from .forms_cotizaciones import FiltrosEquipo
from .forms_agenda import GestionForm
from apps.nucleo.firmas import url_archivo
from web.models import Imagen, Postulacion, Prediccion


def propias(user):
    # También los administradores ven solo sus propuestas en «Mis cotizaciones».
    # La gestión global se consulta en la bandeja del equipo, exclusiva de ADMIN.
    return Postulacion.objects.filter(tatuadora__usuario=user).select_related("contacto", "tatuadora__usuario")


def nombre_estado(estado):
    return estado.replace("_", " ").capitalize()


def precio_legible(propuesta):
    if propuesta.precio_sugerido is None:
        return "Revisión personalizada"
    return "$" + f"{propuesta.precio_sugerido:,}".replace(",", ".") + " CLP"


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def lista(request):
    if request.GET.get("bandeja") in ("aceptadas", "rechazadas", "terminadas", "agendadas"):
        return redirect(reverse("nucleo:registro") + "?bandeja=" + request.GET["bandeja"])
    return _lista(request, propias(request.user))


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def registro(request):
    return _lista(request, propias(request.user), es_registro=True)


@solo_admin
@never_cache
@require_GET
def equipo(request):
    propuestas = Postulacion.objects.select_related("contacto", "tatuadora__usuario")
    return _lista(request, propuestas, es_equipo=True)


def _lista(request, propuestas, es_equipo=False, es_registro=False):
    resumen = None
    bandeja = request.GET.get("bandeja", "")
    if not es_equipo:
        if es_registro:
            propuestas = propuestas.filter(estado__in=["ACEPTADA", "RESERVADA", "REALIZADA", "RECHAZADA"])
            resumen = {"aceptadas": propuestas.exclude(estado="RECHAZADA").count(), "rechazadas": propuestas.filter(estado="RECHAZADA").count()}
        else:
            propuestas = propuestas.filter(estado__in=["RECIBIDA", "EN_REVISION"])
    estados = [(estado, nombre_estado(estado)) for estado in propuestas.order_by("estado").values_list("estado", flat=True).distinct()]
    estado = request.GET.get("estado", "")
    if estado not in {valor for valor, _ in estados}:
        estado = ""
    total = propuestas.count()
    grupos = {"aceptadas": ["ACEPTADA", "RESERVADA", "REALIZADA"], "por_agendar": ["ACEPTADA"], "agendadas": ["RESERVADA"], "rechazadas": ["RECHAZADA"], "terminadas": ["REALIZADA"]}
    if es_registro and bandeja in grupos:
        propuestas = propuestas.filter(estado__in=grupos[bandeja])
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
    ultima = Prediccion.objects.filter(imagen__postulacion=OuterRef("pk"), imagen__es_principal=True).order_by("-generada_en", "-pk")
    propuestas = propuestas.annotate(confianza_resumen=Subquery(ultima.values("confianza_maxima")[:1]), modelo_resumen=Subquery(ultima.values("version_modelo")[:1]), estilo_resumen=Subquery(ultima.values("estilo_sugerido__codigo")[:1]))
    orden = ["-creada_en", "-pk"]
    if request.GET.get("orden") == "confianza":
        # Los resultados simulados nunca deben ganar prioridad frente a clientes reales.
        from django.db.models import Case, When, DecimalField
        propuestas = propuestas.annotate(prioridad=Case(When(modelo_resumen__startswith="simulado", then=None), default=F("confianza_resumen"), output_field=DecimalField()))
        orden = [F("prioridad").desc(nulls_last=True), "creada_en", "pk"]
    pagina = Paginator(propuestas.order_by(*orden), 20).get_page(request.GET.get("pagina"))
    for propuesta in pagina:
        propuesta.estado_legible = propuesta.estado_comercial
        propuesta.precio_legible = precio_legible(propuesta)
        propuesta.confianza_legible = "Sin análisis"
        if propuesta.modelo_resumen:
            propuesta.confianza_legible = "Simulado" if propuesta.modelo_resumen.startswith("simulado") else f"{propuesta.confianza_resumen * 100:.1f} %" + (" · revisar" if propuesta.estilo_resumen == "E-99" else "")
    return render(request, "cotizaciones/lista.html", {
        "pagina": pagina, "total": total, "estados": estados, "estado": estado,
        "es_equipo": es_equipo, "form_filtros": form, "filtros_query": filtros.urlencode(),
        "titulo": "Cotizaciones del equipo" if es_equipo else "Registro" if es_registro else "Solicitudes pendientes",
        "es_registro": es_registro, "resumen_registro": resumen, "bandeja": bandeja,
        "detalle_nombre": "nucleo:equipo_cotizacion_detalle" if es_equipo else "nucleo:cotizacion_detalle",
        "resumen_nombre": "nucleo:equipo_resumen" if es_equipo else "nucleo:cotizacion_resumen",
    }, status=status)


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def detalle(request, referencia):
    from .avisos import marcar_vista
    marcar_vista(request.user, referencia)
    return _detalle(request, referencia, propias(request.user))


@solo_admin
@never_cache
@require_GET
def equipo_detalle(request, referencia):
    return _detalle(request, referencia, Postulacion.objects.select_related("contacto", "tatuadora__usuario"), es_equipo=True)


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def resumen(request, referencia):
    return _resumen(request, referencia, propias(request.user))


@solo_admin
@never_cache
@require_GET
def equipo_resumen(request, referencia):
    return _resumen(request, referencia, Postulacion.objects.select_related("contacto", "tatuadora__usuario"), es_equipo=True)


def _resumen(request, referencia, propuestas, es_equipo=False):
    p=get_object_or_404(propuestas,referencia=referencia)
    im=p.imagen_set.filter(es_principal=True).first()
    url=None
    if im:
        raiz=Path(settings.MEDIA_ROOT).resolve()
        ruta=(raiz/im.url).resolve()
        if raiz in ruta.parents and ruta.is_file() and ruta.suffix.lower() in (".jpg",".jpeg",".png"):
            url=url_archivo(im.url)
    respuesta=render(request,"cotizaciones/resumen.html",{
        "propuesta":p,"estado_legible":p.estado_comercial,"precio_legible":precio_legible(p),"imagen_url":url,
        "detalle_nombre":"nucleo:equipo_cotizacion_detalle" if es_equipo else "nucleo:cotizacion_detalle",
        "puede_evaluar":p.tatuadora.usuario_id==request.user.pk and request.user.es_tatuadora and p.tatuadora.activa and p.estado in ("RECIBIDA","EN_REVISION"),
    })
    respuesta["X-MTFlow-Fragment"]="resumen-solicitud"
    return respuesta


def _detalle(request, referencia, propuestas, es_equipo=False, gestion_form=None, status=200):
    propuesta = get_object_or_404(propuestas, referencia=referencia)
    propuesta.precio_legible = precio_legible(propuesta)
    propuesta.idea_legible = propuesta.descripcion
    opciones = {
        "color": propuesta.get_color_display() if propuesta.color else "No registrado",
        "detalle": propuesta.get_nivel_detalle_display() if propuesta.nivel_detalle else "No registrado",
        "cobertura": "No registrado" if propuesta.cobertura is None else "Sí" if propuesta.cobertura else "No",
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
            parcial = prediccion.version_modelo.startswith("roboflow") and sum(f.confianza for f in confianzas if f.estilo.codigo != "E-99") < Decimal(".99")
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
            "maxima": (prediccion.confianza_maxima * 100).quantize(Decimal(".1")) if prediccion else None,
            "umbral": (prediccion.umbral_confianza * 100).quantize(Decimal("1")) if prediccion and prediccion.umbral_confianza is not None else None,
        })
    from .flujo import RevisionForm
    principal = next((r for r in referencias if r["imagen"].es_principal and r["prediccion"]), None)
    sugerido = principal["prediccion"].estilo_sugerido if principal else None
    revision_form = RevisionForm(initial={"version": propuesta.actualizada_en.isoformat(), "estilo": sugerido.pk if sugerido and sugerido.codigo != "E-99" else None})
    from .flujo import estado_cierre
    from .operaciones_agenda import _clp
    cierre = estado_cierre(propuesta)
    return render(request, "cotizaciones/detalle.html", {
        "revision_form": revision_form, "estilo_sugerido": sugerido if sugerido and sugerido.codigo != "E-99" else None,
        "propuesta": propuesta, "referencias": referencias, "revision": propuesta.imagen_set.filter(es_principal=True).select_related("etiquetaconsolidada__estilo").first(),
        "estado_legible": propuesta.estado_comercial,
        "pendiente_decision": propuesta.estado in ("RECIBIDA", "EN_REVISION"),
        "puede_agendar": propuesta.estado in ("ACEPTADA", "RESERVADA") and not propuesta.sesiones.filter(estado="RESERVADA").exists() and propuesta.total_cobrado > 0 and propuesta.total_cobrado >= (propuesta.abono_solicitado or 0) and propuesta.destino_abono not in ("RETENIDO", "DEVOLVER"),
        "opciones": opciones, "es_equipo": es_equipo,
        "gestion_form": gestion_form if gestion_form is not None else GestionForm(solicitud=propuesta),
        "puede_gestionar": propuesta.tatuadora.usuario_id == request.user.pk and request.user.es_tatuadora and propuesta.tatuadora.activa,
        "sesiones": propuesta.sesiones.all(), "eventos": propuesta.eventos.select_related("actor")[:50],
        "tiene_inasistencias": propuesta.sesiones.filter(estado="NO_ASISTIO").exists(),
        "cierre_disponible": cierre["sesiones_listas"],
        # Terminar exige el pago final confirmado: sin saldo pendiente.
        "puede_terminar": cierre["puede_terminar"],
        "sesiones_por_marcar": cierre["por_marcar"],
        "saldo_texto": _clp(propuesta.saldo_pendiente),
        # Tras registrar el pago final se pregunta si terminar ahora o después.
        "ofrecer_cierre": cierre["puede_terminar"] and request.GET.get("cerrar") == "1",
        "cierre_version": propuesta.actualizada_en.isoformat(),
    }, status=status)

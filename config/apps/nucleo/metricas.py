from collections import Counter, defaultdict
from datetime import timedelta
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import Postulacion, BloqueHorario
from .agenda import profesional


def calcular(artista, inicio, fin):
    # Una fila por solicitud: unir sesiones y cobros multiplicaría los importes.
    solicitudes = Postulacion.objects.filter(tatuadora=artista).select_related("contacto").prefetch_related("imagen_set__etiquetaconsolidada__estilo", "movimientos")
    estados, zonas, estilos, rechazados = Counter(), Counter(), Counter(), Counter()
    ingresos = defaultdict(int)
    totales = {"recibido": 0, "abonos": 0, "solicitado": 0, "saldo": 0, "retencion": 0}
    recibidas = 0
    for p in solicitudes:
        imagen = next((i for i in p.imagen_set.all() if i.es_principal), None)
        etiqueta = getattr(imagen, "etiquetaconsolidada", None) if imagen else None
        estilo = etiqueta.estilo.nombre if etiqueta else "Sin revisión humana"
        movimientos = list(p.movimientos.all())
        abono = (p.monto_abono or 0) if p.abono_verificado_en else 0
        neto = abono + sum(m.monto if m.tipo == "PAGO" else -m.monto for m in movimientos)
        totales["recibido"] += neto
        totales["abonos"] += abono
        totales["solicitado"] += p.abono_solicitado or 0
        if p.estado in ("ACEPTADA", "RESERVADA", "REALIZADA") and p.destino_abono != "RETENIDO":
            totales["saldo"] += max(0, (p.precio_final or 0) - neto)
        if p.destino_abono == "RETENIDO":
            totales["retencion"] += min(p.monto_abono or 0, max(0, neto))
        ingresos[estilo] += neto
        if inicio <= timezone.localtime(p.creada_en).date() <= fin:
            recibidas += 1
            estados[p.estado] += 1
            if p.estado == "RECHAZADA":
                rechazados[estilo] += 1
        if p.realizada_en and inicio <= timezone.localtime(p.realizada_en).date() <= fin:
            estilos[estilo] += 1
            zonas[p.zona_cuerpo] += 1
    ausencias = BloqueHorario.objects.filter(tatuadora=artista, estado="NO_ASISTIO", fecha__range=(inicio, fin)).count()
    return {"totales": totales, "recibidas": recibidas, "estados": sorted(estados.items()), "zonas": zonas.most_common(), "estilos": estilos.most_common(), "rechazados": rechazados.most_common(), "ingresos": sorted(ingresos.items()), "ausencias": ausencias}


def serie_semanal(artista, hoy, semanas=12):
    """Solicitudes recibidas y trabajos terminados por semana (lunes a domingo), las últimas N semanas."""
    lunes = hoy - timedelta(days=hoy.weekday())
    inicios = [lunes - timedelta(weeks=n) for n in range(semanas - 1, -1, -1)]
    recibidas, terminados = [0] * semanas, [0] * semanas
    desde = inicios[0]
    for creada, realizada in Postulacion.objects.filter(tatuadora=artista).values_list("creada_en", "realizada_en"):
        for fecha, serie in ((creada, recibidas), (realizada, terminados)):
            if fecha:
                dia = timezone.localtime(fecha).date()
                if desde <= dia <= hoy:
                    serie[(dia - desde).days // 7] += 1
    return {"etiquetas": [f"{d:%d/%m}" for d in inicios], "recibidas": recibidas, "terminados": terminados}


ETAPAS = [("RECIBIDA", "Recibidas"), ("EN_REVISION", "En revisión"), ("ACEPTADA", "Aceptadas"),
          ("RESERVADA", "Agendadas"), ("REALIZADA", "Terminadas"), ("RECHAZADA", "Rechazadas")]


def presentar(c):
    """Solo presentación: nombres legibles y escalas para las barras. No cambia los cálculos."""
    por_estado = dict(c["estados"])
    etapas = [{"codigo": cod, "nombre": nombre, "cantidad": por_estado.get(cod, 0)} for cod, nombre in ETAPAS]
    return {
        "etapas": etapas,
        "etapas_max": max([e["cantidad"] for e in etapas] + [1]),
        "terminados": sum(n for _, n in c["estilos"]),
        "rechazadas": por_estado.get("RECHAZADA", 0),
        "estilos_max": max([n for _, n in c["estilos"]] + [1]),
        "zonas_max": max([n for _, n in c["zonas"]] + [1]),
        "rechazados_max": max([n for _, n in c["rechazados"]] + [1]),
        "ingresos_max": max([m for _, m in c["ingresos"]] + [1]),
    }


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def inicio(request):
    artista = profesional(request)
    hoy = timezone.localdate()
    periodo = "mes" if request.GET.get("periodo") == "mes" else "semana"
    desde = hoy.replace(day=1) if periodo == "mes" else hoy - timedelta(days=hoy.weekday())
    contexto = calcular(artista, desde, hoy)
    contexto.update(desde=desde, hasta=hoy, periodo=periodo)
    contexto.update(presentar(contexto))
    contexto["serie"] = serie = serie_semanal(artista, hoy)
    contexto["serie_filas"] = list(zip(serie["etiquetas"], serie["recibidas"], serie["terminados"]))
    return render(request, "flujo/metricas.html", contexto)

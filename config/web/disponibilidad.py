"""Disponibilidad común a la agenda privada y el calendario público."""
from datetime import datetime, time, timedelta
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import BloqueHorario, HorarioTrabajo, Tatuadora

OCUPADOS = ("RESERVADA", "REALIZADA", "BLOQUEADO", "NO_ASISTIO")

def semana(tatuadora):
    guardados = {h.dia: h for h in HorarioTrabajo.objects.filter(tatuadora=tatuadora)}
    return {
        dia: ((guardados[dia].hora_inicio, guardados[dia].hora_fin) if guardados[dia].activo else None)
        if dia in guardados else ((time(10), time(19)) if dia < 6 else None) for dia in range(7)}

def intervalos_trabajo(tatuadora, fecha, bloques=None, semanal=None):
    if bloques is None:
        bloques = list(BloqueHorario.objects.filter(tatuadora=tatuadora, fecha=fecha).exclude(estado="CANCELADA"))
    excepciones = [(b.hora_inicio, b.hora_fin) for b in bloques if b.tipo == "DISPONIBILIDAD" and b.estado == "DISPONIBLE"]
    if excepciones:
        return sorted(excepciones)
    habitual = (semanal if semanal is not None else semana(tatuadora)).get(fecha.weekday())
    return [habitual] if habitual else []

def libres_del_dia(tatuadora, fecha, bloques=None, semanal=None):
    if bloques is None:
        bloques = list(BloqueHorario.objects.filter(tatuadora=tatuadora, fecha=fecha).exclude(estado="CANCELADA"))
    libres = intervalos_trabajo(tatuadora, fecha, bloques, semanal)
    for b in bloques:
        if b.estado not in OCUPADOS:
            continue
        restantes = []
        for inicio, fin in libres:
            if b.hora_inicio >= fin or b.hora_fin <= inicio:
                restantes.append((inicio, fin))
            else:
                if inicio < b.hora_inicio: restantes.append((inicio, b.hora_inicio))
                if b.hora_fin < fin: restantes.append((b.hora_fin, fin))
        libres = restantes
    return libres

def hora_disponible(tatuadora, fecha, hora):
    return any(inicio <= hora < fin for inicio, fin in libres_del_dia(tatuadora, fecha))

@never_cache
@require_GET
def calendario_publico(request):
    from datetime import date
    try:
        artista_id = int(request.GET.get("tatuadora", ""))
        inicio = date.fromisoformat(request.GET.get("start", "")[:10])
        fin = date.fromisoformat(request.GET.get("end", "")[:10])
        if not timedelta(0) < fin-inicio <= timedelta(days=62): raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Selecciona una tatuadora y un intervalo de hasta 62 días."}, status=400)
    artista = get_object_or_404(Tatuadora, pk=artista_id, activa=True, usuario__is_active=True, usuario__es_tatuadora=True)
    ahora = timezone.localtime()
    inicio = max(inicio, ahora.date())
    por_dia = {}
    for b in BloqueHorario.objects.filter(tatuadora=artista, fecha__gte=inicio, fecha__lt=fin).exclude(estado="CANCELADA"):
        por_dia.setdefault(b.fecha, []).append(b)
    semanal = semana(artista)
    eventos = []
    limites = []
    dia = inicio
    def agregar(fecha, desde, hasta, libre):
        if fecha == ahora.date(): desde = max(desde, ahora.time().replace(tzinfo=None))
        if desde >= hasta: return
        eventos.append({"title": "Disponible" if libre else "No disponible", "start": f"{fecha}T{desde.isoformat()}",
                        "end": f"{fecha}T{hasta.isoformat()}", "extendedProps": {"disponible": libre},
                        "classNames": ["horario-libre" if libre else "horario-ocupado"]})
    while dia < fin:
        bloques = por_dia.get(dia, [])
        trabajo = intervalos_trabajo(artista, dia, bloques, semanal)
        limites.extend(trabajo)
        for desde, hasta in libres_del_dia(artista, dia, bloques, semanal): agregar(dia, desde, hasta, True)
        for b in bloques:
            if b.estado in OCUPADOS:
                for desde, hasta in trabajo:
                    agregar(dia, max(desde,b.hora_inicio), min(hasta,b.hora_fin), False)
        dia += timedelta(days=1)
    return JsonResponse({"eventos": eventos, "ahora": ahora.replace(tzinfo=None).isoformat(),
                         "inicio": min((a for a,b in limites), default=time(10)).isoformat(),
                         "fin": max((b for a,b in limites), default=time(19)).isoformat()})

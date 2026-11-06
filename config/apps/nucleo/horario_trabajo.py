from datetime import time
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError
from django.forms import formset_factory
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import HorarioTrabajo, BloqueHorario
from web.disponibilidad import semana, intervalos_trabajo
from .agenda import profesional
from .operaciones_agenda import bloquear_profesional

class DiaForm(forms.Form):
    dia = forms.IntegerField(min_value=0, max_value=6, widget=forms.HiddenInput)
    activo = forms.BooleanField(required=False, label="Trabajar este día")
    hora_inicio = forms.TimeField(label="Desde", widget=forms.TimeInput(attrs={"type":"time"}, format="%H:%M"))
    hora_fin = forms.TimeField(label="Hasta", widget=forms.TimeInput(attrs={"type":"time"}, format="%H:%M"))
    def clean(self):
        d=super().clean()
        if d.get("hora_inicio") and d.get("hora_fin") and d["hora_inicio"] >= d["hora_fin"]:
            raise ValidationError("El término debe ser posterior al inicio.")
        return d

Dias = formset_factory(DiaForm, extra=0, min_num=7, max_num=7, validate_min=True, validate_max=True, absolute_max=7)

@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def editar(request):
    artista=profesional(request)
    actual=semana(artista)
    inicial=[{"dia":dia,"activo":bool(actual[dia]),"hora_inicio":actual[dia][0] if actual[dia] else time(10),"hora_fin":actual[dia][1] if actual[dia] else time(19)} for dia in range(7)]
    forms_dias=Dias(request.POST if request.method=="POST" else None, initial=inicial)
    error=""
    status=200
    if request.method=="POST":
        status=400
        if forms_dias.is_valid():
            try:
                with transaction.atomic():
                    artista=bloquear_profesional(request.user)
                    datos=forms_dias.cleaned_data
                    if sorted(d["dia"] for d in datos)!=list(range(7)):
                        raise ValidationError("Completa los siete días sin repetirlos.")
                    nueva={d["dia"]:(d["hora_inicio"],d["hora_fin"]) if d["activo"] else None for d in datos}
                    for cita in BloqueHorario.objects.filter(tatuadora=artista, tipo="CITA", estado="RESERVADA", fecha__gte=timezone.localdate()):
                        if not any(a<=cita.hora_inicio and b>=cita.hora_fin for a,b in intervalos_trabajo(artista,cita.fecha,semanal=nueva)):
                            raise ValidationError(f"La sesión del {cita.fecha:%d/%m/%Y} queda fuera del nuevo horario. Reprográmala o define una excepción para esa fecha primero.")
                    for d in datos:
                        dia=d.pop("dia")
                        HorarioTrabajo.objects.update_or_create(tatuadora=artista,dia=dia,defaults=d)
            except (ValidationError, DatabaseError) as exc:
                error=" ".join(exc.messages) if isinstance(exc,ValidationError) else "No se guardó el horario. Recarga y vuelve a intentar."
            else:
                messages.success(request,"Horario de trabajo actualizado. Los clientes verán la nueva disponibilidad.")
                return redirect("nucleo:agenda")
    nombres=[nombre for _,nombre in HorarioTrabajo._meta.get_field("dia").choices]
    return render(request,"agenda/horario_trabajo.html",{"dias":zip(nombres,forms_dias),"formset":forms_dias,"error":error},status=status)

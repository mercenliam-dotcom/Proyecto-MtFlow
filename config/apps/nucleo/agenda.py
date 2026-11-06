from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import BloqueHorario, Postulacion, Tatuadora
from .forms_agenda import BloqueForm, GestionForm
from .operaciones_agenda import guardar_bloque, cerrar_bloque, gestionar


def profesional(request):
    if not request.user.es_tatuadora:
        raise PermissionDenied("La agenda requiere una cuenta habilitada como tatuadora.")
    return get_object_or_404(Tatuadora, usuario=request.user, activa=True)


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def inicio(request):
    artista = profesional(request)
    bloques = BloqueHorario.objects.filter(tatuadora=artista, fecha__gte=timezone.localdate()).exclude(estado="CANCELADA").select_related("sesion__postulacion__contacto")[:100]
    return render(request, "agenda/inicio.html", {"bloques": bloques, "hoy": timezone.localdate().isoformat()})


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def eventos(request):
    artista = profesional(request)
    try:
        inicio = date.fromisoformat(request.GET.get("start", "")[:10])
        fin = date.fromisoformat(request.GET.get("end", "")[:10])
        if not timedelta(0) < fin - inicio <= timedelta(days=100):
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Intervalo de fechas inválido (máximo 100 días)."}, status=400)
    datos = []
    for b in BloqueHorario.objects.filter(tatuadora=artista, fecha__gte=inicio, fecha__lt=fin).exclude(estado="CANCELADA").select_related("sesion__postulacion__contacto"):
        datos.append({"id": str(b.referencia), "title": (str(b.postulacion.contacto) if b.postulacion_id else b.get_tipo_display()) + " · " + b.estado.lower(),
                      "start": f"{b.fecha}T{b.hora_inicio}", "end": f"{b.fecha}T{b.hora_fin}",
                      "url": reverse("nucleo:agenda_editar", args=[b.referencia]),
                      "classNames": ["agenda-" + b.tipo.lower()]})
    return JsonResponse(datos, safe=False)


@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def editar(request, referencia=None):
    artista = profesional(request)
    bloque = get_object_or_404(BloqueHorario, referencia=referencia, tatuadora=artista) if referencia else None
    inicial = {campo: getattr(bloque, campo) for campo in ("tipo", "fecha", "hora_inicio", "hora_fin", "postulacion", "nota")} if bloque else {"fecha": request.GET.get("fecha", timezone.localdate()), "tipo": "DISPONIBILIDAD"}
    if bloque:
        inicial["version"] = bloque.actualizada_en.isoformat()
    elif request.GET.get("solicitud"):
        from uuid import UUID
        from django.http import Http404
        try:
            solicitud_ref = UUID(request.GET["solicitud"])
        except ValueError:
            raise Http404
        p = get_object_or_404(Postulacion, tatuadora=artista, referencia=solicitud_ref)
        inicial.update(tipo="CITA", postulacion=p)
    form = BloqueForm(request.POST if request.method == "POST" else None, initial=inicial, tatuadora=artista)
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                guardar_bloque(request.user, form.cleaned_data, referencia)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
                status = 409
            except DatabaseError:
                form.add_error(None, "No se guardó el cambio. El horario pudo cambiar en otra ventana; recarga y vuelve a intentarlo.")
                status = 409
            else:
                messages.success(request, "Agenda actualizada.")
                return redirect("nucleo:agenda")
    return render(request, "agenda/editar.html", {"form": form, "bloque": bloque}, status=status)


@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN)
@never_cache
@require_POST
def cerrar(request, referencia):
    profesional(request)
    try:
        cerrar_bloque(request.user, referencia, request.POST.get("accion"), request.POST.get("motivo", ""), request.POST.get("version"))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    except DatabaseError:
        messages.error(request, "No se guardó el cambio. Recarga y vuelve a intentarlo.")
    else:
        messages.success(request, "Bloque actualizado; el historial se conserva.")
    return redirect("nucleo:agenda_editar", referencia=referencia)


@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN)
@never_cache
@require_POST
def gestion(request, referencia):
    artista = profesional(request)
    propuesta = get_object_or_404(Postulacion, referencia=referencia, tatuadora=artista)
    form = GestionForm(request.POST, solicitud=propuesta)
    status = 400
    if form.is_valid():
        try:
            gestionar(request.user, referencia, form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
            status = 409
        except DatabaseError:
            form.add_error(None, "No se guardó el cambio. Recarga y vuelve a intentarlo.")
            status = 409
        else:
            messages.success(request, "Solicitud actualizada.")
            return redirect("nucleo:cotizacion_detalle", referencia=referencia)
    from .cotizaciones import _detalle, propias
    return _detalle(request, referencia, propias(request.user), gestion_form=form, status=status)

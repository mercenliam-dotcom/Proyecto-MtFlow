"""Campana de avisos: solicitudes nuevas que la tatuadora aún no abre."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from web.models import Postulacion

LIMITE = 6


def no_leidas(user):
    return Postulacion.objects.filter(
        tatuadora__usuario=user, vista_en__isnull=True, estado__in=["RECIBIDA", "EN_REVISION"],
    ).select_related("contacto").order_by("-creada_en", "-pk")


def puede_ver(user):
    return user is not None and user.is_authenticated and getattr(user, "es_tatuadora", False) and not getattr(user, "es_cliente", False)


def _items(user):
    consulta = no_leidas(user)
    total = consulta.count()
    items = [{
        "nombre": str(p.contacto),
        "detalle": f"{p.zona_cuerpo.capitalize()} · {p.alto_cm:.2f} × {p.ancho_cm:.2f} cm".replace(".", ","),
        "hace": "hace " + timesince(p.creada_en).split(",")[0],
        "url": reverse("nucleo:cotizacion_detalle", args=[p.referencia]),
    } for p in consulta[:LIMITE]]
    return total, items


def contexto(request):
    """Procesador de contexto: solo el contador (una consulta) y solo para tatuadoras.
    La lista se pide al abrir la campana, así ninguna página incrusta solicitudes ajenas a ella."""
    user = getattr(request, "user", None)
    if not puede_ver(user):
        return {}
    return {"campana": {"total": no_leidas(user).count()}}


@login_required
@never_cache
@require_GET
def estado(request):
    if not puede_ver(request.user):
        return JsonResponse({"total": 0, "items": []}, status=403)
    total, items = _items(request.user)
    return JsonResponse({"total": total, "items": items})


@login_required
@require_POST
def marcar_leidas(request):
    if puede_ver(request.user):
        no_leidas(request.user).update(vista_en=timezone.now())
    return redirect("nucleo:cotizaciones")


def marcar_vista(user, referencia):
    """Al abrir el detalle. update() no altera actualizada_en (control de versión)."""
    Postulacion.objects.filter(tatuadora__usuario=user, referencia=referencia, vista_en__isnull=True).update(vista_en=timezone.now())

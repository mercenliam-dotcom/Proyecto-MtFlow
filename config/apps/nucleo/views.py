import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from .firmas import leer_ruta_firmada
from apps.cuentas.permisos import rol_requerido
from apps.cuentas.models import Rol


@login_required
@require_GET
def inicio(request):
    if request.user.es_cliente:
        return redirect("clientes:inicio")
    contexto = {"hoy": timezone.localdate()}
    if request.user.es_tatuadora:
        # Resumen de trabajo pendiente: solo lectura de las propias solicitudes.
        from .cotizaciones import propias
        from web.models import BloqueHorario
        mias = propias(request.user)
        por_decidir = mias.filter(estado__in=["RECIBIDA", "EN_REVISION"])
        contexto.update({
            "cuenta": {
                "por_decidir": por_decidir.count(),
                "aceptadas": mias.filter(estado="ACEPTADA").count(),
                "agendadas": mias.filter(estado="RESERVADA").count(),
            },
            "por_decidir": por_decidir.order_by("creada_en", "pk")[:5],
            "proximas": BloqueHorario.objects.filter(
                tatuadora__usuario=request.user, tipo="CITA", estado="RESERVADA", fecha__gte=contexto["hoy"],
            ).select_related("sesion__postulacion__contacto")[:5],
        })
    return render(request, "nucleo/inicio.html", contexto)


@rol_requerido(Rol.ADMIN)
@require_GET
def archivo(request, token):
    """Sirve un archivo privado solo si el token firmado es válido y no ha caducado."""
    ruta_relativa = leer_ruta_firmada(token)
    if not ruta_relativa:
        raise Http404
    from web.models import Imagen
    imagenes = Imagen.objects.filter(url=ruta_relativa)
    if not request.user.es_admin:
        imagenes = imagenes.filter(postulacion__tatuadora__usuario=request.user)
    if not imagenes.exists():
        raise Http404
    raiz = Path(settings.MEDIA_ROOT).resolve()
    ruta = (raiz / ruta_relativa).resolve()
    # Impide salir de MEDIA_ROOT con "../" aunque la firma fuera válida.
    if raiz not in ruta.parents or not ruta.is_file():
        raise Http404
    tipo, _ = mimetypes.guess_type(ruta.name)
    if tipo not in ("image/jpeg", "image/png"):
        raise Http404
    respuesta = FileResponse(open(ruta, "rb"), content_type=tipo)
    respuesta["Content-Disposition"] = "inline"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta

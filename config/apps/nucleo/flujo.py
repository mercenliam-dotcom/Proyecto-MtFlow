"""Gestión profesional: revisión humana, cobros externos y cierre explícito."""
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import Postulacion, Estilo, Imagen, EtiquetaConsolidada, MovimientoCobro, EventoSolicitud
from web.validadores import texto_sin_controles
from .agenda import profesional
from .operaciones_agenda import bloquear_profesional


class RevisionForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    estilo = forms.ModelChoiceField(queryset=Estilo.objects.all().order_by("nombre"), label="Estilo confirmado por ti")


class CobroForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    tipo = forms.ChoiceField(choices=MovimientoCobro.Tipo.choices, label="Movimiento")
    monto = forms.IntegerField(min_value=1, max_value=100000000, label="Importe de este movimiento (CLP)")
    verificado = forms.BooleanField(label="Comprobé este pago o devolución fuera de MTFlow")
    detalle = forms.CharField(max_length=300, validators=[texto_sin_controles], label="Referencia del comprobante / motivo", widget=forms.Textarea(attrs={"rows": 2}))


class CierreForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    confirmado = forms.BooleanField(label="El tatuaje está terminado y revisé los cobros registrados")


class InasistenciaForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    destino_abono = forms.ChoiceField(choices=Postulacion.DestinoAbono.choices, label="Acuerdo sobre el abono")
    detalle = forms.CharField(max_length=300, validators=[texto_sin_controles], label="Acuerdo con el cliente", widget=forms.Textarea(attrs={"rows": 2}))


@transaction.atomic
def aplicar(user, referencia, accion, datos):
    artista = bloquear_profesional(user)
    p = get_object_or_404(Postulacion.objects.select_for_update(), referencia=referencia, tatuadora=artista)
    clases = {"estilo": RevisionForm, "cobro": CobroForm, "terminar": CierreForm, "inasistencia": InasistenciaForm}
    if accion not in clases:
        raise ValidationError("Acción desconocida.")
    form = clases[accion](datos)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    d = form.cleaned_data
    if d["version"] != p.actualizada_en.isoformat():
        raise ValidationError("La solicitud cambió. Recarga y revisa sus datos antes de continuar.")
    detalle = d.get("detalle", "")
    if accion == "estilo":
        imagen = get_object_or_404(Imagen, postulacion=p, es_principal=True)
        pred = imagen.prediccion_set.order_by("-generada_en", "-pk").first()
        EtiquetaConsolidada.objects.update_or_create(imagen=imagen, defaults={
            "estilo": d["estilo"], "tatuadora": artista,
            "fue_corregida": bool(pred and pred.estilo_sugerido_id != d["estilo"].pk),
            "apta_entrenamiento": False, "confirmada_en": timezone.now(),
        })
        detalle = f"Estilo revisado: {d['estilo'].nombre}. No inicia entrenamiento."
    elif accion == "cobro":
        if p.estado not in ("ACEPTADA", "RESERVADA", "REALIZADA") or not p.precio_final:
            raise ValidationError("Registra primero el acuerdo con su precio total.")
        neto = p.total_cobrado
        if d["tipo"] == "DEVOLUCION" and d["monto"] > neto:
            raise ValidationError("No puedes devolver más de lo recibido.")
        if d["tipo"] == "PAGO" and neto + d["monto"] > p.precio_final:
            raise ValidationError("El cobro supera el total acordado. Revisa el acuerdo.")
        MovimientoCobro.objects.create(postulacion=p, tipo=d["tipo"], monto=d["monto"], detalle=detalle, verificado_por=user)
        detalle = f"{d['tipo']}: {d['monto']} CLP. {detalle}"
    elif accion == "terminar":
        if p.estado not in ("ACEPTADA", "RESERVADA") or not p.sesiones.filter(estado="REALIZADA").exists():
            raise ValidationError("Debes registrar al menos una sesión realizada antes de terminar el trabajo.")
        if p.sesiones.filter(estado="RESERVADA").exists():
            raise ValidationError("Todavía hay sesiones reservadas. Complétalas o cancélalas antes de cerrar.")
        p.estado, p.realizada_en = "REALIZADA", timezone.now()
        detalle = f"Trabajo terminado. Cobrado: {p.total_cobrado} CLP; saldo: {p.saldo_pendiente} CLP."
    else:
        if not p.sesiones.filter(estado="NO_ASISTIO").exists():
            raise ValidationError("Primero registra la inasistencia en la sesión correspondiente.")
        if d["destino_abono"] in ("RETENIDO", "DEVOLVER") and p.sesiones.filter(estado="RESERVADA").exists():
            raise ValidationError("Resuelve primero las sesiones aún reservadas antes de retener o devolver el abono.")
        p.destino_abono = d["destino_abono"]
        detalle = f"Abono: {p.get_destino_abono_display()}. {detalle}"
    p.full_clean()
    p.save()
    EventoSolicitud.objects.create(postulacion=p, actor=user, tipo=accion, detalle=detalle[:500])
    return p


@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN, Rol.USUARIO)
@never_cache
@require_http_methods(["GET", "POST"])
def editar(request, referencia, accion):
    artista = profesional(request)
    p = get_object_or_404(Postulacion, referencia=referencia, tatuadora=artista)
    clases = {"estilo": (RevisionForm, "Revisar estilo"), "cobro": (CobroForm, "Registrar pago o devolución"), "terminar": (CierreForm, "Terminar trabajo"), "inasistencia": (InasistenciaForm, "Resolver abono por inasistencia")}
    from django.http import Http404
    if accion not in clases:
        raise Http404
    clase, titulo = clases[accion]
    form = clase(request.POST if request.method == "POST" else None, initial={"version": p.actualizada_en.isoformat(), "destino_abono": p.destino_abono})
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                aplicar(request.user, referencia, accion, form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
                status = 409
            except DatabaseError:
                form.add_error(None, "No se guardó el cambio. Recarga antes de reintentar.")
                status = 409
            else:
                messages.success(request, "Cambio registrado en el historial.")
                return redirect("nucleo:cotizacion_detalle", referencia=referencia)
    return render(request, "flujo/formulario.html", {"form": form, "titulo": titulo, "propuesta": p}, status=status)

"""Gestión profesional: revisión humana, cobros externos y cierre explícito."""
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
import uuid
from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction, DatabaseError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import Postulacion, Estilo, Imagen, EtiquetaConsolidada, MovimientoCobro, EventoSolicitud
from web.validadores import texto_sin_controles
from .agenda import profesional
from .operaciones_agenda import bloquear_profesional
from .imagenes import validar_imagen, TIPOS_ACEPTADOS_HTML


class RevisionForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    estilo = forms.ModelChoiceField(queryset=Estilo.objects.all().order_by("nombre"), label="Estilo confirmado por ti")


class CobroForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    tipo = forms.ChoiceField(choices=MovimientoCobro.Tipo.choices, label="Movimiento")
    monto = forms.IntegerField(min_value=1, max_value=100000000, label="Importe de este movimiento (CLP)")
    verificado = forms.BooleanField(label="Comprobé este pago o devolución fuera de MTFlow")
    detalle = forms.CharField(max_length=300, validators=[texto_sin_controles], label="Referencia del comprobante / motivo", widget=forms.Textarea(attrs={"rows": 2}))
    comprobante = forms.FileField(required=False, label="Imagen del comprobante (opcional, JPG o PNG, máximo 10 MB)",
                                  help_text="Una captura o foto legible de la transferencia. Solo la ves tú; no se publica.",
                                  widget=forms.FileInput(attrs={"accept": TIPOS_ACEPTADOS_HTML}))

    def clean_comprobante(self):
        archivo = self.cleaned_data.get("comprobante")
        # Misma validación que las referencias: firma real JPG/PNG, tamaño y re-codificación.
        return validar_imagen(archivo).archivo if archivo else None


class CierreForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    confirmado = forms.BooleanField(label="El tatuaje está terminado y revisé los cobros registrados")


class InasistenciaForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    destino_abono = forms.ChoiceField(choices=Postulacion.DestinoAbono.choices, label="Acuerdo sobre el abono")
    detalle = forms.CharField(max_length=300, validators=[texto_sin_controles], label="Acuerdo con el cliente", widget=forms.Textarea(attrs={"rows": 2}))


def _resumen_cobro(p):
    """Cifras del acuerdo para mostrar cuánto se abonó y cuánto resta."""
    from django.db.models import Sum
    from .operaciones_agenda import _clp
    por_tipo = dict(p.movimientos.values_list("tipo").annotate(total=Sum("monto")))
    abono = p.monto_abono if p.abono_verificado_en and p.monto_abono else 0
    datos = {"precio": p.precio_final or 0, "abono": abono, "pagos": por_tipo.get("PAGO", 0), "devoluciones": por_tipo.get("DEVOLUCION", 0),
             "neto": p.total_cobrado, "saldo": p.saldo_pendiente}
    datos["texto"] = {k: _clp(v) for k, v in datos.items()}
    return datos


def _almacen():
    return FileSystemStorage(location=settings.MEDIA_ROOT)


def aplicar(user, referencia, accion, datos, archivos=None):
    """Aplica la acción; si falla, borra los archivos que alcanzó a guardar."""
    guardados = []
    try:
        return _aplicar(user, referencia, accion, datos, archivos, guardados)
    except BaseException:
        for ruta in guardados:
            _almacen().delete(ruta)
        raise


@transaction.atomic
def _aplicar(user, referencia, accion, datos, archivos, guardados):
    artista = bloquear_profesional(user)
    p = get_object_or_404(Postulacion.objects.select_for_update(), referencia=referencia, tatuadora=artista)
    clases = {"estilo": RevisionForm, "cobro": CobroForm, "terminar": CierreForm, "inasistencia": InasistenciaForm}
    if accion not in clases:
        raise ValidationError("Acción desconocida.")
    form = clases[accion](datos, archivos)
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
        ruta = ""
        if d.get("comprobante"):
            archivo = d["comprobante"]
            ruta = _almacen().save(f"comprobantes/{p.referencia.hex}/{uuid.uuid4().hex}{Path(archivo.name).suffix.lower()}", archivo)
            guardados.append(ruta)
        MovimientoCobro.objects.create(postulacion=p, tipo=d["tipo"], monto=d["monto"], detalle=detalle, verificado_por=user, comprobante=ruta)
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
@rol_requerido(Rol.ADMIN)
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
    inicial = {"version": p.actualizada_en.isoformat(), "destino_abono": p.destino_abono}
    resumen = _resumen_cobro(p) if accion == "cobro" else None
    if resumen and resumen["saldo"] > 0:
        inicial["monto"] = resumen["saldo"]  # sugerencia: pagar lo que resta
    form = clase(request.POST if request.method == "POST" else None, request.FILES if request.method == "POST" else None, initial=inicial)
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            try:
                aplicar(request.user, referencia, accion, form.cleaned_data, request.FILES)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
                status = 409
            except DatabaseError:
                form.add_error(None, "No se guardó el cambio. Recarga antes de reintentar.")
                status = 409
            else:
                messages.success(request, "Cambio registrado en el historial.")
                return redirect("nucleo:cotizacion_detalle", referencia=referencia)
    return render(request, "flujo/formulario.html", {"form": form, "titulo": titulo, "propuesta": p, "resumen_cobro": resumen}, status=status)


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def comprobante(request, referencia, pk):
    """Muestra la imagen del comprobante solo a la tatuadora dueña de la solicitud."""
    artista = profesional(request)
    movimiento = get_object_or_404(MovimientoCobro, pk=pk, postulacion__referencia=referencia, postulacion__tatuadora=artista)
    raiz = Path(settings.MEDIA_ROOT).resolve()
    archivo = (raiz / movimiento.comprobante).resolve() if movimiento.comprobante else None
    if not archivo or not movimiento.comprobante.startswith("comprobantes/") or raiz not in archivo.parents or not archivo.is_file():
        raise Http404
    tipo = "image/png" if archivo.suffix.lower() == ".png" else "image/jpeg"
    respuesta = FileResponse(open(archivo, "rb"), content_type=tipo)
    respuesta["Content-Disposition"] = "inline"
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta

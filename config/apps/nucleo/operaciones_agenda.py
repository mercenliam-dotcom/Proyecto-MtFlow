"""Operaciones atómicas de agenda. Todas bloquean primero a la profesional."""
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.forms.utils import from_current_timezone
from django.shortcuts import get_object_or_404
from django.utils import timezone
from web.models import BloqueHorario, EventoSolicitud, Postulacion, Tatuadora

OCUPADOS = ("RESERVADA", "REALIZADA", "BLOQUEADO")


def bloquear_profesional(user):
    qs = Tatuadora.objects.filter(usuario=user, activa=True, usuario__is_active=True, usuario__es_tatuadora=True)
    if connection.vendor == "sqlite":
        # SQLite no implementa SELECT FOR UPDATE: adquirir el bloqueo de escritura
        # antes de leer disponibilidad. No se reintenta una operación parcialmente guardada.
        qs.update(activa=F("activa"))
    return get_object_or_404(qs.select_for_update())


@transaction.atomic
def gestionar(user, referencia, datos):
    artista = bloquear_profesional(user)
    p = get_object_or_404(Postulacion.objects.select_for_update(), referencia=referencia, tatuadora=artista)
    accion = datos["accion"]
    if accion == "revisar":
        if p.estado != "RECIBIDA":
            raise ValidationError("Solo puedes pasar a revisión una solicitud recién recibida.")
        p.estado = "EN_REVISION"
    elif accion == "aceptar":
        if p.estado not in ("RECIBIDA", "EN_REVISION", "ACEPTADA"):
            raise ValidationError("El estado actual no permite registrar este acuerdo.")
        if p.abono_verificado_en and datos["precio_final"] < (p.monto_abono or 0):
            raise ValidationError("El precio no puede ser menor que el abono verificado.")
        p.precio_final = datos["precio_final"]
        p.estado = "ACEPTADA"
    elif accion == "abono":
        if p.estado not in ("ACEPTADA", "RESERVADA") or not p.precio_final:
            raise ValidationError("Primero registra el acuerdo y el precio final.")
        monto = datos["monto_abono"]
        if not datos["verificado"] or monto > p.precio_final or monto < (p.monto_abono or 0):
            raise ValidationError("El abono debe estar verificado, no disminuir y no superar el precio acordado.")
        p.monto_abono = monto
        p.abono_verificado_en = timezone.now()
        p.abono_verificado_por = user
    elif accion == "rechazar":
        if p.estado not in ("RECIBIDA", "EN_REVISION", "ACEPTADA") or p.sesiones.filter(estado__in=OCUPADOS).exists():
            raise ValidationError("No puedes rechazar una solicitud con sesiones reservadas o realizadas.")
        if p.abono_verificado_en:
            raise ValidationError("Esta solicitud tiene un abono: resuelve la cancelación con el cliente antes de cerrar el proceso.")
        p.estado, p.motivo_rechazo = "RECHAZADA", datos["motivo"]
    p.save()
    detalle = datos.get("motivo", "")
    if accion == "aceptar":
        detalle = f"Precio acordado: {p.precio_final} CLP. {detalle}"[:500]
    if accion == "abono":
        detalle = f"Abono verificado acumulado: {p.monto_abono} CLP. {detalle}"[:500]
    EventoSolicitud.objects.create(postulacion=p, actor=user, tipo=accion, detalle=detalle)
    return p


@transaction.atomic
def guardar_bloque(user, datos, referencia=None):
    artista = bloquear_profesional(user)
    b = get_object_or_404(BloqueHorario, referencia=referencia, tatuadora=artista) if referencia else BloqueHorario(tatuadora=artista)
    if b.pk:
        if b.estado in ("CANCELADA", "REALIZADA"):
            raise ValidationError("Una sesión cancelada o realizada no se puede reprogramar.")
        if b.actualizada_en.isoformat() != datos.get("version"):
            raise ValidationError("El bloque cambió en otra ventana. Recarga antes de modificarlo.")
        if datos["tipo"] != b.tipo or (b.postulacion_id and getattr(datos.get("postulacion"), "pk", None) != b.postulacion_id):
            raise ValidationError("Para cambiar el tipo o el cliente, cancela el bloque y crea uno nuevo.")
    anteriores = (b.fecha, b.hora_inicio, b.hora_fin) if b.pk else None
    p = None
    if datos["tipo"] == "CITA":
        p = get_object_or_404(Postulacion.objects.select_for_update(), pk=datos["postulacion"].pk, tatuadora=artista)
        if p.estado not in ("ACEPTADA", "RESERVADA") or not p.abono_verificado_en or not p.monto_abono:
            raise ValidationError("La solicitud necesita acuerdo y abono verificado antes de reservar.")
    candidatos = BloqueHorario.objects.filter(tatuadora=artista, fecha=datos["fecha"], hora_inicio__lt=datos["hora_fin"], hora_fin__gt=datos["hora_inicio"]).exclude(pk=b.pk)
    if datos["tipo"] == "DISPONIBILIDAD":
        if candidatos.filter(tipo="DISPONIBILIDAD", estado="DISPONIBLE").exists():
            raise ValidationError("Esta disponibilidad se superpone con otra. Edita el bloque existente.")
        if b.pk:
            asegurar_sesiones_cubiertas(b, datos)
    else:
        if candidatos.filter(estado__in=OCUPADOS).exists():
            raise ValidationError("Ese intervalo ya está ocupado. Elige otra hora.")
        if p and not BloqueHorario.objects.filter(tatuadora=artista, tipo="DISPONIBILIDAD", estado="DISPONIBLE", fecha=datos["fecha"], hora_inicio__lte=datos["hora_inicio"], hora_fin__gte=datos["hora_fin"]).exists():
            raise ValidationError("La sesión debe quedar dentro de un bloque de disponibilidad de tu agenda.")
    for campo in ("tipo", "fecha", "hora_inicio", "hora_fin", "nota"):
        setattr(b, campo, datos[campo])
    b.postulacion = p
    b.estado = {"CITA": "RESERVADA", "BLOQUEO": "BLOQUEADO", "DISPONIBILIDAD": "DISPONIBLE"}[b.tipo]
    b.full_clean()
    b.save()
    if p:
        p.estado = "RESERVADA"
        # Conservar compatibilidad con el DER original; sesiones permite más de una.
        if not p.bloque_id:
            p.bloque = b
        p.save(update_fields=["estado", "bloque", "actualizada_en"])
        detalle = f"{b.fecha} {b.hora_inicio:%H:%M}–{b.hora_fin:%H:%M}"
        if anteriores:
            detalle = f"Antes: {anteriores}. Ahora: {detalle}"
        EventoSolicitud.objects.create(postulacion=p, actor=user, tipo="reprogramada" if anteriores else "reservada", detalle=detalle[:500])
    return b


def asegurar_sesiones_cubiertas(bloque, reemplazo=None):
    sesiones = BloqueHorario.objects.filter(tatuadora=bloque.tatuadora, tipo="CITA", estado="RESERVADA", fecha=bloque.fecha, hora_inicio__gte=bloque.hora_inicio, hora_fin__lte=bloque.hora_fin)
    for sesion in sesiones:
        if not reemplazo or reemplazo["fecha"] != sesion.fecha or reemplazo["hora_inicio"] > sesion.hora_inicio or reemplazo["hora_fin"] < sesion.hora_fin:
            raise ValidationError("Reprograma o cancela primero las sesiones dentro de esta disponibilidad.")


@transaction.atomic
def cerrar_bloque(user, referencia, accion, motivo, version):
    artista = bloquear_profesional(user)
    b = get_object_or_404(BloqueHorario, referencia=referencia, tatuadora=artista)
    if b.actualizada_en.isoformat() != version:
        raise ValidationError("El bloque cambió. Recarga la página.")
    if b.estado in ("CANCELADA", "REALIZADA"):
        raise ValidationError("El bloque ya está cerrado.")
    if accion == "realizar":
        fin = from_current_timezone(datetime.combine(b.fecha, b.hora_fin))
        if b.tipo != "CITA" or fin > timezone.now():
            raise ValidationError("Solo puedes completar una sesión cuyo horario ya terminó.")
        b.estado = "REALIZADA"
    elif accion == "cancelar":
        if not motivo.strip():
            raise ValidationError("Indica un motivo para cancelar.")
        if b.tipo == "DISPONIBILIDAD":
            asegurar_sesiones_cubiertas(b)
        b.estado = "CANCELADA"
    else:
        raise ValidationError("Acción no válida.")
    b.save(update_fields=["estado", "actualizada_en"])
    if b.postulacion_id:
        p = b.postulacion
        otras = p.sesiones.exclude(pk=b.pk)
        if not otras.filter(estado="RESERVADA").exists():
            p.estado = "REALIZADA" if b.estado == "REALIZADA" else "ACEPTADA"
            if p.estado == "REALIZADA":
                p.realizada_en = timezone.now()
            p.save(update_fields=["estado", "realizada_en", "actualizada_en"])
        EventoSolicitud.objects.create(postulacion=p, actor=user, tipo=accion, detalle=f"Sesión {b.fecha} {b.hora_inicio:%H:%M}. {motivo}"[:500])
    return b

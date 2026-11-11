
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from .validadores import nombre_contacto, telefono_contacto, texto_sin_controles

from django.db import models
from django.conf import settings

class Cliente(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.RESTRICT, related_name="cliente_registro")
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    nombres = models.CharField(max_length=80)
    primer_apellido = models.CharField(max_length=160, blank=True)
    segundo_apellido = models.CharField(max_length=80, blank=True)
    correo = models.EmailField(max_length=254, null=True, blank=True)
    telefono = models.CharField(max_length=25, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombres} {self.primer_apellido} {self.segundo_apellido}".strip()

    @property
    def apellidos(self):
        return self.primer_apellido

    @apellidos.setter
    def apellidos(self, valor):
        self.primer_apellido = valor

class Tatuadora(models.Model):
    # Conectamos con el sistema de usuarios de Django como sugería el mer.txt
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre_artistico = models.CharField(max_length=120, null=True, blank=True)
    telefono = models.CharField(max_length=25, blank=True, validators=[telefono_contacto])
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre_publico

    @property
    def nombre_publico(self):
        """El nombre vigente de la cuenta vinculada, incluso en perfiles antiguos."""
        return self.usuario.get_full_name().strip() or self.usuario.nombre_usuario

class HorarioTrabajo(models.Model):
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.CASCADE, related_name="horario_semanal")
    dia = models.PositiveIntegerField(choices=list(enumerate(["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])))
    activo = models.BooleanField(default=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        ordering = ["dia"]
        unique_together = [("tatuadora", "dia")]
        constraints = [
            models.CheckConstraint(condition=models.Q(dia__gte=0, dia__lte=6), name="horario_dia_valido"),
            models.CheckConstraint(condition=models.Q(hora_inicio__lt=models.F("hora_fin")), name="horario_intervalo_valido"),
        ]


class BloqueHorario(models.Model):
    class Tipo(models.TextChoices):
        DISPONIBILIDAD = "DISPONIBILIDAD", "Disponible para trabajar"
        CITA = "CITA", "Sesión reservada"
        BLOQUEO = "BLOQUEO", "Bloqueo personal"

    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.DISPONIBILIDAD)
    nota = models.CharField(max_length=300, blank=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.CharField(max_length=15)

    class Meta:
        ordering = ["fecha", "hora_inicio", "pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(hora_inicio__lt=models.F("hora_fin")), name="bloque_intervalo_positivo"),
            models.CheckConstraint(condition=models.Q(tipo="DISPONIBILIDAD", estado__in=["DISPONIBLE", "CANCELADA"]) | models.Q(tipo="CITA", estado__in=["RESERVADA", "REALIZADA", "CANCELADA", "NO_ASISTIO"]) | models.Q(tipo="BLOQUEO", estado__in=["BLOQUEADO", "CANCELADA"]), name="bloque_tipo_estado_valido"),
        ]
        indexes = [models.Index(fields=["tatuadora", "fecha", "estado"], name="agenda_busqueda")]

    @property
    def postulacion(self):
        try:
            return self.sesion.postulacion
        except Sesion.DoesNotExist:
            return None

    @property
    def postulacion_id(self):
        return self.postulacion.pk if self.postulacion else None

    def __str__(self):
        return f"{self.fecha} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M} · {self.get_tipo_display()}"

class Postulacion(models.Model):
    @property
    def cuenta_cliente(self):
        return self.cliente.usuario

    @property
    def cuenta_cliente_id(self):
        return self.cliente.usuario_id
    class DestinoAbono(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de acuerdo"
        REAGENDAR = "REAGENDAR", "Conservar para reagendar"
        RETENIDO = "RETENIDO", "Retenido según acuerdo"
        DEVOLVER = "DEVOLVER", "Devolución acordada (registrar devolución por separado)"

    fecha_propuesta = models.DateField(null=True, blank=True)
    hora_propuesta = models.TimeField(null=True, blank=True)
    abono_solicitado = models.PositiveIntegerField(null=True, blank=True)
    alto_final_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ancho_final_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    destino_abono = models.CharField(max_length=15, choices=DestinoAbono.choices, default=DestinoAbono.PENDIENTE)
    class EstadoML(models.TextChoices):
        LEGADO = "LEGADO", "Sin trazabilidad previa"
        NO_SOLICITADO = "NO_SOLICITADO", "No solicitado"
        COMPLETADO = "COMPLETADO", "Completado"
        NO_DISPONIBLE = "NO_DISPONIBLE", "No disponible"

    abono_verificado_en = models.DateTimeField(null=True, blank=True)
    abono_verificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="abonos_verificados")
    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    estado_ml = models.CharField(max_length=20, choices=EstadoML.choices, default=EstadoML.LEGADO)
    # Primera vez que la tatuadora abrió el detalle; vacío = aviso no leído.
    vista_en = models.DateTimeField(null=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.RESTRICT, related_name="solicitudes")
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    zona_cuerpo = models.CharField(max_length=100)
    alto_cm = models.DecimalField(max_digits=5, decimal_places=2)
    ancho_cm = models.DecimalField(max_digits=5, decimal_places=2)
    presupuesto_estimado = models.IntegerField(null=True, blank=True)
    descripcion = models.TextField(validators=[texto_sin_controles])
    color = models.CharField(max_length=10, choices=[("negro", "Negro y grises"), ("color", "Con color")], null=True, blank=True)
    nivel_detalle = models.CharField(max_length=10, choices=[("normal", "Simple o intermedio"), ("alto", "Alto")], null=True, blank=True)
    cobertura = models.BooleanField(null=True, blank=True)
    ciclo_de_vida = models.CharField(max_length=15, null=True, blank=True)
    estado = models.CharField(max_length=20)
    alerta_ml = models.CharField(max_length=20, null=True, blank=True)
    motivo_rechazo = models.TextField(null=True, blank=True)
    precio_sugerido = models.IntegerField(null=True, blank=True)
    precio_final = models.IntegerField(null=True, blank=True)
    monto_abono = models.IntegerField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    realizada_en = models.DateTimeField(null=True, blank=True)

    @property
    def area_cm2(self):
        return (Decimal(str(self.alto_cm)) * Decimal(str(self.ancho_cm))).quantize(Decimal(".0001"))

    @property
    def categoria_tamano(self):
        area = self.area_cm2
        return "pequeno" if area <= 25 else "mediano" if area <= 150 else "grande" if area <= 625 else "especial"

    @property
    def sesiones(self):
        return BloqueHorario.objects.filter(sesion__postulacion=self)

    @property
    def total_cobrado(self):
        # El abono histórico sigue siendo el único registro del depósito.
        # El libro adicional solo contiene pagos de saldo y devoluciones.
        from django.db.models import Sum, Case, When, F, IntegerField
        movimientos = self.movimientos.aggregate(total=Sum(Case(When(tipo="DEVOLUCION", then=-F("monto")), default=F("monto"), output_field=IntegerField())))["total"] or 0
        return (self.monto_abono or 0 if self.abono_verificado_en else 0) + movimientos

    @property
    def saldo_pendiente(self):
        return max(0, (self.precio_final or 0) - self.total_cobrado)

    @property
    def codigo(self):
        """Código corto y legible para mostrar (MT-7309021A). La referencia completa
        sigue siendo el identificador interno de los enlaces."""
        return "MT-" + self.referencia.hex[:8].upper()

    @property
    def estado_comercial(self):
        if self.estado == "ACEPTADA":
            return "Confirmada" if self.abono_verificado_en and self.total_cobrado > 0 else "Cotizada"
        return self.estado.replace("_", " ").capitalize()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(abono_solicitado__isnull=True) | models.Q(abono_solicitado__gt=0, abono_solicitado__lte=100000000), name="abono_solicitado_valido"),
            models.CheckConstraint(condition=models.Q(abono_solicitado__isnull=True) | models.Q(precio_final__isnull=True) | models.Q(abono_solicitado__lte=models.F("precio_final")), name="abono_solicitado_no_supera_total"),
            models.CheckConstraint(condition=models.Q(alto_final_cm__isnull=True, ancho_final_cm__isnull=True) | models.Q(alto_final_cm__isnull=False, ancho_final_cm__isnull=False, alto_final_cm__gt=0, ancho_final_cm__gt=0), name="medidas_finales_coherentes"),
            models.CheckConstraint(condition=models.Q(fecha_propuesta__isnull=True, hora_propuesta__isnull=True) | models.Q(fecha_propuesta__isnull=False, hora_propuesta__isnull=False), name="preferencia_fecha_hora_completa"),
            models.CheckConstraint(condition=models.Q(destino_abono__in=["PENDIENTE", "REAGENDAR", "RETENIDO", "DEVOLVER"]), name="destino_abono_valido"),
            models.CheckConstraint(condition=models.Q(alto_cm__gt=0, alto_cm__lte=Decimal("999.99"), ancho_cm__gt=0, ancho_cm__lte=Decimal("999.99")), name="solicitud_medidas_validas"),
            models.CheckConstraint(condition=models.Q(precio_final__isnull=True) | models.Q(precio_final__gt=0, precio_final__lte=100000000), name="solicitud_precio_valido"),
            models.CheckConstraint(condition=models.Q(monto_abono__isnull=True) | models.Q(monto_abono__gte=0, monto_abono__lte=100000000), name="solicitud_abono_valido"),
            models.CheckConstraint(condition=models.Q(monto_abono__isnull=True) | models.Q(precio_final__isnull=True) | models.Q(monto_abono__lte=models.F("precio_final")), name="abono_no_supera_precio"),
            models.CheckConstraint(condition=models.Q(abono_verificado_en__isnull=True) | models.Q(monto_abono__isnull=False, monto_abono__gt=0, precio_final__isnull=False), name="abono_verificado_coherente"),
            models.CheckConstraint(condition=models.Q(color__isnull=True) | models.Q(color__in=["negro", "color"]), name="solicitud_color_valido"),
            models.CheckConstraint(condition=models.Q(nivel_detalle__isnull=True) | models.Q(nivel_detalle__in=["normal", "alto"]), name="solicitud_detalle_valido"),
            models.CheckConstraint(condition=models.Q(estado__in=["RECIBIDA", "EN_REVISION", "ACEPTADA", "RESERVADA", "REALIZADA", "RECHAZADA"]), name="solicitud_estado_valido"),
        ]


class ContactoSolicitud(models.Model):
    """Datos declarados en un envío: no acreditan la identidad de Cliente."""
    postulacion = models.OneToOneField(Postulacion, primary_key=True, on_delete=models.RESTRICT, related_name="contacto")
    nombres = models.CharField(max_length=80, validators=[nombre_contacto])
    primer_apellido = models.CharField(max_length=160, blank=True)
    segundo_apellido = models.CharField(max_length=80, blank=True, validators=[nombre_contacto])
    canal_preferido = models.CharField(max_length=12, choices=[("correo", "Correo"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("tiktok", "TikTok")], default="correo")
    usuario_social = models.CharField(max_length=80, blank=True, validators=[nombre_contacto])
    correo = models.EmailField(max_length=254, null=True, blank=True)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[telefono_contacto])

    def __str__(self):
        return f"{self.nombres} {self.primer_apellido} {self.segundo_apellido}".strip()

    @property
    def apellidos(self):
        """Compatibilidad de lectura para vistas anteriores; no es otra columna."""
        return self.primer_apellido

    @apellidos.setter
    def apellidos(self, valor):
        self.primer_apellido = valor


class Sesion(models.Model):
    """ Única relación entre una reserva de agenda y una solicitud."""
    bloque = models.OneToOneField(BloqueHorario, primary_key=True, on_delete=models.RESTRICT, related_name="sesion")
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT, related_name="vinculos_sesiones")

    def clean(self):
        if self.bloque_id and self.postulacion_id:
            if self.bloque.tatuadora_id != self.postulacion.tatuadora_id or self.bloque.tipo != "CITA":
                raise ValidationError("La sesión debe vincular una cita y una solicitud de la misma tatuadora.")
            
            # --- NUEVA VALIDACIÓN: Bloquea duplicidad ---
            if Sesion.objects.filter(postulacion_id=self.postulacion_id).exclude(pk=self.pk).exists():
                raise ValidationError("Esta solicitud ya tiene un horario asignado. No puedes asignarle otro.")


class Imagen(models.Model):
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT)
    url = models.TextField(unique=True)
    orden = models.SmallIntegerField()
    es_principal = models.BooleanField(default=False)
    formato = models.CharField(max_length=10)
    ancho_px = models.IntegerField()
    alto_px = models.IntegerField()
    tamano_bytes = models.IntegerField()
    nitidez = models.FloatField(null=True, blank=True)
    cargada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('postulacion', 'orden')
        constraints = [
            models.UniqueConstraint(fields=["postulacion"], condition=models.Q(es_principal=True), name="imagen_principal_unica"),
            models.CheckConstraint(condition=models.Q(orden__gt=0, ancho_px__gt=0, alto_px__gt=0, tamano_bytes__gt=0), name="imagen_metadata_positiva"),
        ]

class Estilo(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(null=True, blank=True)
    es_catalogo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Prediccion(models.Model):
    imagen = models.ForeignKey(Imagen, on_delete=models.RESTRICT)
    version_modelo = models.CharField(max_length=120)
    estilo_sugerido = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    confianza_maxima = models.DecimalField(max_digits=17, decimal_places=16)
    umbral_confianza = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    tiempo_inferencia_ms = models.IntegerField()
    ood = models.JSONField(null=True, blank=True)
    motivo_abstencion = models.CharField(max_length=32, blank=True, default="", choices=[
        ("", "Sin abstención"), ("fuera_distribucion", "Fuera de distribución"),
        ("confianza_insuficiente", "Confianza insuficiente"),
    ])
    generada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('imagen', 'version_modelo')
        constraints = [models.CheckConstraint(condition=models.Q(confianza_maxima__gte=0, confianza_maxima__lte=1, tiempo_inferencia_ms__gte=0), name="prediccion_valores_validos"), models.CheckConstraint(condition=models.Q(umbral_confianza__isnull=True) | models.Q(umbral_confianza__gte=0, umbral_confianza__lte=1), name="prediccion_umbral_valido")]

class ConfianzaEstilo(models.Model):
    prediccion = models.ForeignKey(Prediccion, on_delete=models.RESTRICT)
    estilo = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    confianza = models.DecimalField(max_digits=17, decimal_places=16)

    class Meta:
        unique_together = ('prediccion', 'estilo')
        constraints = [models.CheckConstraint(condition=models.Q(confianza__gte=0, confianza__lte=1), name="confianza_estilo_valida")]

class EtiquetaConsolidada(models.Model):
    imagen = models.OneToOneField(Imagen, on_delete=models.RESTRICT)
    estilo = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    fue_corregida = models.BooleanField()
    apta_entrenamiento = models.BooleanField(default=False)
    confirmada_en = models.DateTimeField(auto_now_add=True)

class TatuadoraEstilo(models.Model):
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    estilo = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    dominio = models.CharField(max_length=12)

    class Meta:
        unique_together = ('tatuadora', 'estilo')

class TrabajoPortafolio(models.Model):
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    estilo = models.ForeignKey(Estilo, on_delete=models.RESTRICT, null=True, blank=True)
    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT, null=True, blank=True)
    visible = models.BooleanField(default=False)
    en_carrusel = models.BooleanField(default=False)
    autorizacion_publicacion = models.BooleanField(default=False)
    tipo = models.CharField(max_length=10, choices=[("TATUAJE", "Tatuaje realizado"), ("ESTUDIO", "Estudio")], default="TATUAJE")
    actualizada_en = models.DateTimeField(auto_now=True)
    titulo = models.CharField(max_length=120)
    url = models.TextField()
    publicado_en = models.DateField()
    apto_entrenamiento = models.BooleanField(default=False)

    def clean(self):
        if self.postulacion_id and self.postulacion.tatuadora_id != self.tatuadora_id:
            raise ValidationError("La solicitud debe pertenecer a tu cuenta.")
        if self.visible and not self.autorizacion_publicacion:
            raise ValidationError("Confirma que tienes autorización para publicar esta fotografía.")
        if self.tipo == "TATUAJE" and not self.estilo_id:
            raise ValidationError("Selecciona el estilo del tatuaje.")


class MovimientoCobro(models.Model):
    class Tipo(models.TextChoices):
        PAGO = "PAGO", "Pago adicional recibido (no repetir el abono)"
        DEVOLUCION = "DEVOLUCION", "Devolución efectivamente realizada"
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT, related_name="movimientos")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    monto = models.PositiveIntegerField()
    detalle = models.CharField(max_length=300, validators=[texto_sin_controles])
    verificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-pk"]
        constraints = [models.CheckConstraint(condition=models.Q(monto__gt=0, monto__lte=100000000), name="cobro_monto_valido"), models.CheckConstraint(condition=models.Q(tipo__in=["PAGO", "DEVOLUCION"]), name="cobro_tipo_valido")]


from django.db.models.signals import post_save
from django.dispatch import receiver  
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_perfil_tatuadora(sender, instance, created, raw=False, **kwargs):
    if not raw and instance.es_tatuadora:

        # Habilitar la función en una cuenta existente también crea su perfil.
        # Deshabilitarla no elimina el perfil ni sus propuestas históricas.
        Tatuadora.objects.get_or_create(
            usuario=instance, defaults={"activa": True},
        )


class EventoSolicitud(models.Model):
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT, related_name="eventos")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=40)
    detalle = models.CharField(max_length=500, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-pk"]

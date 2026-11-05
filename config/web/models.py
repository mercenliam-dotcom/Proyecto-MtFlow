
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from .validadores import nombre_contacto, telefono_contacto, texto_sin_controles

from django.db import models
from django.conf import settings

class Cliente(models.Model):
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=160)
    correo = models.EmailField(max_length=254, null=True, blank=True)
    telefono = models.CharField(max_length=25, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

class Tatuadora(models.Model):
    # Conectamos con el sistema de usuarios de Django como sugería el mer.txt
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre_artistico = models.CharField(max_length=120, null=True, blank=True)
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre_publico

    @property
    def nombre_publico(self):
        """El nombre vigente de la cuenta vinculada, incluso en perfiles antiguos."""
        return self.usuario.get_full_name().strip() or self.usuario.nombre_usuario

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
            models.CheckConstraint(condition=models.Q(tipo="DISPONIBILIDAD", estado__in=["DISPONIBLE", "CANCELADA"]) | models.Q(tipo="CITA", estado__in=["RESERVADA", "REALIZADA", "CANCELADA"]) | models.Q(tipo="BLOQUEO", estado__in=["BLOQUEADO", "CANCELADA"]), name="bloque_tipo_estado_valido"),
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
    class EstadoML(models.TextChoices):
        LEGADO = "LEGADO", "Sin trazabilidad previa"
        NO_SOLICITADO = "NO_SOLICITADO", "No solicitado"
        COMPLETADO = "COMPLETADO", "Completado"
        NO_DISPONIBLE = "NO_DISPONIBLE", "No disponible"

    abono_verificado_en = models.DateTimeField(null=True, blank=True)
    abono_verificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="abonos_verificados")
    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    estado_ml = models.CharField(max_length=20, choices=EstadoML.choices, default=EstadoML.LEGADO)
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.RESTRICT)
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

    class Meta:
        constraints = [
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
    apellidos = models.CharField(max_length=160, blank=True)
    correo = models.EmailField(max_length=254, null=True, blank=True)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[telefono_contacto])

    def __str__(self):
        return f"{self.nombres} {self.apellidos}".strip()


class Sesion(models.Model):
    """Única relación entre una reserva de agenda y una solicitud."""
    bloque = models.OneToOneField(BloqueHorario, primary_key=True, on_delete=models.RESTRICT, related_name="sesion")
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT, related_name="vinculos_sesiones")

    def clean(self):
        if self.bloque_id and self.postulacion_id:
            if self.bloque.tatuadora_id != self.postulacion.tatuadora_id or self.bloque.tipo != "CITA":
                raise ValidationError("La sesión debe vincular una cita y una solicitud de la misma tatuadora.")


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

class Prediccion(models.Model):
    imagen = models.ForeignKey(Imagen, on_delete=models.RESTRICT)
    version_modelo = models.CharField(max_length=120)
    estilo_sugerido = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    confianza_maxima = models.DecimalField(max_digits=17, decimal_places=16)
    umbral_confianza = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    tiempo_inferencia_ms = models.IntegerField()
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
    estilo = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    titulo = models.CharField(max_length=120)
    url = models.TextField()
    publicado_en = models.DateField()
    apto_entrenamiento = models.BooleanField(default=False)


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

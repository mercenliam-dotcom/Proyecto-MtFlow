
import uuid

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
    nombre = models.CharField(max_length=120)
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre_publico

    @property
    def nombre_publico(self):
        """El nombre vigente de la cuenta vinculada, incluso en perfiles antiguos."""
        return self.usuario.get_full_name().strip() or self.nombre

class BloqueHorario(models.Model):
    class Tipo(models.TextChoices):
        DISPONIBILIDAD = "DISPONIBILIDAD", "Disponible para trabajar"
        CITA = "CITA", "Sesión reservada"
        BLOQUEO = "BLOQUEO", "Bloqueo personal"

    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.DISPONIBILIDAD)
    postulacion = models.ForeignKey("Postulacion", null=True, blank=True, on_delete=models.RESTRICT, related_name="sesiones")
    nota = models.CharField(max_length=300, blank=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.CharField(max_length=15)

    class Meta:
        ordering = ["fecha", "hora_inicio", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(hora_inicio__lt=models.F("hora_fin")), name="bloque_intervalo_positivo")]
        indexes = [models.Index(fields=["tatuadora", "fecha", "estado"], name="agenda_busqueda")]

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
    cliente = models.ForeignKey(Cliente, on_delete=models.RESTRICT)
    tatuadora = models.ForeignKey(Tatuadora, on_delete=models.RESTRICT)
    bloque = models.OneToOneField(BloqueHorario, on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitud_principal")
    zona_cuerpo = models.CharField(max_length=100)
    alto_cm = models.DecimalField(max_digits=5, decimal_places=2)
    ancho_cm = models.DecimalField(max_digits=5, decimal_places=2)
    area_cm2 = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    categoria_tamano = models.CharField(max_length=10)
    presupuesto_estimado = models.IntegerField(null=True, blank=True)
    descripcion = models.TextField()
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

class Imagen(models.Model):
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT)
    url = models.TextField()
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

class ConfianzaEstilo(models.Model):
    prediccion = models.ForeignKey(Prediccion, on_delete=models.RESTRICT)
    estilo = models.ForeignKey(Estilo, on_delete=models.RESTRICT)
    confianza = models.DecimalField(max_digits=17, decimal_places=16)

    class Meta:
        unique_together = ('prediccion', 'estilo')

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
        nombre_completo = (instance.get_full_name().strip() or instance.nombre_usuario)[:120]

        # Habilitar la función en una cuenta existente también crea su perfil.
        # Deshabilitarla no elimina el perfil ni sus propuestas históricas.
        Tatuadora.objects.get_or_create(
            usuario=instance, defaults={"nombre": nombre_completo, "activa": True},
        )


class EventoSolicitud(models.Model):
    postulacion = models.ForeignKey(Postulacion, on_delete=models.RESTRICT, related_name="eventos")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=40)
    detalle = models.CharField(max_length=500, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-pk"]

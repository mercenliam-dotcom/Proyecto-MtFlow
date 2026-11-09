import uuid

from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from apps.nucleo.imagenes import validar_imagen, TIPOS_ACEPTADOS_HTML
from .models import Tatuadora
from .validadores import nombre_contacto, telefono_contacto, texto_sin_controles


def token_envio():
    return signing.dumps(str(uuid.uuid4()), salt="web.recepcion")

class CotizacionForm(forms.Form):
    envio = forms.CharField(widget=forms.HiddenInput, initial=token_envio)
    nombre = forms.CharField(label="Nombres", max_length=80, validators=[nombre_contacto], widget=forms.TextInput(attrs={"id": "client-name", "autocomplete": "name"}))
    primer_apellido = forms.CharField(label="Primer apellido", max_length=80, required=False, validators=[nombre_contacto])
    segundo_apellido = forms.CharField(label="Segundo apellido (opcional)", max_length=80, required=False, validators=[nombre_contacto])
    canal_preferido = forms.ChoiceField(label="Medio de contacto preferido", required=False, choices=[("correo", "Correo"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("tiktok", "TikTok")], initial="correo")
    usuario_social = forms.RegexField(r"^@?[A-Za-z0-9_.]{1,60}$", label="Usuario de Instagram o TikTok (opcional)", max_length=61, required=False)
    fecha_propuesta = forms.DateField(label="Fecha que propones (opcional)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hora_propuesta = forms.TimeField(label="Hora que propones (opcional)", required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    email = forms.EmailField(label="Correo electrónico", max_length=254, widget=forms.EmailInput(attrs={"id": "client-email", "autocomplete": "email"}))
    telefono = forms.CharField(label="Teléfono (opcional)", max_length=25, required=False, validators=[telefono_contacto], widget=forms.TextInput(attrs={"id": "client-phone", "type": "tel", "autocomplete": "tel"}))
    
    # 1. Selector dinámico conectado a la Base de Datos
    tatuadora = forms.ModelChoiceField(
        queryset=Tatuadora.objects.filter(activa=True, usuario__is_active=True, usuario__es_tatuadora=True).select_related('usuario').order_by('usuario__nombre', 'usuario__apellido', 'pk'),
        empty_label="Selecciona tu tatuadora",
        label="Tatuadora con quien quieres tatuarte",
        widget=forms.Select(attrs={"id": "quote-artist"}),
        required=True
    )
    
    zona = forms.ChoiceField(label="Zona del cuerpo", choices=[("", "Selecciona una zona"), ("brazo", "Brazo"), ("antebrazo", "Antebrazo"), ("pierna", "Pierna"), ("espalda", "Espalda"), ("pecho", "Pecho"), ("costillas", "Costillas"), ("otra", "Otra zona / por definir")], widget=forms.Select(attrs={"id": "body-zone"}))
    
    # 2. Reemplazo del combo por inputs numéricos reales
    alto_cm = forms.DecimalField(label="Alto (cm)", min_value=1, max_digits=5, decimal_places=2, widget=forms.NumberInput(attrs={"id": "tattoo-height", "placeholder": "Ej: 15.5"}))
    ancho_cm = forms.DecimalField(label="Ancho (cm)", min_value=1, max_digits=5, decimal_places=2, widget=forms.NumberInput(attrs={"id": "tattoo-width", "placeholder": "Ej: 10"}))
    
    color = forms.ChoiceField(label="Color", choices=[("negro", "Negro y grises"), ("color", "Con color")])
    detalle = forms.ChoiceField(label="Detalle que buscas", choices=[("normal", "Simple o intermedio"), ("alto", "Alto: muchos elementos o trazos")])
    idea = forms.CharField(label="Cuéntanos tu idea", max_length=1500, validators=[texto_sin_controles], widget=forms.Textarea(attrs={"id": "idea", "rows": 4, "placeholder": "Motivo, ubicación y detalles que imaginas…"}))
    cobertura = forms.BooleanField(label="Quiero cubrir un tatuaje existente", required=False)
    imagen = forms.FileField(label="Imagen de referencia", help_text="JPG o PNG · máximo 10 MB · mínimo 224 píxeles por lado.", widget=forms.FileInput(attrs={"id": "reference", "accept": TIPOS_ACEPTADOS_HTML}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        self.fields["fecha_propuesta"].widget.attrs["min"] = timezone.localdate().isoformat()
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "form-control"

    def clean_envio(self):
        try:
            return uuid.UUID(signing.loads(self.cleaned_data["envio"], salt="web.recepcion", max_age=86400))
        except (signing.BadSignature, ValueError, TypeError):
            raise ValidationError("El formulario venció o no es válido. Recarga la página antes de enviar.")

    def clean(self):
        datos = super().clean()
        datos["analizar"] = True  # Obligatorio: nunca confiar en un interruptor del navegador.
        if not self.fields["tatuadora"].queryset.exists():
            raise ValidationError("No hay tatuadoras habilitadas para recibir propuestas en este momento. Inténtalo más tarde.")
        from datetime import datetime
        from django.forms.utils import from_current_timezone
        from django.utils import timezone
        if bool(datos.get("fecha_propuesta")) != bool(datos.get("hora_propuesta")):
            raise ValidationError("Para proponer un horario, completa fecha y hora. No representa una reserva.")
        if datos.get("fecha_propuesta") and datos.get("hora_propuesta"):
            if from_current_timezone(datetime.combine(datos["fecha_propuesta"], datos["hora_propuesta"])) <= timezone.now():
                self.add_error("fecha_propuesta", "Propón una fecha y hora futuras.")
            elif datos.get("tatuadora"):
                from .disponibilidad import hora_disponible
                if not hora_disponible(datos["tatuadora"], datos["fecha_propuesta"], datos["hora_propuesta"]):
                    self.add_error("hora_propuesta", "Esa hora no está disponible dentro del horario de trabajo. Elige otra o envía sin proponer horario.")
        if datos.get("canal_preferido") == "whatsapp" and not datos.get("telefono"):
            self.add_error("telefono", "Indica el teléfono en el que quieres recibir contacto.")
        if datos.get("canal_preferido") in ("instagram", "tiktok") and not datos.get("usuario_social"):
            datos["canal_preferido"] = "correo"  # Sin usuario social, el correo obligatorio permite contactar.
        return datos

    def clean_imagen(self):
        self.validada = validar_imagen(self.cleaned_data["imagen"])
        return self.validada.archivo

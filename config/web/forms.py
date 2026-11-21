import uuid

from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from apps.nucleo.imagenes import validar_imagen, TIPOS_ACEPTADOS_HTML
from .models import Tatuadora
from . import imagen_pendiente as pendientes
from .campos import FechaEspejoInput, NombrePersonaField, TelefonoChileField, TelefonoChileInput
from .validadores import nombre_contacto, texto_sin_controles


def token_envio():
    return signing.dumps(str(uuid.uuid4()), salt="web.recepcion")

class CotizacionForm(forms.Form):
    envio = forms.CharField(widget=forms.HiddenInput, initial=token_envio)
    nombre = NombrePersonaField(label="Nombres", validators=[nombre_contacto], widget=forms.TextInput(attrs={"id": "client-name", "autocomplete": "given-name"}))
    primer_apellido = NombrePersonaField(label="Primer apellido", required=False, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    segundo_apellido = NombrePersonaField(label="Segundo apellido (opcional)", required=False)
    canal_preferido = forms.ChoiceField(label="Medio de contacto preferido", required=False, choices=[("correo", "Correo"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("tiktok", "TikTok")], initial="correo")
    usuario_social = forms.RegexField(r"^@?[A-Za-z0-9_.]{1,60}$", label="Usuario de Instagram o TikTok (opcional)", max_length=61, required=False,
                                      error_messages={"invalid": "Usa solo letras, números, punto o guion bajo, sin espacios (por ejemplo @maria.tattoo)."},
                                      widget=forms.TextInput(attrs={"data-solo": "social", "autocomplete": "off", "spellcheck": "false"}))
    fecha_propuesta = forms.DateField(label="Fecha que propones (opcional)", required=False, widget=FechaEspejoInput)
    hora_propuesta = forms.TimeField(label="Hora que propones (opcional)", required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    email = forms.EmailField(label="Correo electrónico", max_length=254, widget=forms.EmailInput(attrs={"id": "client-email", "autocomplete": "email"}))
    telefono = TelefonoChileField(label="Teléfono (opcional)", required=False, widget=TelefonoChileInput(attrs={"id": "client-phone"}))
    
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
    imagen = forms.FileField(label="Imagen de referencia", required=False, help_text="JPG o PNG · máximo 10 MB · mínimo 224 píxeles por lado.", widget=forms.FileInput(attrs={"id": "reference", "accept": TIPOS_ACEPTADOS_HTML}))
    # Token de la imagen ya subida en esta sesión (ver web/imagen_pendiente.py): conserva
    # la imagen entre envíos fallidos hasta que se envíe, se quite o se reemplace.
    imagen_pendiente = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput(attrs={"id": "imagen-pendiente"}))

    # Con sesión de cliente, estos datos salen de su cuenta y no se pueden cambiar en el envío.
    CAMPOS_DE_CUENTA = ("nombre", "primer_apellido", "segundo_apellido", "email", "telefono", "canal_preferido", "usuario_social")

    def __init__(self, *args, cuenta=None, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cuenta = cuenta
        self.request = request
        self.validada = None
        self.token_pendiente = ""
        if cuenta is not None:
            # disabled: Django ignora lo que llegue en el POST y usa el valor inicial (el de la cuenta).
            for nombre in self.CAMPOS_DE_CUENTA:
                self.fields[nombre].disabled = True
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
            if self.cuenta is not None:
                self.add_error(None, "Tu perfil indica WhatsApp como medio de contacto, pero no tiene teléfono. Agrégalo en «Mi perfil» y vuelve a enviar.")
            else:
                self.add_error("telefono", "Indica el teléfono en el que quieres recibir contacto.")
        if datos.get("canal_preferido") in ("instagram", "tiktok") and not datos.get("usuario_social"):
            datos["canal_preferido"] = "correo"  # Sin usuario social, el correo obligatorio permite contactar.
        return datos

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if self.cuenta is not None:
            return email  # el de la cuenta
        from apps.cuentas.verificacion_correo import validar_dominio_correo
        validar_dominio_correo(email)
        return email

    def clean_imagen(self):
        archivo = self.cleaned_data.get("imagen")
        if not archivo:
            return None
        self.validada = validar_imagen(archivo)
        if self.request is not None:
            # Se guarda ya, aunque otro campo falle: el reintento no pide la imagen de nuevo.
            self.token_pendiente = pendientes.guardar(self.request, self.validada)
        return self.validada.archivo

    def clean_imagen_pendiente(self):
        token = self.cleaned_data.get("imagen_pendiente", "")
        if self.validada is None and token and self.request is not None:
            self.validada = pendientes.cargar(self.request, token)
            if self.validada is not None:
                self.token_pendiente = token
        if self.validada is None and "imagen" not in self.errors:
            self.add_error("imagen", "Selecciona una imagen JPG o PNG para tu referencia.")
        if self.token_pendiente and self.token_pendiente != token:
            # El reintento mostrará y enviará el token nuevo.
            self.data = self.data.copy()
            self.data["imagen_pendiente"] = self.token_pendiente
        return self.token_pendiente

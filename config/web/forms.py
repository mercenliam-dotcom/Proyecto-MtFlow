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
    nombre = forms.CharField(label="Nombre o alias", max_length=80, validators=[nombre_contacto], widget=forms.TextInput(attrs={"id": "client-name", "autocomplete": "name"}))
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
    analizar = forms.BooleanField(label="Analizar el estilo al seleccionar la imagen", required=False, initial=True,
                                 help_text="La imagen se procesa con el servicio de análisis configurado por el estudio. La tatuadora revisará la sugerencia antes de acordar tu sesión.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        if not self.fields["tatuadora"].queryset.exists():
            raise ValidationError("No hay tatuadoras habilitadas para recibir propuestas en este momento. Inténtalo más tarde.")
        return datos

    def clean_imagen(self):
        self.validada = validar_imagen(self.cleaned_data["imagen"])
        return self.validada.archivo

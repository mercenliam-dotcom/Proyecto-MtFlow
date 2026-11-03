from django import forms
from apps.nucleo.imagenes import validar_imagen, TIPOS_ACEPTADOS_HTML


class CotizacionForm(forms.Form):
    nombre = forms.CharField(label="Nombre o alias", max_length=80, widget=forms.TextInput(attrs={"id": "client-name", "autocomplete": "name"}))
    email = forms.EmailField(label="Correo electrónico", max_length=150, widget=forms.EmailInput(attrs={"id": "client-email", "autocomplete": "email"}))
    telefono = forms.CharField(label="Teléfono (opcional)", max_length=25, required=False, widget=forms.TextInput(attrs={"id": "client-phone", "type": "tel", "autocomplete": "tel"}))
    tatuadora = forms.ChoiceField(label="Preferencia de tatuadora", choices=[("", "Selecciona una opción"), ("cualquiera", "Cualquiera de las dos"), ("1", "Tatuadora 1"), ("2", "Tatuadora 2")], widget=forms.Select(attrs={"id": "quote-artist"}))
    zona = forms.ChoiceField(label="Zona del cuerpo", choices=[("", "Selecciona una zona"), ("brazo", "Brazo"), ("antebrazo", "Antebrazo"), ("pierna", "Pierna"), ("espalda", "Espalda"), ("pecho", "Pecho"), ("costillas", "Costillas"), ("otra", "Otra zona / por definir")], widget=forms.Select(attrs={"id": "body-zone"}))
    tamano = forms.ChoiceField(label="Tamaño del lado mayor", choices=[("", "Selecciona un tamaño"), ("pequeno", "Hasta 5 cm"), ("mediano", "Más de 5 y hasta 15 cm"), ("grande", "Más de 15 y hasta 25 cm"), ("especial", "Más de 25 cm / por definir")], widget=forms.Select(attrs={"id": "tattoo-size"}))
    color = forms.ChoiceField(label="Color", choices=[("negro", "Negro y grises"), ("color", "Con color")])
    detalle = forms.ChoiceField(label="Detalle que buscas", choices=[("normal", "Simple o intermedio"), ("alto", "Alto: muchos elementos o trazos")])
    idea = forms.CharField(label="Cuéntanos tu idea", max_length=1500, widget=forms.Textarea(attrs={"id": "idea", "rows": 4, "placeholder": "Motivo, ubicación y detalles que imaginas…"}))
    cobertura = forms.BooleanField(label="Quiero cubrir un tatuaje existente", required=False)
    imagen = forms.FileField(label="Imagen de referencia", help_text="JPG o PNG · máximo 5 MB · mínimo 224 píxeles por lado.", widget=forms.FileInput(attrs={"id": "reference", "accept": TIPOS_ACEPTADOS_HTML}))
    analizar = forms.BooleanField(label="Quiero analizar el estilo con Roboflow", required=False,
        help_text="Si marcas esta opción, enviaremos la imagen sin metadatos al servicio de análisis, que puede usar Roboflow. No enviamos tu nombre, correo ni teléfono. Es opcional y no autoriza publicación ni entrenamiento.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "form-control"

    def clean_imagen(self):
        self.validada = validar_imagen(self.cleaned_data["imagen"])
        return self.validada.archivo

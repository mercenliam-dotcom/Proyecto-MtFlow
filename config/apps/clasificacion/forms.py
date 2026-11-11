from django import forms

from apps.nucleo.imagenes import TIPOS_ACEPTADOS_HTML, validar_imagen, configurar_campo_imagen


class ImagenReferenciaForm(forms.Form):
    """
    Solo un campo de ARCHIVO. No existe ningún campo para pegar una URL:
    el sistema nunca descarga contenido desde direcciones que escriba el
    usuario, así que no se pueden "inyectar" videos ni páginas externas.
    """
    imagen = forms.FileField(
        label="Imagen de referencia",
        help_text="Solo JPG o PNG, máximo 10 MB, al menos 224 píxeles por lado.",
        widget=forms.FileInput(attrs={"accept": TIPOS_ACEPTADOS_HTML}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configurar_campo_imagen(self.fields["imagen"])

    def clean_imagen(self):
        self.validada = validar_imagen(self.cleaned_data["imagen"])
        return self.validada.archivo

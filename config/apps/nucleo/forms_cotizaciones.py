from django import forms

from web.models import Tatuadora


class FiltrosEquipo(forms.Form):
    tatuadora = forms.ChoiceField(label="Tatuadora", required=False)
    estado = forms.ChoiceField(label="Estado", required=False)
    desde = forms.DateField(label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, propuestas, estados, **kwargs):
        super().__init__(*args, **kwargs)
        tatuadoras = Tatuadora.objects.filter(postulacion__in=propuestas).select_related("usuario").distinct().order_by("usuario__nombre", "usuario__apellido", "pk")
        self.fields["tatuadora"].choices = [("", "Todas las tatuadoras")] + [(str(t.usuario.uuid), t.nombre_publico) for t in tatuadoras]
        self.fields["estado"].choices = [("", "Todos los estados")] + estados

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha de término.")
        return datos

    def filtrar(self, propuestas):
        datos = self.cleaned_data
        if datos.get("tatuadora"):
            propuestas = propuestas.filter(tatuadora__usuario__uuid=datos["tatuadora"])
        if datos.get("estado"):
            propuestas = propuestas.filter(estado=datos["estado"])
        if datos.get("desde"):
            propuestas = propuestas.filter(creada_en__date__gte=datos["desde"])
        if datos.get("hasta"):
            propuestas = propuestas.filter(creada_en__date__lte=datos["hasta"])
        return propuestas

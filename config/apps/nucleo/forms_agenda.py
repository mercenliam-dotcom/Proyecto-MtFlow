from datetime import datetime

from django import forms
from django.forms.utils import from_current_timezone
from django.utils import timezone
from web.models import BloqueHorario, Postulacion


class BloqueForm(forms.Form):
    tipo = forms.ChoiceField(label="Qué quieres agendar", choices=BloqueHorario.Tipo.choices)
    fecha = forms.DateField(label="Fecha", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hora_inicio = forms.TimeField(label="Inicio", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    hora_fin = forms.TimeField(label="Término", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    postulacion = forms.ModelChoiceField(label="Solicitud (solo para sesiones)", queryset=Postulacion.objects.none(), required=False)
    nota = forms.CharField(label="Nota interna / motivo del cambio", max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    version = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, tatuadora, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["postulacion"].queryset = Postulacion.objects.filter(
            tatuadora=tatuadora, estado__in=["ACEPTADA", "RESERVADA"],
            abono_verificado_en__isnull=False, monto_abono__gt=0,
        ).select_related("cliente").order_by("-creada_en")
        self.fields["postulacion"].label_from_instance = lambda p: f"{p.cliente.nombres} · {p.referencia.hex[:8]}"

    def clean(self):
        d = super().clean()
        if d.get("tipo") == "CITA" and not d.get("postulacion"):
            self.add_error("postulacion", "Selecciona una solicitud aceptada con abono verificado.")
        if d.get("tipo") != "CITA" and d.get("postulacion"):
            self.add_error("postulacion", "Solo las sesiones se asocian a una solicitud.")
        if all(d.get(k) for k in ("fecha", "hora_inicio", "hora_fin")):
            if d["hora_inicio"] >= d["hora_fin"]:
                self.add_error("hora_fin", "El término debe ser posterior al inicio, dentro del mismo día.")
            try:
                inicio = from_current_timezone(datetime.combine(d["fecha"], d["hora_inicio"]))
                from_current_timezone(datetime.combine(d["fecha"], d["hora_fin"]))
                if inicio <= timezone.now():
                    self.add_error("fecha", "Elige una fecha y hora futuras.")
            except forms.ValidationError:
                self.add_error("hora_inicio", "Horario ambiguo o inexistente por el cambio de hora en Chile.")
        return d


class GestionForm(forms.Form):
    accion = forms.ChoiceField(label="Acción", choices=[("revisar", "Marcar en revisión"), ("aceptar", "Registrar acuerdo y aceptar"), ("abono", "Registrar abono verificado"), ("rechazar", "Rechazar solicitud")])
    precio_final = forms.IntegerField(label="Precio total acordado (CLP)", min_value=1, max_value=100000000, required=False)
    monto_abono = forms.IntegerField(label="Abono recibido acumulado (CLP)", min_value=1, max_value=100000000, required=False)
    verificado = forms.BooleanField(label="Verifiqué el pago recibido fuera de la plataforma", required=False)
    motivo = forms.CharField(label="Observación / motivo de rechazo", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, solicitud=None, **kwargs):
        super().__init__(*args, **kwargs)
        if solicitud is not None:
            permitidas = []
            if solicitud.estado == "RECIBIDA":
                permitidas.append("revisar")
            if solicitud.estado in ("RECIBIDA", "EN_REVISION", "ACEPTADA"):
                permitidas.append("aceptar")
                if not solicitud.abono_verificado_en:
                    permitidas.append("rechazar")
            if solicitud.estado in ("ACEPTADA", "RESERVADA"):
                permitidas.append("abono")
            self.fields["accion"].choices = [(k, v) for k, v in self.fields["accion"].choices if k in permitidas]
            self.initial.update(precio_final=solicitud.precio_final, monto_abono=solicitud.monto_abono)

    def clean(self):
        d = super().clean()
        if d.get("accion") == "aceptar" and not d.get("precio_final"):
            self.add_error("precio_final", "Indica el precio acordado con el cliente.")
        if d.get("accion") == "abono" and (not d.get("monto_abono") or not d.get("verificado")):
            raise forms.ValidationError("Indica el abono y confirma que lo verificaste. Aquí no se procesan pagos.")
        if d.get("accion") == "rechazar" and not d.get("motivo"):
            self.add_error("motivo", "Registra el motivo; la solicitud se conserva en el historial.")
        return d

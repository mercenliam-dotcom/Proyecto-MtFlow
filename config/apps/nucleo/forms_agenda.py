from datetime import datetime

from django import forms
from django.forms.utils import from_current_timezone
from django.utils import timezone
from web.validadores import texto_sin_controles
from web.models import BloqueHorario, Postulacion


class BloqueForm(forms.Form):
    tipo = forms.ChoiceField(label="Qué quieres agendar", choices=BloqueHorario.Tipo.choices)
    fecha = forms.DateField(label="Fecha", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hora_inicio = forms.TimeField(label="Inicio", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    hora_fin = forms.TimeField(label="Término", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    postulacion = forms.ModelChoiceField(label="Solicitud (solo para sesiones)", queryset=Postulacion.objects.none(), required=False)
    nota = forms.CharField(label="Nota interna / motivo del cambio", max_length=300, required=False, validators=[texto_sin_controles], widget=forms.Textarea(attrs={"rows": 2}))
    version = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, tatuadora, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.fields["tipo"].choices = [("DISPONIBILIDAD", "Horario excepcional de una fecha"), ("CITA", "Sesión reservada"), ("BLOQUEO", "Bloqueo personal")]
        from django.db.models import Q
        self.fields["postulacion"].queryset = Postulacion.objects.filter(
            tatuadora=tatuadora, estado__in=["ACEPTADA", "RESERVADA"],
        ).filter(Q(abono_verificado_en__isnull=False, monto_abono__gt=0) | Q(movimientos__tipo="PAGO")).distinct().select_related("contacto").order_by("-creada_en")
        self.fields["postulacion"].label = "Solicitud del cliente"
        self.fields["postulacion"].help_text = "No necesitas una sesión previa: este formulario crea la primera sesión de una solicitud con pago registrado."
        self.fields["postulacion"].label_from_instance = lambda p: f"{p.contacto.nombres} · {p.referencia.hex[:8]}"

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
    version = forms.CharField(required=False, widget=forms.HiddenInput)
    accion = forms.ChoiceField(label="Acción", choices=[("revisar", "Marcar en revisión"), ("aceptar", "Registrar acuerdo y aceptar"), ("abono", "Registrar abono verificado"), ("rechazar", "Rechazar solicitud")])
    precio_final = forms.IntegerField(label="Precio total acordado (CLP)", min_value=1, max_value=100000000, required=False)
    abono_solicitado = forms.IntegerField(label="Abono que se solicita (CLP)", min_value=1, max_value=100000000, required=False)
    alto_final_cm = forms.DecimalField(label="Alto final acordado (cm)", min_value=1, max_digits=5, decimal_places=2, required=False)
    ancho_final_cm = forms.DecimalField(label="Ancho final acordado (cm)", min_value=1, max_digits=5, decimal_places=2, required=False)
    monto_abono = forms.IntegerField(label="Abono recibido acumulado (CLP)", min_value=1, max_value=100000000, required=False)
    verificado = forms.BooleanField(label="Verifiqué el pago recibido fuera de la plataforma", required=False)
    motivo = forms.CharField(label="Observación / motivo de rechazo", max_length=500, required=False, validators=[texto_sin_controles], widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, solicitud=None, accion=None, **kwargs):
        super().__init__(*args, **kwargs)
        if solicitud is not None:
            self.fields["version"].required = True
            self.initial["version"] = solicitud.actualizada_en.isoformat()
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
            self.initial.update(precio_final=solicitud.precio_final, monto_abono=solicitud.monto_abono, abono_solicitado=solicitud.abono_solicitado, alto_final_cm=solicitud.alto_final_cm, ancho_final_cm=solicitud.ancho_final_cm)
        if accion:
            self.initial["accion"] = accion
            if accion != "rechazar":
                self.fields["motivo"].label = "Observación o referencia del comprobante (opcional)" if accion == "abono" else "Observación del acuerdo (opcional)"
            if accion == "abono":
                self.fields["monto_abono"].help_text = "Si ya registraste parte del abono aquí, escribe el total acumulado; no vuelvas a sumar un pago registrado por otra opción."
            self.fields["accion"].widget = forms.HiddenInput()
            campos = {"aceptar": {"precio_final", "abono_solicitado", "alto_final_cm", "ancho_final_cm", "motivo"},
                      "abono": {"monto_abono", "verificado", "motivo"}, "revisar": set(), "rechazar": {"motivo"}}
            for nombre in list(self.fields):
                if nombre not in campos.get(accion, set()) | {"version", "accion"}:
                    del self.fields[nombre]

    def clean(self):
        d = super().clean()
        if d.get("accion") == "aceptar" and not d.get("precio_final"):
            self.add_error("precio_final", "Indica el precio acordado con el cliente.")
        if d.get("accion") == "abono" and (not d.get("monto_abono") or not d.get("verificado")):
            raise forms.ValidationError("Indica el abono y confirma que lo verificaste. Aquí no se procesan pagos.")
        if d.get("accion") == "rechazar" and not d.get("motivo"):
            self.add_error("motivo", "Registra el motivo; la solicitud se conserva en el historial.")
        return d

from datetime import datetime, time, date
from django import forms
from django.forms.utils import from_current_timezone
from django.utils import timezone
from web.validadores import texto_sin_controles
from web.models import BloqueHorario, Postulacion

def parse_hora(v):
    """Convierte de forma segura el valor del select a un objeto time."""
    if isinstance(v, time):
        return v
    if isinstance(v, str) and v:
        return datetime.strptime(v[:5], "%H:%M").time()
    return v

# Generamos opciones de 30 en 30 minutos para el menú desplegable
# El valor es texto "HH:MM" (lo que envía el navegador); parse_hora lo convierte a time.
OPCIONES_HORA = [(f"{h:02d}:{m:02d}", f"{h:02d}:{m:02d}") for h in range(9, 21) for m in (0, 30)]

def _cm(valor):
    """10.00 -> "10"; 10.50 -> "10,5"."""
    return format(valor.normalize(), "f").replace(".", ",") if valor is not None else "?"


class HoraField(forms.TypedChoiceField):
    """Menú de horas cada 30 min. Acepta "HH:MM", "HH:MM:SS" o un time; el control de
    choques lo hace guardar_bloque, así que cualquier hora válida del día se admite."""
    def to_python(self, value):
        if isinstance(value, time):
            return value.strftime("%H:%M")
        return super().to_python(value)

    def valid_value(self, value):
        try:
            datetime.strptime(str(value)[:5], "%H:%M")
            return True
        except ValueError:
            return False


class BloqueForm(forms.Form):
    tipo = forms.ChoiceField(label="Qué quieres agendar", choices=BloqueHorario.Tipo.choices)
    fecha = forms.DateField(label="Fecha (DD/MM/AAAA)", input_formats=["%d/%m/%Y", "%Y-%m-%d"], widget=forms.DateInput(attrs={"placeholder": "DD/MM/AAAA", "inputmode": "numeric", "pattern": r"[0-9]{2}/[0-9]{2}/[0-9]{4}"}, format="%d/%m/%Y"))
    
    hora_inicio = HoraField(label="Inicio", choices=OPCIONES_HORA, coerce=parse_hora, widget=forms.Select)
    hora_fin = HoraField(label="Término", choices=OPCIONES_HORA, coerce=parse_hora, widget=forms.Select)
    
    postulacion = forms.ModelChoiceField(label="Solicitud (solo para sesiones)", queryset=Postulacion.objects.none(), required=False)
    nota = forms.CharField(label="Nota interna / motivo del cambio", max_length=300, required=False, validators=[texto_sin_controles], widget=forms.Textarea(attrs={"rows": 2}))
    version = forms.CharField(required=False, widget=forms.HiddenInput)
    # NUEVO: Guardamos el ID de la referencia actual si estamos editando
    referencia_actual = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, tatuadora, referencia_actual=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.fields["tipo"].choices = [("DISPONIBILIDAD", "Horario excepcional de una fecha"), ("CITA", "Sesión reservada"), ("BLOQUEO", "Bloqueo personal")]
        
        # Si nos pasan la referencia al instanciar el formulario, la guardamos
        if referencia_actual:
            self.initial["referencia_actual"] = str(referencia_actual)
            
        from django.db.models import Q
        self.fields["postulacion"].queryset = Postulacion.objects.filter(
            tatuadora=tatuadora, estado__in=["ACEPTADA", "RESERVADA"],
        ).filter(Q(abono_verificado_en__isnull=False, monto_abono__gt=0) | Q(movimientos__tipo="PAGO")).distinct().select_related("contacto").order_by("-creada_en")
        self.fields["postulacion"].label = "Solicitud del cliente"
        self.fields["postulacion"].help_text = "No necesitas una sesión previa: este formulario crea la primera sesión de una solicitud con pago registrado."
        self.fields["postulacion"].label_from_instance = lambda p: f"{p.contacto} · {(p.zona_cuerpo or '').capitalize()} {_cm(p.alto_cm)}×{_cm(p.ancho_cm)} cm · {p.estado_comercial.lower()} · {p.codigo}"

        # --- FILTRO DINÁMICO DE HORAS OCUPADAS ---
        fecha_val = None
        if self.is_bound and self.data.get("fecha"):
            fecha_str = self.data.get("fecha")
        else:
            fecha_str = self.initial.get("fecha")
        
        if isinstance(fecha_str, str):
            try:
                fecha_val = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    fecha_val = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                except ValueError:
                    pass
        elif isinstance(fecha_str, datetime):
            fecha_val = fecha_str.date()
        elif isinstance(fecha_str, date):
            fecha_val = fecha_str

        # Extraer referencia actual desde los datos si existe
        ref_actual = None
        if self.is_bound and self.data.get("referencia_actual"):
            ref_actual = self.data.get("referencia_actual")
        elif self.initial.get("referencia_actual"):
            ref_actual = self.initial.get("referencia_actual")

        opciones_inicio = []
        opciones_fin = []
        
        if fecha_val:
            # Traemos las citas de la tatuadora
            query_citas = BloqueHorario.objects.filter(
                tatuadora=tatuadora, 
                fecha=fecha_val,
                estado__in=["RESERVADA", "REALIZADA", "BLOQUEADO"]
            )
            
            # NUEVO: Si estamos editando, excluimos EL BLOQUE ACTUAL de la consulta de ocupación
            if ref_actual:
                query_citas = query_citas.exclude(referencia=ref_actual)
                
            citas = list(query_citas)
            
            # Recorremos cada hora posible del menú desplegable
            for valor, label in OPCIONES_HORA:
                t_obj = parse_hora(valor)
                minutos_actual = t_obj.hour * 60 + t_obj.minute
                libre_para_inicio = True
                libre_para_fin = True
                
                for cita in citas:
                    inicio_m = cita.hora_inicio.hour * 60 + cita.hora_inicio.minute
                    fin_m = cita.hora_fin.hour * 60 + cita.hora_fin.minute
                    
                    if inicio_m <= minutos_actual < fin_m:
                        libre_para_inicio = False
                    if inicio_m < minutos_actual <= fin_m:
                        libre_para_fin = False
                        
                if libre_para_inicio:
                    opciones_inicio.append((valor, label))
                if libre_para_fin:
                    opciones_fin.append((valor, label))
                    
            self.fields["hora_inicio"].choices = opciones_inicio or OPCIONES_HORA
            self.fields["hora_fin"].choices = opciones_fin or OPCIONES_HORA

    def clean(self):
        d = super().clean()
        
        # Convertimos el texto a Hora real si viene como String
        for campo in ["hora_inicio", "hora_fin"]:
            valor = d.get(campo)
            if isinstance(valor, str) and valor:
                try:
                    d[campo] = datetime.strptime(valor, "%H:%M").time()
                except ValueError:
                    pass
        
        if d.get("tipo") == "CITA" and not d.get("postulacion"):
            self.add_error("postulacion", "Selecciona una solicitud aceptada con abono verificado.")
        if d.get("tipo") != "CITA" and d.get("postulacion"):
            self.add_error("postulacion", "Solo las sesiones se asocian a una solicitud.")
            
        if all(d.get(k) for k in ("fecha", "hora_inicio", "hora_fin")):
            if d["hora_inicio"] >= d["hora_fin"]:
                self.add_error("hora_fin", "El término debe ser posterior al inicio, dentro del mismo día.")
            else:
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
            self.initial.update(precio_final=solicitud.precio_final, monto_abono=solicitud.monto_abono or solicitud.abono_solicitado, abono_solicitado=solicitud.abono_solicitado, alto_final_cm=solicitud.alto_final_cm, ancho_final_cm=solicitud.ancho_final_cm)
        if accion:
            self.initial["accion"] = accion
            if accion != "rechazar":
                self.fields["motivo"].label = "Observación o referencia del comprobante (opcional)" if accion == "abono" else "Observación del acuerdo (opcional)"
            if accion == "abono":
                self.fields["monto_abono"].help_text = "Si ya registraste parte del abono aquí, escribe el total acumulado; no vuelvas a sumar un pago registrado por otra opción."
                if solicitud is not None and solicitud.precio_final:
                    from .operaciones_agenda import rango_abono, _clp
                    minimo, maximo = rango_abono(solicitud.precio_final)
                    self.fields["monto_abono"].help_text = f"Debe ser entre 30 % y 40 % del precio acordado ({_clp(solicitud.precio_final)}): entre {_clp(minimo)} y {_clp(maximo)} CLP. " + self.fields["monto_abono"].help_text
                    self.fields["monto_abono"].widget.attrs.update(min=minimo, max=maximo)
            if accion == "aceptar":
                self.fields["abono_solicitado"].help_text = "Entre 30 % y 40 % del precio total acordado."
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
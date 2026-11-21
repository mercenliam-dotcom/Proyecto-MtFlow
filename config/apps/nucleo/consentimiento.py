"""Consentimiento informado de cada trabajo, firmado en la cuenta de la tatuadora.

Dos firmas separadas, en este orden:
1. Ficha del cliente: la completa y la firma el cliente (nombre escrito), en el estudio.
2. Declaración de la tatuadora: higiene, material estéril y riesgos explicados.

Sin ambas firmas no se puede marcar una sesión como realizada ni terminar el trabajo.
"""
import unicodedata
from datetime import date

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.consentimiento import DECLARACION_TATUADORA, SECCIONES, VERSION
from web.models import Consentimiento, EventoSolicitud, Postulacion
from web.campos import FechaField, NombrePersonaField
from web.validadores import texto_sin_controles
from .agenda import profesional

EDAD_MINIMA = 18
FALTA_CONSENTIMIENTO = ("Antes de marcar la sesión como realizada, completa el consentimiento de este trabajo: "
                        "la ficha firmada por el cliente y tu declaración.")


def _normalizar(texto):
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


def _edad(nacimiento, hoy):
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def firmar_por_sistema(postulacion, usuario, nacimiento, firma_cliente):
    """Registra ambas firmas de una vez. Solo para datos de demostración y pruebas;
    en el estudio se firma desde la página del consentimiento."""
    ahora = timezone.now()
    return Consentimiento.objects.update_or_create(postulacion=postulacion, defaults={
        "version_texto": VERSION, "fecha_nacimiento": nacimiento, "firma_cliente": firma_cliente,
        "cliente_firmo_en": ahora, "registrado_por": usuario,
        "firma_tatuadora": usuario.get_full_name(), "tatuadora_firmo_en": ahora,
    })[0]


def consentimiento_completo(postulacion):
    c = Consentimiento.objects.filter(postulacion=postulacion).first()
    return bool(c and c.completo)


class FichaClienteForm(forms.Form):
    fecha_nacimiento = FechaField(label="Fecha de nacimiento")
    alergias = forms.CharField(label="Alergias conocidas", max_length=500, required=False, validators=[texto_sin_controles],
                               widget=forms.Textarea(attrs={"rows": 2}), help_text="Tintas, látex, metales, anestésicos u otras. Déjalo vacío si no tienes.")
    condiciones = forms.CharField(label="Condiciones médicas", max_length=500, required=False, validators=[texto_sin_controles],
                                  widget=forms.Textarea(attrs={"rows": 2}), help_text="Diabetes, problemas de coagulación, epilepsia, corazón, piel u otras.")
    medicamentos = forms.CharField(label="Medicamentos que tomas", max_length=500, required=False, validators=[texto_sin_controles],
                                   widget=forms.Textarea(attrs={"rows": 2}), help_text="En especial anticoagulantes o tratamientos para la piel.")
    embarazo = forms.BooleanField(label="Estoy embarazada o en período de lactancia", required=False)
    alcohol_24h = forms.BooleanField(label="Consumí alcohol en las últimas 24 horas", required=False)
    autoriza_fotos = forms.BooleanField(label="Autorizo publicar fotos de mi tatuaje en el portafolio (opcional)", required=False)
    acepta = forms.BooleanField(label=f"Leí el consentimiento informado (versión {VERSION}), entiendo sus riesgos y cuidados, y declaro que mis respuestas son verdaderas")
    firma = NombrePersonaField(label="Firma: escribe tu nombre completo", max_length=160, widget=forms.TextInput(attrs={"autocomplete": "off"}))

    def clean_fecha_nacimiento(self):
        nacimiento = self.cleaned_data["fecha_nacimiento"]
        hoy = timezone.localdate()
        if nacimiento >= hoy or nacimiento < date(hoy.year - 120, 1, 1):
            raise ValidationError("Revisa la fecha de nacimiento.")
        if _edad(nacimiento, hoy) < EDAD_MINIMA:
            raise ValidationError(f"Solo realizamos tatuajes a mayores de {EDAD_MINIMA} años.")
        return nacimiento

    def clean_firma(self):
        firma = " ".join(self.cleaned_data["firma"].split())
        if len(firma.split()) < 2:
            raise ValidationError("Escribe nombre y apellido.")
        return firma

    def clean_alcohol_24h(self):
        if self.cleaned_data["alcohol_24h"]:
            raise ValidationError("Con consumo de alcohol en las últimas 24 horas no se puede realizar la sesión. Reprográmala.")
        return False


class DeclaracionTatuadoraForm(forms.Form):
    firma = NombrePersonaField(label="Firma: escribe tu nombre completo", max_length=160, widget=forms.TextInput(attrs={"autocomplete": "off"}))

    def __init__(self, *args, tatuadora=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tatuadora = tatuadora
        # Una casilla obligatoria por punto de la declaración, antes de la firma.
        casillas = {clave: forms.BooleanField(label=texto) for clave, texto in DECLARACION_TATUADORA}
        self.fields = {**casillas, "firma": self.fields["firma"]}

    def clean_firma(self):
        firma = " ".join(self.cleaned_data["firma"].split())
        esperado = self.tatuadora.usuario.get_full_name().strip() if self.tatuadora else ""
        if esperado and _normalizar(firma) != _normalizar(esperado):
            raise ValidationError(f"Escribe tu nombre tal como aparece en tu cuenta: «{esperado}».")
        return firma


@rol_requerido(Rol.ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def firmar(request, referencia):
    artista = profesional(request)
    p = get_object_or_404(Postulacion.objects.select_related("contacto"), referencia=referencia, tatuadora=artista)
    c = Consentimiento.objects.filter(postulacion=p).first()
    abierta = p.estado in ("ACEPTADA", "RESERVADA")
    ficha = FichaClienteForm(request.POST if request.method == "POST" and request.POST.get("parte") == "cliente" else None, prefix="cliente")
    declaracion = DeclaracionTatuadoraForm(request.POST if request.method == "POST" and request.POST.get("parte") == "tatuadora" else None,
                                           tatuadora=artista, prefix="tatuadora")
    status = 200
    if request.method == "POST":
        status = 400
        parte = request.POST.get("parte")
        if not abierta:
            messages.error(request, "Este trabajo ya no admite cambios en el consentimiento.")
            return redirect("nucleo:consentimiento", referencia=referencia)
        form = ficha if parte == "cliente" else declaracion if parte == "tatuadora" else None
        if form is not None and form.is_valid():
            with transaction.atomic():
                Postulacion.objects.select_for_update().get(pk=p.pk)
                c, _ = Consentimiento.objects.get_or_create(postulacion=p, defaults={"version_texto": VERSION})
                d = form.cleaned_data
                if parte == "cliente" and not c.cliente_firmo_en:
                    for campo in ("fecha_nacimiento", "alergias", "condiciones", "medicamentos", "embarazo", "alcohol_24h", "autoriza_fotos"):
                        setattr(c, campo, d[campo])
                    c.firma_cliente, c.cliente_firmo_en, c.registrado_por, c.version_texto = d["firma"], timezone.now(), request.user, VERSION
                    c.save()
                    # Sin datos de salud en el historial: solo que se firmó.
                    EventoSolicitud.objects.create(postulacion=p, actor=request.user, tipo="consentimiento",
                                                   detalle=f"Ficha firmada por el cliente ({d['firma']}), versión {VERSION}.")
                    messages.success(request, "Ficha del cliente firmada. Ahora firma tu declaración.")
                elif parte == "tatuadora" and c.cliente_firmo_en and not c.tatuadora_firmo_en:
                    c.firma_tatuadora, c.tatuadora_firmo_en = d["firma"], timezone.now()
                    c.save()
                    EventoSolicitud.objects.create(postulacion=p, actor=request.user, tipo="consentimiento",
                                                   detalle=f"Declaración firmada por la tatuadora ({d['firma']}). Consentimiento completo.")
                    messages.success(request, "Consentimiento completo. Ya puedes realizar la sesión.")
                else:
                    messages.error(request, "Primero debe firmar el cliente." if parte == "tatuadora" else "Esta parte ya estaba firmada.")
            return redirect("nucleo:consentimiento", referencia=referencia)
    return render(request, "nucleo/consentimiento.html", {
        "propuesta": p, "c": c, "abierta": abierta, "ficha": ficha, "declaracion": declaracion,
        "secciones": SECCIONES, "version": VERSION, "edad": _edad(c.fecha_nacimiento, timezone.localdate()) if c and c.fecha_nacimiento else None,
    }, status=status)

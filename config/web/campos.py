"""Campos de formulario con las reglas de la entrega final.

Cada campo valida en el servidor y además marca el <input> (data-solo, inputmode,
pattern) para que static/js/validacion.js bloquee al escribir los caracteres no
permitidos y muestre los mensajes del navegador en español.
"""
import re

from django import forms
from django.utils.html import format_html

from .validadores import (MENSAJE_NOMBRE, MENSAJE_TELEFONO, PATRON_NOMBRE, digitos_telefono_cl,
                          nombre_persona, telefono_contacto)

ATRIBUTOS_NOMBRE = {"data-solo": "letras", "autocapitalize": "words", "spellcheck": "false",
                    "pattern": PATRON_NOMBRE, "data-mensaje-patron": MENSAJE_NOMBRE}


def marcar_nombre(campo):
    """Agrega validación y atributos de «solo letras» a un campo ya creado (p. ej. de un ModelForm)."""
    campo.widget.attrs.update(ATRIBUTOS_NOMBRE)
    if nombre_persona not in campo.validators:
        campo.validators.append(nombre_persona)
    return campo


class NombrePersonaField(forms.CharField):
    """Solo letras y un único espacio entre palabras. Los espacios sobrantes se quitan."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 80)
        super().__init__(*args, **kwargs)
        marcar_nombre(self)

    def to_python(self, value):
        # Quita espacios al inicio, al final y repetidos; los saltos de línea o
        # tabulaciones se dejan para que la validación los rechace.
        return re.sub(r" {2,}", " ", super().to_python(value).strip(" "))


class TelefonoChileInput(forms.TextInput):
    """Prefijo +56 fijo y 9 dígitos. Muestra solo el número nacional."""
    input_type = "tel"

    def __init__(self, attrs=None):
        base = {"inputmode": "numeric", "maxlength": "9", "autocomplete": "tel-national", "data-solo": "digitos",
                "pattern": "[2-9][0-9]{8}", "data-mensaje-patron": MENSAJE_TELEFONO, "placeholder": "912345678"}
        super().__init__({**base, **(attrs or {})})

    def format_value(self, value):
        return digitos_telefono_cl(value) if value else ""

    def render(self, name, value, attrs=None, renderer=None):
        campo = super().render(name, value, attrs, renderer)
        return format_html('<span class="telefono-cl"><span class="telefono-prefijo" aria-hidden="true">+56</span>{}</span>', campo)


class TelefonoChileField(forms.CharField):
    widget = TelefonoChileInput
    default_error_messages = {"invalid": MENSAJE_TELEFONO}

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 25)
        super().__init__(*args, **kwargs)
        self.validators.append(telefono_contacto)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs["maxlength"] = "9"  # en pantalla solo el número nacional; se guarda con +56
        return attrs

    def to_python(self, value):
        texto = super().to_python(value)
        if not texto:
            return ""
        digitos = digitos_telefono_cl(texto)
        # Se valida sobre el texto recibido: «9123a4567» no debe pasar al quitar la letra.
        telefono_contacto(texto)
        return "+56" + digitos


class FechaInput(forms.DateInput):
    """Fecha escrita como DD/MM/AAAA, igual en cualquier navegador e idioma."""

    def __init__(self, attrs=None):
        base = {"placeholder": "DD/MM/AAAA", "inputmode": "numeric", "maxlength": "10", "data-mascara": "fecha",
                "pattern": r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "data-mensaje-patron": "Escribe la fecha como DD/MM/AAAA, por ejemplo 05/03/1995.",
                "autocomplete": "off"}
        super().__init__({**base, **(attrs or {})}, format="%d/%m/%Y")


class FechaField(forms.DateField):
    widget = FechaInput
    input_formats = ["%d/%m/%Y", "%Y-%m-%d"]
    default_error_messages = {"invalid": "Escribe una fecha válida con el formato DD/MM/AAAA."}


class FechaEspejoInput(forms.HiddenInput):
    """Para fechas que maneja un calendario en JavaScript con formato ISO (AAAA-MM-DD):
    el valor real va oculto y se muestra una copia editable en DD/MM/AAAA."""

    def id_for_label(self, id_):
        return f"{id_}_es" if id_ else id_

    def render(self, name, value, attrs=None, renderer=None):
        oculto = super().render(name, value, {**(attrs or {}), "data-fecha-iso": ""}, renderer)
        id_ = (attrs or {}).get("id", "")
        return format_html('<input type="text" class="form-control" id="{}_es" data-espejo-de="{}" data-mascara="fecha" placeholder="DD/MM/AAAA" '
                           'inputmode="numeric" maxlength="10" autocomplete="off" pattern="[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}" '
                           'data-mensaje-patron="Escribe la fecha como DD/MM/AAAA.">{}', id_, id_, oculto)

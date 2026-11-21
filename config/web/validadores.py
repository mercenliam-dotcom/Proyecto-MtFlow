"""Validaciones comunes para formularios, modelos y operaciones internas.

Reglas de los campos (entrega final):
- Nombres y apellidos: solo letras (con tildes, ñ y ü) y un único espacio entre
  palabras: «María José», «De la Fuente». Sin números ni símbolos.
- Teléfono: solo Chile. Se escribe el número nacional de 9 dígitos (el +56 es fijo)
  y se guarda como +56XXXXXXXXX.
- Usuario y contraseña son los únicos campos que combinan letras y números.
"""
import re
import unicodedata
from django.core.exceptions import ValidationError

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
PATRON_NOMBRE = rf"[{LETRAS}]+(?: [{LETRAS}]+)*"
MENSAJE_NOMBRE = "Usa solo letras, con un único espacio entre palabras (sin números ni símbolos)."
MENSAJE_TELEFONO = "Ingresa un teléfono chileno de 9 dígitos, por ejemplo 912345678."


def texto_sin_controles(valor):
    if any(unicodedata.category(c) in ("Cc", "Cf") and c not in "\n\r\t" for c in valor):
        raise ValidationError("El texto contiene caracteres de control no permitidos.")


def nombre_contacto(valor):
    """Regla mínima a nivel de modelo (una línea, sin controles). Los formularios
    aplican además nombre_persona."""
    texto_sin_controles(valor)
    if not valor.strip() or any(c in valor for c in "\n\r\t"):
        raise ValidationError("Indica un nombre o alias en una sola línea.")


def nombre_persona(valor):
    texto_sin_controles(valor)
    if not re.fullmatch(PATRON_NOMBRE, valor or ""):
        raise ValidationError(MENSAJE_NOMBRE, code="nombre_persona")


def digitos_telefono_cl(valor):
    """«+56 9 1234-5678», «56912345678» o «912345678» → «912345678» (sin validar)."""
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) == 11 and digitos.startswith("56"):
        digitos = digitos[2:]
    return digitos


def telefono_contacto(valor):
    if not valor:
        return
    if not re.fullmatch(r"\+?[0-9 ()-]+", valor) or not re.fullmatch(r"[2-9][0-9]{8}", digitos_telefono_cl(valor)):
        raise ValidationError(MENSAJE_TELEFONO, code="telefono")

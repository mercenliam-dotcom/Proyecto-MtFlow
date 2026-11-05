"""Validaciones comunes para formularios, modelos y operaciones internas."""
import re
import unicodedata
from django.core.exceptions import ValidationError


def texto_sin_controles(valor):
    if any(unicodedata.category(c) in ("Cc", "Cf") and c not in "\n\r\t" for c in valor):
        raise ValidationError("El texto contiene caracteres de control no permitidos.")


def nombre_contacto(valor):
    texto_sin_controles(valor)
    if not valor.strip() or any(c in valor for c in "\n\r\t"):
        raise ValidationError("Indica un nombre o alias en una sola línea.")


def telefono_contacto(valor):
    if not valor:
        return
    if not re.fullmatch(r"\+?[0-9 ()-]+", valor) or not 7 <= len(re.sub(r"\D", "", valor)) <= 15:
        raise ValidationError("Indica un teléfono de 7 a 15 dígitos; puedes usar +, espacios, guiones y paréntesis.")

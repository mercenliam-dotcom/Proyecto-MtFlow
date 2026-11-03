"""
Reglas de formato para los datos de una cuenta.

- Nombre de usuario: solo letras sin tilde y números, 4 a 30 caracteres,
  sin símbolos ni espacios. Se guarda en minúsculas.
- Nombre y apellido: solo letras (con tildes y ñ) y espacios simples.
- Contraseña: mínimo 10 caracteres (AUTH_PASSWORD_VALIDATORS), con al menos
  una letra y un número, sin espacios al inicio o al final y sin caracteres
  de control. Los símbolos SÍ se permiten: prohibirlos reduce la cantidad de
  contraseñas posibles y las hace más fáciles de adivinar (NIST SP 800-63B).
"""
import re
import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

validar_nombre_usuario = RegexValidator(
    regex=r"^[a-z0-9]{4,30}\Z",
    message="El nombre de usuario debe tener entre 4 y 30 caracteres, solo letras "
            "minúsculas sin tilde y números, sin símbolos ni espacios.",
    code="nombre_usuario",
)

validar_nombre_persona = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*\Z",
    message="Solo se permiten letras y espacios, sin números ni símbolos.",
    code="nombre_persona",
)


class ComplejidadContrasenaValidator:
    """Exige al menos una letra y un número, y prohíbe caracteres invisibles."""

    def validate(self, password, user=None):
        errores = []
        if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", password):
            errores.append(ValidationError("La contraseña debe incluir al menos una letra.",
                                           code="sin_letra"))
        if not re.search(r"\d", password):
            errores.append(ValidationError("La contraseña debe incluir al menos un número.",
                                           code="sin_numero"))
        if password != password.strip():
            errores.append(ValidationError("La contraseña no puede empezar ni terminar con espacios.",
                                           code="espacios"))
        if any(unicodedata.category(c).startswith("C") for c in password):
            errores.append(ValidationError("La contraseña contiene caracteres no permitidos.",
                                           code="control"))
        if len(password) > 128:
            errores.append(ValidationError("La contraseña no puede superar los 128 caracteres.",
                                           code="larga"))
        if errores:
            raise ValidationError(errores)

    def get_help_text(self):
        return "Debe incluir al menos una letra y un número."

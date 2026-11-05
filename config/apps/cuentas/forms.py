from django import forms
from django.contrib.auth import authenticate, password_validation

from .models import Rol, Usuario
from .seguridad import esta_bloqueado, limpiar_fallos, registrar_fallo

MENSAJE_LOGIN_INVALIDO = "Usuario o contraseña incorrectos."
MENSAJE_BLOQUEO = (
    "Demasiados intentos fallidos. Por seguridad, espera unos minutos antes de volver a intentar."
)


class _NormalizarTextoMixin:
    """Quita espacios sobrantes y normaliza nombre de usuario y correo."""

    def clean_nombre_usuario(self):
        return (self.cleaned_data.get("nombre_usuario") or "").strip().lower()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = Usuario.objects.filter(email__iexact=email)
        if getattr(self.instance, "pk", None):
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return email

    def clean_nombre(self):
        return " ".join((self.cleaned_data.get("nombre") or "").split())

    def clean_apellido(self):
        return " ".join((self.cleaned_data.get("apellido") or "").split())


class LoginForm(forms.Form):
    nombre_usuario = forms.CharField(
        label="Nombre de usuario", max_length=30,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Contraseña", max_length=128, strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, request, *args, **kwargs):
        self.request = request
        self.usuario = None
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        nombre = (datos.get("nombre_usuario") or "").strip().lower()
        password = datos.get("password") or ""
        if not nombre or not password:
            return datos
        from .seguridad import ip_cliente
        ip = ip_cliente(self.request)
        if esta_bloqueado(nombre, ip):
            raise forms.ValidationError(MENSAJE_BLOQUEO, code="bloqueado")
        # authenticate() calcula el hash de la contraseña ingresada y lo
        # compara con el guardado. Rechaza cuentas desactivadas.
        usuario = authenticate(self.request, nombre_usuario=nombre, password=password)
        if usuario is None:
            registrar_fallo(nombre, ip)
            raise forms.ValidationError(MENSAJE_LOGIN_INVALIDO, code="invalido")
        limpiar_fallos(nombre)
        self.usuario = usuario
        return datos


class _ContrasenaNuevaMixin:
    """Dos campos de contraseña que deben coincidir y cumplir la política."""

    def _validar_contrasenas(self, usuario):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
            return
        if p1:
            try:
                password_validation.validate_password(p1, usuario)
            except forms.ValidationError as e:
                self.add_error("password1", e)


def _campo_contrasena(etiqueta, autocomplete="new-password"):
    return forms.CharField(
        label=etiqueta, max_length=128, strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": autocomplete}),
    )


class CrearCuentaForm(_NormalizarTextoMixin, _ContrasenaNuevaMixin, forms.ModelForm):
    password1 = _campo_contrasena("Contraseña temporal")
    password2 = _campo_contrasena("Repite la contraseña")

    class Meta:
        model = Usuario
        fields = ["nombre_usuario", "nombre", "apellido", "email", "rol", "es_tatuadora"]
        help_texts = {
            "nombre_usuario": "Entre 4 y 30 caracteres: letras minúsculas sin tilde y números.",
        }

    def clean(self):
        datos = super().clean()
        # Usuario provisional para comparar similitud contraseña / datos personales
        provisional = Usuario(
            nombre_usuario=datos.get("nombre_usuario", ""),
            nombre=datos.get("nombre", ""), apellido=datos.get("apellido", ""),
            email=datos.get("email", ""),
        )
        self._validar_contrasenas(provisional)
        return datos

    def save(self, creado_por=None):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        usuario.creado_por = creado_por
        usuario.debe_cambiar_contrasena = True
        usuario.save()
        return usuario


class EditarCuentaForm(_NormalizarTextoMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "apellido", "email", "rol", "es_tatuadora", "is_active"]

    def __init__(self, *args, editor=None, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        cuenta = self.instance
        deja_de_ser_admin = cuenta.rol == Rol.ADMIN and (
            datos.get("rol") != Rol.ADMIN or not datos.get("is_active", True)
        )
        if deja_de_ser_admin:
            if self.editor and cuenta.pk == self.editor.pk:
                raise forms.ValidationError(
                    "No puedes quitarte el rol de administrador ni desactivar tu propia cuenta."
                )
            otros_admins = Usuario.objects.filter(rol=Rol.ADMIN, is_active=True).exclude(pk=cuenta.pk)
            if not otros_admins.exists():
                raise forms.ValidationError("Debe existir al menos un administrador activo.")
        return datos


class RestablecerContrasenaForm(_ContrasenaNuevaMixin, forms.Form):
    """El administrador asigna una contraseña temporal a otra cuenta."""
    password1 = _campo_contrasena("Nueva contraseña temporal")
    password2 = _campo_contrasena("Repite la contraseña")

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        self._validar_contrasenas(self.usuario)
        return datos

    def save(self):
        self.usuario.set_password(self.cleaned_data["password1"])
        self.usuario.debe_cambiar_contrasena = True
        self.usuario.save(update_fields=["password", "debe_cambiar_contrasena"])
        return self.usuario


class CambiarMiContrasenaForm(_ContrasenaNuevaMixin, forms.Form):
    """Cada persona cambia su propia contraseña; exige la actual."""
    actual = _campo_contrasena("Contraseña actual", "current-password")
    password1 = _campo_contrasena("Nueva contraseña")
    password2 = _campo_contrasena("Repite la nueva contraseña")

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_actual(self):
        actual = self.cleaned_data.get("actual")
        if not self.usuario.check_password(actual):
            raise forms.ValidationError("La contraseña actual no es correcta.")
        return actual

    def clean(self):
        datos = super().clean()
        self._validar_contrasenas(self.usuario)
        if datos.get("actual") and datos.get("actual") == datos.get("password1"):
            self.add_error("password1", "La nueva contraseña debe ser distinta de la actual.")
        return datos

    def save(self):
        self.usuario.set_password(self.cleaned_data["password1"])
        self.usuario.debe_cambiar_contrasena = False
        self.usuario.save(update_fields=["password", "debe_cambiar_contrasena"])
        return self.usuario

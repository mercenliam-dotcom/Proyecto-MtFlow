"""Recuperar la contraseña olvidada (solo cuentas de cliente).

Usa el mecanismo de Django: el enlace lleva un token firmado con SECRET_KEY,
el último inicio de sesión y la contraseña actual, así que deja de servir apenas
se usa y vence en PASSWORD_RESET_TIMEOUT. No se guarda nada en la base de datos.

Las cuentas del equipo no se recuperan por correo: la administración les asigna
una contraseña temporal desde «Cuentas del equipo».
"""
from django import forms
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.cache import cache
from django.urls import reverse_lazy

from .forms import _campo_contrasena
from .models import Rol, Usuario
from .seguridad import ip_cliente

MAX_PEDIDOS_HORA_IP = 5
MENSAJE_LIMITE = "Pediste demasiados enlaces en poco tiempo. Inténtalo de nuevo en una hora."


class PedirEnlaceForm(PasswordResetForm):
    email = forms.EmailField(
        label="Correo de tu cuenta", max_length=254,
        error_messages={"required": "Escribe el correo de tu cuenta.", "invalid": "Escribe un correo válido, por ejemplo nombre@correo.cl."},
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )

    def get_users(self, email):
        # Solo clientes activos con contraseña propia (no cuentas creadas solo con Google).
        for usuario in Usuario.objects.filter(email__iexact=email.strip(), is_active=True, rol=Rol.USUARIO):
            if usuario.has_usable_password():
                yield usuario


class NuevaContrasenaForm(SetPasswordForm):
    new_password1 = _campo_contrasena("Nueva contraseña")
    new_password2 = _campo_contrasena("Repite la nueva contraseña")
    error_messages = {"password_mismatch": "Las contraseñas no coinciden."}

    def save(self, commit=True):
        self.user.debe_cambiar_contrasena = False
        return super().save(commit)


class PedirEnlace(auth_views.PasswordResetView):
    form_class = PedirEnlaceForm
    template_name = "clientes/recuperar_pedir.html"
    email_template_name = "clientes/recuperar_correo.txt"
    subject_template_name = "clientes/recuperar_asunto.txt"
    success_url = reverse_lazy("clientes:recuperar_enviado")

    def form_valid(self, form):
        clave = "recuperar:" + ip_cliente(self.request)
        if cache.get(clave, 0) >= MAX_PEDIDOS_HORA_IP:
            form.add_error(None, MENSAJE_LIMITE)
            return self.form_invalid(form)
        cache.set(clave, cache.get(clave, 0) + 1, 3600)
        return super().form_valid(form)  # mismo mensaje exista o no la cuenta


class EnlaceEnviado(auth_views.PasswordResetDoneView):
    template_name = "clientes/recuperar_enviado.html"


class DefinirContrasena(auth_views.PasswordResetConfirmView):
    form_class = NuevaContrasenaForm
    template_name = "clientes/recuperar_nueva.html"
    success_url = reverse_lazy("clientes:recuperar_listo")

    def get_user(self, uidb64):
        usuario = super().get_user(uidb64)
        return usuario if usuario is not None and usuario.es_cliente else None


class ContrasenaLista(auth_views.PasswordResetCompleteView):
    template_name = "clientes/recuperar_listo.html"


__all__ = ["PedirEnlace", "EnlaceEnviado", "DefinirContrasena", "ContrasenaLista"]

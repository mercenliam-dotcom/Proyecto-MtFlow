from django import forms
from web.validadores import nombre_contacto, telefono_contacto
from .models import Usuario, PerfilCliente, Rol
from .forms import _NormalizarTextoMixin, _ContrasenaNuevaMixin, _campo_contrasena


class RegistroClienteForm(_NormalizarTextoMixin, _ContrasenaNuevaMixin, forms.ModelForm):
    password1 = _campo_contrasena("Contraseña")
    password2 = _campo_contrasena("Repite la contraseña")

    class Meta:
        model = Usuario
        fields = ["nombre_usuario", "nombre", "apellido", "email"]
        labels = {"nombre": "Nombres", "apellido": "Primer apellido"}
        help_texts = {"nombre_usuario": "Entre 4 y 30 letras minúsculas sin tilde o números."}

    def clean(self):
        datos = super().clean()
        self._validar_contrasenas(Usuario(**{campo: datos.get(campo, "") for campo in self.Meta.fields}))
        return datos

    def save(self):
        usuario = super().save(commit=False)
        # Ningún atributo de permisos procede del formulario público.
        usuario.rol = Rol.CLIENTE
        usuario.es_tatuadora = usuario.is_superuser = usuario.es_admin_desarrollo = False
        usuario.is_active = True
        usuario.debe_cambiar_contrasena = False
        usuario.set_password(self.cleaned_data["password1"])
        usuario.full_clean()
        usuario.save()
        PerfilCliente.objects.create(usuario=usuario)
        return usuario


class DatosClienteForm(_NormalizarTextoMixin, forms.ModelForm):
    actual = forms.CharField(label="Contraseña actual (solo si cambias el correo)", required=False, max_length=128, strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    class Meta:
        model = Usuario
        fields = ["nombre", "apellido", "email"]
        labels = {"nombre": "Nombres", "apellido": "Primer apellido"}

    def clean(self):
        datos = super().clean()
        if datos.get("email") != self.instance.email and not self.instance.check_password(datos.get("actual", "")):
            self.add_error("actual", "Confirma tu contraseña actual para cambiar el correo.")
        return datos


class ContactoClienteForm(forms.ModelForm):
    segundo_apellido = forms.CharField(label="Segundo apellido", max_length=80, required=False, validators=[nombre_contacto])
    telefono = forms.CharField(label="Teléfono", max_length=25, required=False, validators=[telefono_contacto])
    usuario_social = forms.RegexField(r"^@?[A-Za-z0-9_.]{1,60}$", label="Usuario de Instagram o TikTok", max_length=61, required=False)

    class Meta:
        model = PerfilCliente
        fields = ["segundo_apellido", "telefono", "canal_preferido", "usuario_social"]
        labels = {"canal_preferido": "Medio de contacto preferido"}

    def clean(self):
        datos = super().clean()
        if datos.get("canal_preferido") == "whatsapp" and not datos.get("telefono"):
            self.add_error("telefono", "Indica tu teléfono para este medio de contacto.")
        if datos.get("canal_preferido") in ("instagram", "tiktok") and not datos.get("usuario_social"):
            self.add_error("usuario_social", "Indica tu usuario para este medio de contacto.")
        return datos

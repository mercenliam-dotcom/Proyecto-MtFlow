"""«¿Olvidaste tu contraseña?»: solo clientes, enlace de un uso y mensajes en español."""
import re

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Rol, Usuario


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperarContrasena(TestCase):
    def setUp(self):
        cache.clear()
        self.cliente = Usuario.objects.create_user("anacliente", "ana@correo.cl", "Antigua2026clave", nombre="Ana", apellido="Rojas")
        self.equipo = Usuario.objects.create_user("camila", "camila@estudio.cl", "Equipo2026clave", nombre="Camila", apellido="Soto", rol=Rol.ADMIN, es_tatuadora=True)

    def pedir(self, email):
        return self.client.post(reverse("clientes:recuperar"), {"email": email})

    def enlace(self):
        return re.search(r"https?://[^/]+(/\S+)", mail.outbox[-1].body).group(1)

    def test_login_muestra_el_enlace(self):
        self.assertContains(self.client.get(reverse("cuentas:login")), "¿Olvidaste tu contraseña?")

    def test_cliente_recupera_y_el_enlace_sirve_una_vez(self):
        r = self.pedir("ANA@correo.cl")
        self.assertRedirects(r, reverse("clientes:recuperar_enviado"))
        self.assertEqual(mail.outbox[-1].subject, "Recupera tu contraseña de MTFlow")
        self.assertIn("anacliente", mail.outbox[-1].body)
        r = self.client.get(self.enlace(), follow=True)
        self.assertContains(r, "Crea tu nueva contraseña")
        url_formulario = r.redirect_chain[-1][0]
        r = self.client.post(url_formulario, {"new_password1": "Nueva2026segura", "new_password2": "Nueva2026segura"})
        self.assertRedirects(r, reverse("clientes:recuperar_listo"))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password("Nueva2026segura"))
        r = self.client.get(self.enlace(), follow=True)
        self.assertContains(r, "El enlace ya no sirve")

    def test_contrasenas_distintas_en_espanol(self):
        self.pedir("ana@correo.cl")
        r = self.client.get(self.enlace(), follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "Nueva2026segura", "new_password2": "Otra2026segura"})
        self.assertContains(r, "Las contraseñas no coinciden.")

    def test_equipo_y_correo_inexistente_no_reciben_nada_pero_ven_lo_mismo(self):
        for correo in ("camila@estudio.cl", "nadie@correo.cl"):
            r = self.pedir(correo)
            self.assertRedirects(r, reverse("clientes:recuperar_enviado"))
        self.assertEqual(mail.outbox, [])

    def test_limite_por_hora(self):
        for _ in range(5):
            self.pedir("nadie@correo.cl")
        r = self.pedir("ana@correo.cl")
        self.assertContains(r, "demasiados enlaces")
        self.assertEqual(mail.outbox, [])

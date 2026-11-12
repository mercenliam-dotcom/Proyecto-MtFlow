"""Un cliente con cuenta no puede cambiar sus datos de contacto al enviar una solicitud."""
import tempfile
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.clasificacion.cliente_ml import ServicioMLNoDisponible
from apps.cuentas.models import PerfilCliente, Rol, Usuario
from .models import ContactoSolicitud, Postulacion
from .test_recepcion import profesional, propuesta


class DatosDeCuentaBloqueados(TestCase):
    def setUp(self):
        cache.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajuste = self.settings(MEDIA_ROOT=tmp.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.artista = profesional()
        self.cliente = Usuario.objects.create_user("valesoto", "vale@ejemplo.cl", "Tinta2026segura", nombre="Valentina", apellido="Soto", rol=Rol.USUARIO, debe_cambiar_contrasena=False)
        PerfilCliente.objects.create(usuario=self.cliente, segundo_apellido="Núñez", telefono="+56911112222", canal_preferido="whatsapp")
        self.client.force_login(self.cliente)

    def enviar(self, **extra):
        with mock.patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            return self.client.post(reverse("web:cotizacion"), propuesta(self.artista, **extra))

    def test_formulario_muestra_datos_de_la_cuenta_bloqueados(self):
        r = self.client.get(reverse("web:cotizacion"))
        self.assertContains(r, "Usaremos los datos de tu cuenta")
        self.assertContains(r, "Valentina Soto Núñez")
        self.assertContains(r, "+56911112222")
        self.assertContains(r, reverse("clientes:perfil"))
        self.assertTrue(r.context["form"].fields["email"].disabled)

    def test_datos_alterados_en_el_envio_se_ignoran(self):
        r = self.enviar(nombre="Otra", primer_apellido="Persona", email="falso@ejemplo.cl", telefono="+56900000000", canal_preferido="correo")
        self.assertEqual(r.status_code, 200)
        contacto = ContactoSolicitud.objects.get(postulacion=Postulacion.objects.get())
        self.assertEqual((contacto.nombres, contacto.apellidos, contacto.segundo_apellido), ("Valentina", "Soto", "Núñez"))
        self.assertEqual((contacto.correo, contacto.telefono, contacto.canal_preferido), ("vale@ejemplo.cl", "+56911112222", "whatsapp"))

    def test_perfil_incompleto_pide_completarlo(self):
        PerfilCliente.objects.filter(usuario=self.cliente).update(telefono="")
        r = self.enviar()
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Agrégalo en «Mi perfil»", status_code=400)
        self.assertFalse(Postulacion.objects.exists())

    def test_visitante_sin_cuenta_sigue_escribiendo_sus_datos(self):
        self.client.logout()
        r = self.client.get(reverse("web:cotizacion"))
        self.assertNotContains(r, "Usaremos los datos de tu cuenta")
        self.assertFalse(r.context["form"].fields["email"].disabled)

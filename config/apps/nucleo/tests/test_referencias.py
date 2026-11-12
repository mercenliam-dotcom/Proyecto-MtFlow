"""Galería privada de imágenes de referencia."""
import tempfile

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from unittest import mock

from apps.clasificacion.cliente_ml import ServicioMLNoDisponible
from web.models import Postulacion
from web.test_recepcion import profesional, propuesta


class GaleriaReferencias(TestCase):
    def setUp(self):
        cache.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajuste = self.settings(MEDIA_ROOT=tmp.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.a, self.b = profesional("camila01"), profesional("sofia02")
        self.pa = self.enviar(self.a, nombre="Valentina", primer_apellido="Soto")
        self.pb = self.enviar(self.b, nombre="Tomás", primer_apellido="Rojas")
        self.url = reverse("nucleo:referencias")

    def enviar(self, artista, **extra):
        with mock.patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            Client().post(reverse("web:cotizacion"), propuesta(artista, **extra))
        return Postulacion.objects.latest("pk")

    def test_requiere_sesion(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_cada_tatuadora_ve_solo_sus_referencias(self):
        self.client.force_login(self.a.usuario)
        r = self.client.get(self.url)
        self.assertContains(r, "Valentina Soto")
        self.assertContains(r, self.pa.codigo)
        self.assertNotContains(r, "Tomás Rojas")
        self.assertNotContains(r, self.pb.codigo)
        self.assertContains(r, "media_privado/referencias/camila01/")
        self.assertContains(r, "data-galeria-zoom")
        self.assertContains(r, reverse("nucleo:cotizacion_detalle", args=[self.pa.referencia]))

    def test_busqueda_por_nombre_y_por_codigo(self):
        otra = self.enviar(self.a, nombre="Florencia", primer_apellido="Reyes")
        self.client.force_login(self.a.usuario)
        r = self.client.get(self.url, {"q": "flore"})
        self.assertContains(r, "Florencia Reyes")
        self.assertNotContains(r, "Valentina Soto")
        r = self.client.get(self.url, {"q": self.pa.codigo})
        self.assertContains(r, "Valentina Soto")
        self.assertNotContains(r, "Florencia Reyes")
        self.assertContains(self.client.get(self.url, {"q": "nadie"}), "Sin resultados")

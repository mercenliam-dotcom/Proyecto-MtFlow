"""La imagen de referencia se conserva entre envíos fallidos hasta enviar, quitar o reemplazar."""
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from apps.clasificacion.cliente_ml import ServicioMLNoDisponible
from .models import Imagen, Postulacion
from .test_recepcion import profesional, propuesta


class ImagenPendiente(TestCase):
    def setUp(self):
        cache.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajuste = self.settings(MEDIA_ROOT=tmp.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.media = Path(tmp.name)
        self.artista = profesional()
        self.url = reverse("web:cotizacion")

    def enviar(self, cliente=None, **extra):
        with mock.patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            return (cliente or self.client).post(self.url, propuesta(self.artista, **extra), follow=True)

    def pendientes(self):
        carpeta = self.media / "pendientes"
        return sorted(carpeta.iterdir()) if carpeta.exists() else []

    def token_de(self, respuesta):
        return re.search(r'name="imagen_pendiente" value="([^"]+)"', respuesta.content.decode()).group(1)

    def test_envio_fallido_conserva_la_imagen_y_el_reintento_la_usa(self):
        r = self.enviar(nombre="Ana1")  # nombre inválido
        self.assertEqual(r.status_code, 400)
        token = self.token_de(r)
        self.assertContains(r, reverse("web:imagen_pendiente", args=[token]), status_code=400)
        self.assertContains(r, "guardada", status_code=400)
        self.assertEqual(len(self.pendientes()), 1)
        self.assertEqual(self.client.get(reverse("web:imagen_pendiente", args=[token])).status_code, 200)
        # Segundo y tercer intento sin volver a elegir la imagen.
        r = self.enviar(nombre="Ana 2", imagen="", imagen_pendiente=token)
        self.assertEqual(r.status_code, 400)
        r = self.enviar(imagen="", imagen_pendiente=self.token_de(r))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Postulacion.objects.exists())
        self.assertTrue(Imagen.objects.get().url.startswith("referencias/"))
        self.assertEqual(self.pendientes(), [])  # la copia temporal se descarta al completar

    def test_token_de_otra_sesion_no_sirve(self):
        token = self.token_de(self.enviar(nombre="Ana1"))
        otro = Client()
        self.assertEqual(otro.get(reverse("web:imagen_pendiente", args=[token])).status_code, 404)
        r = self.enviar(cliente=otro, imagen="", imagen_pendiente=token)
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Selecciona una imagen", status_code=400)
        self.assertFalse(Postulacion.objects.exists())

    def test_sin_imagen_ni_token_pide_la_imagen(self):
        r = self.enviar(imagen="")
        self.assertContains(r, "Selecciona una imagen", status_code=400)

    def test_analisis_previo_devuelve_el_token(self):
        with mock.patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            r = self.client.post(reverse("web:analizar_referencia"), {"analizar": "on", "imagen": propuesta(self.artista)["imagen"]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("no está disponible", r.json()["error"])
        token = r.json()["pendiente"]
        self.assertEqual(len(self.pendientes()), 1)
        r = self.enviar(imagen="", imagen_pendiente=token)
        self.assertEqual(r.status_code, 200, re.findall(r'class="error[^"]*"[^>]*>(.{0,200})', r.content.decode()))
        self.assertEqual(self.pendientes(), [])


    def test_tras_enviar_se_muestra_el_resultado_una_vez_y_al_recargar_queda_vacio(self):
        with mock.patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            r = self.client.post(self.url, propuesta(self.artista, email="persona@correo.cl"))
        self.assertRedirects(r, self.url, fetch_redirect_response=False)  # Post/Redirect/Get: recargar no reenvía el formulario
        r = self.client.get(self.url)
        self.assertContains(r, "Propuesta enviada")
        self.assertNotContains(r, 'value="persona@correo.cl"')  # el formulario nuevo viene vacío
        r = self.client.get(self.url)  # recarga
        self.assertNotContains(r, "Propuesta enviada")
        self.assertNotContains(r, "persona@correo.cl")

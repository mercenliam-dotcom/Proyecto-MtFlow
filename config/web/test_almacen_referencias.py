"""Las referencias se guardan en referencias/<tatuadora>/ con nombre legible."""
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.clasificacion.cliente_ml import ServicioMLNoDisponible

from .models import Imagen, Postulacion
from .test_recepcion import profesional, propuesta


class AlmacenReferencias(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ajuste = self.settings(MEDIA_ROOT=self.tmp.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.media = Path(self.tmp.name)
        self.artista = profesional("camila01")

    def enviar(self, **extra):
        with mock.patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            r = Client().post(reverse("web:cotizacion"), propuesta(self.artista, **extra))
        self.assertEqual(r.status_code, 200)
        return Postulacion.objects.latest("pk")

    def test_nueva_referencia_va_a_la_carpeta_de_su_tatuadora(self):
        p = self.enviar(nombre="Valentina", primer_apellido="Soto Núñez")
        url = Imagen.objects.get(postulacion=p).url
        carpeta, nombre = url.rsplit("/", 1)
        self.assertEqual(carpeta, "referencias/camila01")
        self.assertTrue(nombre.startswith(f"{p.codigo}_valentina-soto-nunez_"), nombre)
        self.assertTrue(nombre.endswith(".jpg"))
        self.assertTrue((self.media / url).is_file())

    def test_otra_tatuadora_tiene_su_propia_carpeta(self):
        self.artista = profesional("sofia02")
        p = self.enviar()
        self.assertTrue(Imagen.objects.get(postulacion=p).url.startswith("referencias/sofia02/"))

    def test_ordenar_referencias_mueve_antiguas_y_es_repetible(self):
        p = self.enviar(nombre="Tomás")
        imagen = Imagen.objects.get(postulacion=p)
        # Simula el formato antiguo: una carpeta por solicitud y por intento.
        antigua = f"postulaciones/{p.referencia}/abc123/archivo.jpg"
        (self.media / antigua).parent.mkdir(parents=True)
        (self.media / imagen.url).rename(self.media / antigua)
        Imagen.objects.filter(pk=imagen.pk).update(url=antigua)

        salida = io.StringIO()
        call_command("ordenar_referencias", "--simular", stdout=salida)
        self.assertTrue((self.media / antigua).is_file())  # simular no mueve

        call_command("ordenar_referencias", stdout=io.StringIO())
        imagen.refresh_from_db()
        self.assertTrue(imagen.url.startswith(f"referencias/camila01/{p.codigo}_tomas_"))
        self.assertTrue((self.media / imagen.url).is_file())
        self.assertFalse((self.media / "postulaciones").exists())  # carpetas vacías eliminadas

        salida = io.StringIO()
        call_command("ordenar_referencias", stdout=salida)
        self.assertIn("Movidas: 0", salida.getvalue())

    def test_archivo_faltante_se_informa_sin_tocar_registro(self):
        p = self.enviar()
        imagen = Imagen.objects.get(postulacion=p)
        Imagen.objects.filter(pk=imagen.pk).update(url="postulaciones/no-existe.jpg")
        salida = io.StringIO()
        call_command("ordenar_referencias", stdout=salida)
        imagen.refresh_from_db()
        self.assertEqual(imagen.url, "postulaciones/no-existe.jpg")
        self.assertIn("Sin archivo en disco: 1", salida.getvalue())

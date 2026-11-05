from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.clasificacion.cliente_ml import ResultadoClasificacion, ServicioMLNoDisponible
from apps.nucleo.tests.utilidades import jpg_valido, subido, HTML_CON_SCRIPT
from .models import Cliente, ConfianzaEstilo, Imagen, Postulacion, Prediccion
from .test_recepcion import profesional, propuesta


class AnalisisPrevio(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        contexto = self.settings(MEDIA_ROOT=self.tmp.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.url = reverse("web:analizar_referencia")

    def analizar(self, **extra):
        return self.client.post(self.url, {"analizar": "on", "imagen": jpg_valido(), **extra})

    def assert_sin_guardado(self):
        for modelo in (Cliente, Imagen, Postulacion, Prediccion, ConfianzaEstilo):
            self.assertFalse(modelo.objects.exists())
        self.assertFalse(any(Path(self.tmp.name).rglob("*")))

    def test_clasifica_antes_de_completar_contacto_sin_guardar(self):
        vector = {"E-01": .64, **{f"E-{i:02}": .36 / 6 for i in range(2, 8)}}
        respuesta = Mock(status_code=200, json=lambda: {
            "version_modelo": "efficientnet_b0:v1:test", "confianzas": vector,
            "estilo_sugerido": "E-01", "confianza_maxima": .64, "umbral_confianza": .6,
        })
        with patch("requests.post", return_value=respuesta) as ml:
            r = self.analizar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nombre"], "Alto contraste")
        self.assertNotIn("umbral_confianza", r.json())
        self.assertNotIn("estilos", r.json())
        self.assertFalse(r.json()["simulado"])
        self.assertIn("no-store", r["Cache-Control"])
        self.assertNotIn("nombre", ml.call_args.kwargs["files"])
        self.assert_sin_guardado()

    def test_bajo_60_devuelve_fuera_de_catalogo_sin_inventar_probabilidad(self):
        vector = {"E-01": .59, **{f"E-{i:02}": .41 / 6 for i in range(2, 8)}}
        respuesta = Mock(status_code=200, json=lambda: {"confianzas": vector})
        with patch("requests.post", return_value=respuesta):
            r = self.analizar()
        self.assertEqual(r.json()["estilo_sugerido"], "E-99")
        self.assertEqual(r.json()["nombre"], "Fuera de catálogo")
        self.assertNotIn("confianza_maxima", r.json())
        self.assertNotIn("estilos", r.json())
        self.assert_sin_guardado()

    def test_envia_solo_imagen_recodificada(self):
        imagen = jpg_valido()
        originales = imagen.read()
        imagen.seek(0)
        resultado = ResultadoClasificacion({"E-01": .8}, "E-01", .8, "local:test")
        with patch("web.views.clasificar", return_value=resultado) as ml:
            r = self.analizar(imagen=imagen, email="contacto@example.test")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(ml.call_args.args), 3)
        self.assertNotEqual(ml.call_args.args[0], originales)
        self.assertNotIn("contacto@example.test", repr(ml.call_args))
        self.assert_sin_guardado()

    def test_sin_activar_analisis_no_llama_al_modelo(self):
        with patch("web.views.clasificar") as ml:
            r = self.analizar(analizar="")
        self.assertEqual(r.status_code, 400)
        ml.assert_not_called()

    def test_archivo_disfrazado_no_llega_al_servicio(self):
        with patch("web.views.clasificar") as ml:
            r = self.analizar(imagen=subido("falso.jpg", HTML_CON_SCRIPT))
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())
        ml.assert_not_called()
        self.assert_sin_guardado()

    def test_fallo_del_modelo_permite_continuar_sin_datos_guardados(self):
        with patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            r = self.analizar()
        self.assertEqual(r.status_code, 503)
        self.assertIn("reintentarlo", r.json()["error"])
        self.assert_sin_guardado()

    def test_csrf_y_metodo_post_obligatorios(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, {"analizar": "on", "imagen": jpg_valido()}).status_code, 403)

    @override_settings(ANALISIS_MAX_INTENTOS=1, COTIZACION_MAX_INTENTOS=1)
    def test_limite_del_analisis_no_consume_los_envios_de_propuesta(self):
        resultado = ResultadoClasificacion({"E-01": .8}, "E-01", .8, "local:test")
        with patch("web.views.clasificar", return_value=resultado):
            self.assertEqual(self.analizar().status_code, 200)
            r = self.analizar()
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r)
        self.assert_sin_guardado()
        artista = profesional()
        r = self.client.post(reverse("web:cotizacion"), propuesta(artista))
        self.assertEqual(r.status_code, 200)

    def test_formulario_ofrece_analisis_automatico_y_url_del_endpoint(self):
        r = self.client.get(reverse("web:cotizacion"))
        self.assertTrue(r.context["form"].fields["analizar"].initial)
        self.assertContains(r, 'id="live-analysis"')
        self.assertContains(r, self.url)

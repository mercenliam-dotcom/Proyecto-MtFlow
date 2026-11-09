from unittest.mock import patch
import tempfile

from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.clasificacion.cliente_ml import ResultadoClasificacion, ServicioMLNoDisponible
from apps.nucleo.tests.utilidades import jpg_valido, subido, HTML_CON_SCRIPT
from .precios import estimar
from .forms import token_envio
from .test_recepcion import profesional


def datos(**extra):
    valores = dict(envio=token_envio(), nombre="Cliente", email="cliente@example.com", telefono="", tatuadora="1",
                   zona="antebrazo", alto_cm="5", ancho_cm="5", color="negro", detalle="normal",
                   idea="Una flor", imagen=jpg_valido())
    valores.update(extra)
    return valores


class CotizacionPublica(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media_settings = self.settings(MEDIA_ROOT=self.tmp.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.artista = profesional()
        self.url = reverse("web:cotizacion")

    def datos(self, **extra):
        return datos(**{"tatuadora": str(self.artista.pk), **extra})

    def test_precio_servidor_ignora_monto_inyectado_y_analiza_automaticamente(self):
        with patch("web.views.clasificar", side_effect=ServicioMLNoDisponible) as ml:
            r = self.client.post(self.url, self.datos(minimo="1", maximo="1", precio="1"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "$35.000")
        self.assertContains(r, "$60.000")
        self.assertFalse(r.context["estimacion"]["manual"])
        ml.assert_called_once()
        self.assertIn("no-store", r["Cache-Control"])

    def test_ml_solo_recibe_imagen_limpia_y_no_contacto(self):
        resultado = ResultadoClasificacion({"E-05": .92}, "E-05", .92, "roboflow-prueba")
        with patch("web.views.clasificar", return_value=resultado) as ml:
            r = self.client.post(self.url, self.datos(analizar="on"))
        self.assertContains(r, "Línea fina")
        self.assertEqual(len(ml.call_args.args), 3)
        self.assertNotIn("cliente@example.com", repr(ml.call_args))
        self.assertNotEqual(ml.call_args.args[1], "referencia.jpg")
        self.assertContains(r, "$35.000")

    def test_ml_caido_conserva_estimacion(self):
        with patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            r = self.client.post(self.url, self.datos(analizar="on"))
        self.assertContains(r, "El análisis no está disponible")
        self.assertContains(r, "$35.000")

    def test_simulacion_se_informa(self):
        resultado = ResultadoClasificacion({"E-05": .92}, "E-05", .92, "simulado-0.2")
        with patch("web.views.clasificar", return_value=resultado):
            r = self.client.post(self.url, self.datos(analizar="on"))
        self.assertContains(r, "Resultado simulado")

    def test_cobertura_no_inventa_precio(self):
        r = self.client.post(self.url, self.datos(cobertura="on"))
        self.assertTrue(r.context["estimacion"]["manual"])
        self.assertNotContains(r, "$35.000")

    def test_xss_se_muestra_como_texto(self):
        ataque = '<script>alert("x")</script>'
        r = self.client.post(self.url, self.datos(nombre=ataque, idea=ataque))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, ataque)
        self.assertContains(r, "&lt;script&gt;")

    def test_opciones_manipuladas_y_campos_incompletos_rechazados(self):
        for cambios in ({"alto_cm": "-5"}, {"ancho_cm": ""}, {"tatuadora": "99"}, {"color": "<script>"}, {"email": "no-es-correo"}, {"idea": "x" * 1501}):
            with self.subTest(cambios=cambios), patch("web.views.clasificar") as ml:
                r = self.client.post(self.url, self.datos(analizar="on", **cambios))
                self.assertEqual(r.status_code, 400)
                self.assertNotIn("estimacion", r.context)
                ml.assert_not_called()

    def test_archivo_disfrazado_no_llega_a_ml(self):
        with patch("web.views.clasificar") as ml:
            r = self.client.post(self.url, self.datos(analizar="on", imagen=subido("falso.jpg", HTML_CON_SCRIPT)))
        self.assertEqual(r.status_code, 400)
        ml.assert_not_called()

    def test_csrf_obligatorio(self):
        r = Client(enforce_csrf_checks=True).post(self.url, datos())
        self.assertEqual(r.status_code, 403)

    @override_settings(COTIZACION_MAX_INTENTOS=1, CONFIAR_EN_PROXY=False)
    def test_limite_no_se_elude_con_forwarded_for(self):
        self.client.post(self.url, self.datos(), HTTP_X_FORWARDED_FOR="1.1.1.1")
        with patch("web.views.clasificar") as ml:
            r = self.client.post(self.url, self.datos(analizar="on"), HTTP_X_FORWARDED_FOR="8.8.8.8")
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r)
        ml.assert_not_called()

    @override_settings(IMAGEN_MAX_BYTES=100, DEBUG=False)
    def test_tamano_se_corta_durante_subida(self):
        with patch("web.forms.validar_imagen") as validar:
            r = self.client.post(self.url, self.datos())
        self.assertEqual(r.status_code, 400)
        validar.assert_not_called()

    def test_solo_get_y_post(self):
        self.assertEqual(self.client.put(self.url, "{}").status_code, 405)


class Tarifas(TestCase):
    def test_reglas_y_redondeo_exactos(self):
        r = estimar(dict(tamano="pequeno", zona="pecho", cobertura=False, color="color", detalle="alto"))
        self.assertEqual((r["minimo"], r["maximo"]), (55000, 100000))

    def test_fuera_de_rango_y_zona_especial_exigen_revision(self):
        for tamano, zona in (("especial", "brazo"), ("mediano", "otra")):
            self.assertTrue(estimar(dict(tamano=tamano, zona=zona, cobertura=False))["manual"])

    def test_precios_crecen_con_tamano(self):
        rangos = [estimar(dict(tamano=t, zona="brazo", cobertura=False, color="negro", detalle="normal")) for t in ("pequeno", "mediano", "grande")]
        self.assertEqual([x["minimo"] for x in rangos], [35000, 65000, 110000])

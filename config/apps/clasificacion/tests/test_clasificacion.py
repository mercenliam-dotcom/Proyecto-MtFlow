from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.clasificacion.catalogo import recomendar
from apps.clasificacion.cliente_ml import ServicioMLNoDisponible, _validar_respuesta, clasificar
from apps.cuentas.models import Rol, Usuario
from apps.nucleo.tests import utilidades as u

CONF_OK = {"E-01": 0.93, "E-02": 0.02, "E-03": 0.01, "E-04": 0.01, "E-05": 0.01, "E-06": 0.01, "E-07": 0.01}
# Formato del modelo de Roboflow: 7 estilos, sin E-99


class Recomendacion(SimpleTestCase):
    def test_tres_estados(self):
        self.assertEqual(recomendar("E-01", 0.95).codigo, "APTO")
        self.assertEqual(recomendar("E-01", 0.87).codigo, "EN_EVALUACION")
        self.assertEqual(recomendar("E-01", 0.50).codigo, "NO_RECOMENDADO")

    def test_fuera_de_catalogo_nunca_es_apto(self):
        self.assertEqual(recomendar("E-99", 0.99).codigo, "NO_RECOMENDADO")

    def test_solo_apto_queda_preaprobada(self):
        self.assertEqual(recomendar("E-01", 0.95).alerta_ml, "PRE_APROBADA")
        self.assertEqual(recomendar("E-01", 0.87).alerta_ml, "REVISION_ESPECIAL")


class ValidacionRespuesta(SimpleTestCase):
    def test_respuesta_valida(self):
        r = _validar_respuesta({"version_modelo": "x", "confianzas": CONF_OK})
        self.assertEqual(r.estilo_sugerido, "E-01")

    def test_respuestas_invalidas(self):
        malos = [
            None, [], {"confianzas": "x"},
            {"confianzas": {**CONF_OK, "E-08": 0.0}},                 # clase desconocida
            {"confianzas": {k: v for k, v in CONF_OK.items() if k != "E-07"}},   # falta un estilo
            {"confianzas": {**CONF_OK, "E-01": 1.5}},
            {"confianzas": {**CONF_OK, "E-01": "0.9"}},
            {"confianzas": {**CONF_OK, "E-01": float("nan")}},
            {"confianzas": {k: 0.5 for k in CONF_OK}},                # suma más de 1
            {"confianzas": {k: 0.0 for k in CONF_OK}},                # todo cero
        ]
        for m in malos:
            with self.assertRaises(ServicioMLNoDisponible, msg=str(m)):
                _validar_respuesta(m)

    def test_acepta_clases_omitidas_bajo_umbral(self):
        # Roboflow puede informar solo la clase sobre su umbral (0,4)
        parcial = {k: 0.0 for k in CONF_OK}
        parcial["E-02"] = 0.62
        r = _validar_respuesta({"confianzas": parcial})
        self.assertEqual(r.estilo_sugerido, "E-02")
        self.assertAlmostEqual(r.confianza_maxima, 0.62)

    def test_e99_es_opcional(self):
        con_e99 = {**CONF_OK, "E-01": 0.92, "E-99": 0.01}
        self.assertEqual(_validar_respuesta({"confianzas": con_e99}).estilo_sugerido, "E-01")

    def test_nombres_del_catalogo(self):
        from apps.clasificacion.catalogo import ESTILOS
        self.assertEqual(ESTILOS["E-05"], "Línea fina")
        self.assertEqual(len([c for c in ESTILOS if c != "E-99"]), 7)

    def test_sin_conexion(self):
        with mock.patch("requests.post", side_effect=requests.ConnectionError):
            with self.assertRaises(ServicioMLNoDisponible):
                clasificar(b"x", "a.jpg", "image/jpeg")

    def test_envia_clave_y_no_sigue_redirecciones(self):
        resp = mock.Mock(status_code=200, json=lambda: {"confianzas": CONF_OK})
        with mock.patch("requests.post", return_value=resp) as post:
            clasificar(b"x", "a.jpg", "image/jpeg")
        kwargs = post.call_args.kwargs
        self.assertIn("X-API-Key", kwargs["headers"])
        self.assertFalse(kwargs["allow_redirects"])


class VistaProbar(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user("tatuadora1", "t@e.cl", "Tinta2026segura",
                                                nombre="Ana", apellido="Rojas", rol=Rol.USUARIO)
        self.user.debe_cambiar_contrasena = False
        self.user.save()
        self.client.force_login(self.user)
        self.url = reverse("clasificacion:probar")

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_formulario_solo_tiene_campo_de_archivo(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'accept="image/jpeg,image/png"')
        self.assertNotContains(r, 'type="url"')
        self.assertEqual(list(r.context["form"].fields), ["imagen"])

    def test_imagen_valida_muestra_resultado(self):
        resp = mock.Mock(status_code=200, json=lambda: {"version_modelo": "simulado", "confianzas": CONF_OK})
        with mock.patch("requests.post", return_value=resp):
            r = self.client.post(self.url, {"imagen": u.jpg_valido()})
        self.assertContains(r, "Apto")
        self.assertContains(r, "93,0%")
        self.assertContains(r, 'value="93.0"')
        self.assertContains(r, "data:image/jpeg;base64,")

    def test_fuera_de_catalogo_se_muestra_sin_porcentaje(self):
        # Respuesta del servicio cuando ningún estilo supera el umbral de Roboflow
        fuera = {**{k: 0.0 for k in CONF_OK}, "E-99": 1.0}
        resp = mock.Mock(status_code=200, json=lambda: {"version_modelo": "rf", "confianzas": fuera})
        with mock.patch("requests.post", return_value=resp):
            r = self.client.post(self.url, {"imagen": u.jpg_valido()})
        self.assertContains(r, "No recomendado")
        self.assertContains(r, "Fuera de catálogo")
        self.assertContains(r, "40 %")
        self.assertNotContains(r, "100,0%")

    def test_respuesta_real_con_una_sola_clase(self):
        parcial = {k: 0.0 for k in CONF_OK}
        parcial["E-05"] = 0.4182
        resp = mock.Mock(status_code=200, json=lambda: {
            "version_modelo": "roboflow-workflow:martin-stgmar-gmail-com/tattoo-styles-vtattoo-styles-2-resnet18-t1-logic",
            "confianzas": parcial})
        with mock.patch("requests.post", return_value=resp):
            r = self.client.post(self.url, {"imagen": u.jpg_valido()})
        self.assertContains(r, "Línea fina")
        self.assertContains(r, "41,8%")
        self.assertContains(r, "No recomendado")   # 0,42 < umbral 0,85 de la recomendación
        self.assertContains(r, "&lt; 40 %", count=6)  # los otros 6 estilos no informados
        self.assertContains(r, "roboflow-workflow:martin")

    def test_video_disfrazado_no_llega_al_servicio(self):
        with mock.patch("requests.post") as post:
            r = self.client.post(self.url, {"imagen": u.subido("clip.jpg", u.MP4_FALSO)})
        post.assert_not_called()
        self.assertContains(r, "video")

    def test_pdf_no_llega_al_servicio(self):
        with mock.patch("requests.post") as post:
            self.client.post(self.url, {"imagen": u.subido("doc.pdf", u.PDF_FALSO, "application/pdf")})
        post.assert_not_called()

    def test_campo_url_inyectado_se_ignora(self):
        with mock.patch("requests.post") as post:
            r = self.client.post(self.url, {"url": "https://videos.com/x.mp4",
                                            "imagen_url": "file:///etc/passwd"})
        post.assert_not_called()
        self.assertTrue(r.context["form"].errors.get("imagen"))

    def test_mas_de_tres_archivos_rechazado(self):
        archivos = [u.jpg_valido(f"a{i}.jpg") for i in range(4)]
        r = self.client.post(self.url, {"imagen": archivos})
        self.assertEqual(r.status_code, 400)

    def test_servicio_caido_muestra_aviso(self):
        with mock.patch("requests.post", side_effect=requests.Timeout):
            r = self.client.post(self.url, {"imagen": u.jpg_valido()})
        self.assertContains(r, "no está disponible")

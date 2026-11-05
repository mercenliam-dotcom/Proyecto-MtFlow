from decimal import Decimal
from pathlib import Path
import tempfile
import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.cuentas.models import Usuario
from apps.nucleo.tests.utilidades import imagen_bytes
from web.models import Cliente, ConfianzaEstilo, Estilo, Imagen, Postulacion, Prediccion, Tatuadora
from web.test_recepcion import profesional


class MisCotizaciones(TestCase):
    def setUp(self):
        self.artista = profesional("artista1")
        self.otra = profesional("artista2")
        self.cliente = Cliente.objects.create(nombres="Cliente propio", apellidos="", correo="propio@example.com")
        self.ajeno = Cliente.objects.create(nombres="Cliente ajeno", apellidos="", correo="ajeno@example.com")
        self.propia = self.crear(self.artista, self.cliente)
        self.externa = self.crear(self.otra, self.ajeno, estado="RECHAZADA")
        self.url = reverse("nucleo:cotizaciones")
        self.detalle = reverse("nucleo:cotizacion_detalle", args=[self.propia.referencia])
        self.client.force_login(self.artista.usuario)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.override = self.settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def crear(self, artista, cliente, **extra):
        return Postulacion.objects.create(
            tatuadora=artista, cliente=cliente, alto_cm=5, ancho_cm=4,
            area_cm2=20, zona_cuerpo="antebrazo", categoria_tamano="pequeno",
            descripcion="IDEA: Una flor | COLOR: negro | DETALLE: normal | COVER-UP: False", **{"estado": "RECIBIDA", "estado_ml": "NO_SOLICITADO", **extra},
        )

    def imagen(self, url="postulaciones/prueba.jpg", existente=False):
        if existente:
            ruta = Path(self.tmp.name) / url
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(imagen_bytes())
        return Imagen.objects.create(postulacion=self.propia, url=url, orden=1, formato="JPEG", ancho_px=400, alto_px=300, tamano_bytes=100)

    def test_lista_y_detalle_exigen_sesion(self):
        self.client.logout()
        for url in (self.url, self.detalle):
            self.assertRedirects(self.client.get(url), reverse("cuentas:login") + "?next=" + url, fetch_redirect_response=False)

    def test_lista_solo_muestra_propuestas_propias(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Cliente propio")
        self.assertNotContains(r, "Cliente ajeno")
        self.assertNotContains(r, str(self.externa.referencia))
        self.assertEqual(r.context["total"], 1)
        self.assertIn("no-store", r["Cache-Control"])

    def test_detalle_ajeno_no_revela_datos(self):
        r = self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.externa.referencia]))
        self.assertEqual(r.status_code, 404)
        self.assertNotContains(r, "ajeno@example.com", status_code=404)

    def test_referencia_inexistente_y_formato_invalido(self):
        self.assertEqual(self.client.get(reverse("nucleo:cotizacion_detalle", args=[uuid.uuid4()])).status_code, 404)
        self.assertEqual(self.client.get("/panel/cotizaciones/123/").status_code, 404)

    def test_detalle_muestra_contacto_medidas_y_precio_sin_reservar(self):
        self.propia.precio_sugerido = 35000
        self.propia.save()
        r = self.client.get(self.detalle)
        self.assertContains(r, "propio@example.com")
        self.assertContains(r, "Una flor")
        self.assertContains(r, "Negro y grises")
        self.assertNotContains(r, "COVER-UP")
        self.assertContains(r, "$35.000 CLP")
        self.assertContains(r, "Su recepción no confirma una reserva")
        self.assertIsNone(Postulacion.objects.get(pk=self.propia.pk).bloque_id)

    def test_imagen_se_sirve_mediante_url_privada(self):
        self.imagen(existente=True)
        r = self.client.get(self.detalle)
        url = r.context["referencias"][0]["url"]
        self.assertTrue(url.startswith("/panel/archivo/"))
        self.assertNotContains(r, '/media/')
        imagen = self.client.get(url)
        self.assertEqual(imagen.status_code, 200)
        imagen.close()
        self.client.force_login(self.otra.usuario)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_imagen_legacy_ausente_se_informa(self):
        self.imagen("temporal_local/no-existe.jpg")
        r = self.client.get(self.detalle)
        self.assertContains(r, "La imagen no está disponible")
        self.assertIsNone(r.context["referencias"][0]["url"])

    def test_ruta_externa_o_fuera_del_almacenamiento_no_se_incrusta(self):
        imagen = self.imagen("https://externo.invalid/referencia.jpg")
        for ruta in ("https://externo.invalid/referencia.jpg", "../secreto.jpg"):
            imagen.url = ruta
            imagen.save()
            r = self.client.get(self.detalle)
            self.assertIsNone(r.context["referencias"][0]["url"])
            self.assertNotContains(r, ruta)

    def test_ml_simulado_y_confianzas_se_identifican_sin_inferencia_nueva(self):
        imagen = self.imagen()
        estilo = Estilo.objects.create(codigo="E-05", nombre="Línea fina")
        prediccion = Prediccion.objects.create(imagen=imagen, estilo_sugerido=estilo, version_modelo="simulado-0.2", confianza_maxima="0.92", tiempo_inferencia_ms=100)
        ConfianzaEstilo.objects.create(prediccion=prediccion, estilo=estilo, confianza="0.92")
        with patch("web.views.clasificar") as ml:
            r = self.client.get(self.detalle)
        self.assertContains(r, "Resultado simulado")
        self.assertContains(r, "Línea fina")
        self.assertContains(r, "92,0 %")
        ml.assert_not_called()

    def test_ausencia_de_ml_solicitado_y_caido(self):
        self.imagen()
        self.assertContains(self.client.get(self.detalle), "No se solicitó el análisis")
        self.propia.estado_ml = "NO_DISPONIBLE"
        self.propia.save()
        self.assertContains(self.client.get(self.detalle), "El análisis no estuvo disponible")

    def test_fuera_de_catalogo_no_muestra_porcentaje_como_estilo(self):
        imagen = self.imagen()
        estilo = Estilo.objects.create(codigo="E-99", nombre="Fuera de catálogo", es_catalogo=False)
        fina = Estilo.objects.create(codigo="E-05", nombre="Línea fina")
        prediccion = Prediccion.objects.create(imagen=imagen, estilo_sugerido=estilo, version_modelo="roboflow-workflow:prueba", confianza_maxima=1, tiempo_inferencia_ms=100)
        ConfianzaEstilo.objects.create(prediccion=prediccion, estilo=estilo, confianza=1)
        ConfianzaEstilo.objects.create(prediccion=prediccion, estilo=fina, confianza=0)
        r = self.client.get(self.detalle)
        self.assertContains(r, "Fuera de catálogo")
        self.assertContains(r, "&lt; 40 %")
        self.assertIsNone(r.context["referencias"][0]["confianza"])

    def test_orden_por_fecha_y_paginacion(self):
        for i in range(21):
            self.crear(self.artista, self.cliente)
        r = self.client.get(self.url)
        self.assertEqual(len(r.context["pagina"]), 20)
        self.assertEqual(r.context["total"], 22)
        self.assertGreater(r.context["pagina"][0].pk, r.context["pagina"][-1].pk)
        r = self.client.get(self.url, {"pagina": 2})
        self.assertEqual(len(r.context["pagina"]), 2)

    def test_estado_filtra_solo_dentro_de_las_propias(self):
        self.crear(self.artista, self.cliente, estado="EN_REVISION")
        r = self.client.get(self.url, {"estado": "EN_REVISION"})
        self.assertEqual(r.context["pagina"].paginator.count, 1)
        self.assertEqual(r.context["pagina"][0].estado, "EN_REVISION")
        self.assertNotContains(r, "RECHAZADA")
        r = self.client.get(self.url, {"estado": "RECHAZADA", "pagina": "incorrecta"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["estado"], "")
        self.assertEqual(r.context["pagina"].paginator.count, 2)

    def test_admin_ve_solo_sus_propuestas_en_esta_bandeja(self):
        admin = Usuario.objects.create_superuser("admin01", "admin@example.com", "Tinta2026segura", nombre="Admin", apellido="Local")
        self.client.force_login(admin)
        r = self.client.get(self.url)
        self.assertEqual(r.context["total"], 0)
        self.assertNotContains(r, "Cliente propio")
        self.assertEqual(self.client.get(self.detalle).status_code, 404)

    def test_sin_perfil_o_sin_propuestas_muestra_vacio(self):
        self.client.force_login(self.otra.usuario)
        Postulacion.objects.filter(pk=self.externa.pk).delete()
        Tatuadora.objects.filter(pk=self.otra.pk).delete()
        self.assertContains(self.client.get(self.url), "Aún no tienes cotizaciones")

    def test_solo_consulta_no_acepta_post(self):
        for url in (self.url, self.detalle):
            self.assertEqual(self.client.post(url).status_code, 405)
        self.propia.refresh_from_db()
        self.assertEqual(self.propia.estado, "RECIBIDA")

    def test_descripcion_y_contacto_escapan_html(self):
        ataque = '<script>alert("x")</script>'
        Cliente.objects.filter(pk=self.cliente.pk).update(nombres=ataque)
        Postulacion.objects.filter(pk=self.propia.pk).update(descripcion=ataque)
        for url in (self.url, self.detalle):
            r = self.client.get(url)
            self.assertNotContains(r, ataque)
            self.assertContains(r, "&lt;script&gt;")

    def test_panel_tiene_enlace_y_navegacion_activa_correcta(self):
        self.assertContains(self.client.get(reverse("nucleo:inicio")), self.url)
        r = self.client.get(self.detalle)
        self.assertContains(r, 'href="' + self.url + '" aria-current="page"')

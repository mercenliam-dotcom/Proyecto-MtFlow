"""Con DEBUG=1 no se muestran las páginas técnicas de Django (rutas, trazas)."""
from django.test import TestCase, override_settings
from django.urls import path
from django.http import Http404


def explota(request):
    raise RuntimeError("detalle interno que no debe verse")


def no_existe(request):
    raise Http404("detalle interno 404")


urlpatterns = [path("explota/", explota), path("no-existe/", no_existe)]


@override_settings(DEBUG=True, MOSTRAR_ERRORES_TECNICOS=False)
class PaginasErrorEnDesarrollo(TestCase):
    def test_ruta_inexistente_no_lista_las_rutas(self):
        r = self.client.get("/ruta/que/no/existe/")
        self.assertEqual(r.status_code, 404)
        texto = r.content.decode()
        self.assertIn("Página no encontrada", texto)
        self.assertNotIn("URLconf", texto)
        self.assertNotIn("vista-previa/error", texto)
        self.assertNotIn("gestion-interna", texto)
        self.assertIn("Catálogo de trabajos", texto)

    @override_settings(ROOT_URLCONF=__name__)
    def test_http404_de_una_vista_tampoco_muestra_detalles(self):
        r = self.client.get("/no-existe/")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("detalle interno", r.content.decode())

    @override_settings(ROOT_URLCONF=__name__)
    def test_error_500_sin_traza(self):
        self.client.raise_request_exception = False
        with self.assertLogs("django.request", level="ERROR"):  # el error sigue en la consola
            r = self.client.get("/explota/")
        self.assertEqual(r.status_code, 500)
        texto = r.content.decode()
        self.assertIn("Error interno", texto)
        self.assertNotIn("Traceback", texto)
        self.assertNotIn("detalle interno", texto)

    def test_direcciones_incompletas_redirigen(self):
        self.assertRedirects(self.client.get("/portafolio/imagen/"), "/catalogo/")
        self.assertRedirects(self.client.get("/portafolio/"), "/")

    @override_settings(MOSTRAR_ERRORES_TECNICOS=True)
    def test_modo_depuracion_explicito_conserva_pagina_tecnica(self):
        self.assertIn("URLconf", self.client.get("/ruta/que/no/existe/").content.decode())

from django.test import TestCase, RequestFactory, override_settings, Client
from django.urls import reverse
from web.test_recepcion import profesional
from .test_agenda import solicitud
from apps.nucleo import errores


class BuzonLectura(TestCase):
    def setUp(self):
        self.a = profesional()
        self.b = profesional('otralectora')
        self.p = solicitud(self.a)
        self.url = reverse('nucleo:cotizacion_resumen', args=[self.p.referencia])
        self.client.force_login(self.a.usuario)

    def test_fragmento_privado_escapado_sin_mutaciones(self):
        self.p.descripcion = '<script>alert(1)</script>'
        self.p.save()
        r = self.client.get(self.url)
        self.assertContains(r, 'data-resumen-solicitud')
        self.assertContains(r, '&lt;script&gt;')
        self.assertNotContains(r, '<script>alert')
        self.assertEqual(r['X-MTFlow-Fragment'], 'resumen-solicitud')
        self.assertIn('no-store', r['Cache-Control'])
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, 'RECIBIDA')
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_otra_tatuadora_no_lee_resumen_personal(self):
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(Client().get(self.url).status_code, 302)

    def test_bandeja_conserva_enlaces_completos_y_avisos(self):
        r = self.client.get(reverse('nucleo:cotizaciones'))
        self.assertContains(r, 'class="correo-fila"')
        self.assertContains(r, reverse('nucleo:cotizacion_detalle', args=[self.p.referencia]))
        self.assertContains(r, 'id="avisos-temporales"')
        self.assertNotContains(r, 'id="buzon-lectura"')


class PaginasError(TestCase):
    @override_settings(DEBUG=False)
    def test_404_amigable_y_preview_cerrado(self):
        r = self.client.get('/esta-pagina-no-existe/')
        self.assertContains(r, 'Página no encontrada', status_code=404)
        self.assertContains(r, 'css/errores.css', status_code=404)
        self.assertEqual(self.client.get('/vista-previa/error/500/').status_code, 404)

    @override_settings(DEBUG=True)
    def test_preview_codigos(self):
        for codigo in (400, 403, 404, 500, 503):
            r = self.client.get(f'/vista-previa/error/{codigo}/')
            self.assertEqual(r.status_code, codigo)
            self.assertContains(r, 'Volver al inicio', status_code=codigo)

    def test_500_no_consulta_base_ni_expone_excepcion(self):
        with self.assertNumQueries(0):
            r = errores.error_500(RequestFactory().get('/'))
        self.assertEqual(r.status_code, 500)
        self.assertNotIn(b'Traceback', r.content)

    def test_csrf_amigable_sin_detalles_internos(self):
        r = Client(enforce_csrf_checks=True).post(reverse('cuentas:login'), {})
        self.assertContains(r, 'No pudimos validar el envío', status_code=403)

from django.test import TestCase
from django.urls import reverse
from web.test_recepcion import profesional
from .test_agenda import solicitud


class CampanaAvisos(TestCase):
    def setUp(self):
        self.a = profesional()
        self.b = profesional("otracampana")
        self.p = solicitud(self.a)
        self.client.force_login(self.a.usuario)

    def test_solicitud_nueva_aparece_sin_leer(self):
        r = self.client.get(reverse("nucleo:inicio"))
        self.assertContains(r, 'id="campana"')
        self.assertEqual(r.context["campana"]["total"], 1)
        datos = self.client.get(reverse("nucleo:avisos")).json()
        self.assertEqual(datos["total"], 1)
        self.assertEqual(datos["items"][0]["url"], reverse("nucleo:cotizacion_detalle", args=[self.p.referencia]))

    def test_abrir_detalle_la_marca_leida_sin_cambiar_version(self):
        version = self.p.actualizada_en
        self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.p.referencia]))
        self.p.refresh_from_db()
        self.assertIsNotNone(self.p.vista_en)
        self.assertEqual(self.p.actualizada_en, version)
        self.assertEqual(self.client.get(reverse("nucleo:avisos")).json()["total"], 0)

    def test_otra_tatuadora_no_ve_ni_marca_ajenas(self):
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(reverse("nucleo:avisos")).json()["total"], 0)
        self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.p.referencia]))
        self.client.post(reverse("nucleo:avisos_leidas"))
        self.p.refresh_from_db()
        self.assertIsNone(self.p.vista_en)

    def test_marcar_todo_requiere_post(self):
        self.assertEqual(self.client.get(reverse("nucleo:avisos_leidas")).status_code, 405)
        self.client.post(reverse("nucleo:avisos_leidas"))
        self.p.refresh_from_db()
        self.assertIsNotNone(self.p.vista_en)

    def test_sin_sesion_no_hay_campana(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("nucleo:avisos")).status_code, 302)

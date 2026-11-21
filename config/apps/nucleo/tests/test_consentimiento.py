"""Consentimiento informado: página pública, firmas separadas y bloqueo de la sesión."""
from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.nucleo.flujo import aplicar
from apps.nucleo.operaciones_agenda import cerrar_bloque, gestionar
from web.models import BloqueHorario, Consentimiento, EventoSolicitud, Sesion
from web.test_recepcion import profesional
from .test_agenda import solicitud


class ConsentimientoInformado(TestCase):
    def setUp(self):
        self.a, self.b = profesional(), profesional("otra")
        self.p = solicitud(self.a)
        gestionar(self.a.usuario, self.p.referencia, {"accion": "aceptar", "precio_final": 100000, "abono_solicitado": 30000, "alto_final_cm": 10, "ancho_final_cm": 5})
        gestionar(self.a.usuario, self.p.referencia, {"accion": "abono", "monto_abono": 30000, "verificado": True})
        self.bloque = BloqueHorario.objects.create(tatuadora=self.a, tipo="CITA", fecha=timezone.localdate() - timedelta(days=1), hora_inicio=time(10), hora_fin=time(12), estado="RESERVADA")
        Sesion.objects.create(bloque=self.bloque, postulacion=self.p)
        self.url = reverse("nucleo:consentimiento", args=[self.p.referencia])
        self.client.force_login(self.a.usuario)

    def ficha(self, **extra):
        adulto = timezone.localdate().replace(year=timezone.localdate().year - 25)
        datos = {"parte": "cliente", "cliente-fecha_nacimiento": adulto.isoformat(), "cliente-alergias": "Látex",
                 "cliente-acepta": "on", "cliente-firma": "Valentina Soto"}
        datos.update(extra)
        return self.client.post(self.url, datos)

    def declaracion(self, firma="Ana Rojas", **extra):
        datos = {"parte": "tatuadora", "tatuadora-firma": firma, **{f"tatuadora-{k}": "on" for k in ("higiene", "material", "riesgos", "ficha")}}
        datos.update(extra)
        return self.client.post(self.url, datos)

    def realizar(self):
        self.bloque.refresh_from_db()
        return cerrar_bloque(self.a.usuario, self.bloque.referencia, "realizar", "", self.bloque.actualizada_en.isoformat())

    def test_pagina_publica_solo_lectura(self):
        r = Client().get(reverse("web:consentimiento"))
        self.assertContains(r, "Consentimiento informado")
        self.assertContains(r, "mayor de 18")
        self.assertNotContains(r, 'name="parte"')  # solo lectura: sin formularios de firma

    def test_sin_consentimiento_no_se_marca_realizada(self):
        with self.assertRaisesMessage(ValidationError, "completa el consentimiento"):
            self.realizar()
        r = self.client.get(reverse("nucleo:agenda_editar", args=[self.bloque.referencia]))
        self.assertContains(r, "Falta el consentimiento firmado")

    def test_firmas_en_orden_y_luego_se_puede_realizar(self):
        self.declaracion()
        self.assertFalse(Consentimiento.objects.filter(postulacion=self.p, tatuadora_firmo_en__isnull=False).exists())
        self.assertRedirects(self.ficha(), self.url)
        with self.assertRaises(ValidationError):  # falta la declaración
            self.realizar()
        self.assertContains(self.client.get(self.url), "Látex")
        self.assertRedirects(self.declaracion(), self.url)
        c = Consentimiento.objects.get(postulacion=self.p)
        self.assertTrue(c.completo)
        self.assertEqual(c.firma_cliente, "Valentina Soto")
        self.assertEqual(self.realizar().estado, "REALIZADA")
        # El historial registra las firmas, nunca los datos de salud.
        detalles = " ".join(EventoSolicitud.objects.filter(postulacion=self.p, tipo="consentimiento").values_list("detalle", flat=True))
        self.assertIn("Ficha firmada", detalles)
        self.assertNotIn("Látex", detalles)

    def test_menor_de_edad_y_alcohol_se_rechazan(self):
        menor = timezone.localdate().replace(year=timezone.localdate().year - 17)
        self.assertContains(self.ficha(**{"cliente-fecha_nacimiento": menor.isoformat()}), "mayores de 18", status_code=400)
        self.assertContains(self.ficha(**{"cliente-alcohol_24h": "on"}), "alcohol", status_code=400)
        self.assertContains(self.ficha(**{"cliente-firma": "Valentina"}), "nombre y apellido", status_code=400)
        self.assertFalse(Consentimiento.objects.exists())

    def test_la_tatuadora_firma_con_su_nombre_de_cuenta(self):
        self.ficha()
        self.assertContains(self.declaracion(firma="Otra Persona"), "«Ana Rojas»", status_code=400)
        self.assertRedirects(self.declaracion(firma="ana  rojas"), self.url)  # sin distinguir mayúsculas ni espacios

    def test_solo_su_tatuadora_ve_la_ficha(self):
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_terminar_exige_consentimiento(self):
        aplicar(self.a.usuario, self.p.referencia, "cobro", {"version": self.p.__class__.objects.get(pk=self.p.pk).actualizada_en.isoformat(), "tipo": "PAGO", "monto": 70000, "verificado": True, "detalle": "Saldo"})
        self.p.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "consentimiento"):
            aplicar(self.a.usuario, self.p.referencia, "terminar", {"version": self.p.actualizada_en.isoformat(), "confirmado": True})
        r = self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.p.referencia]))
        self.assertContains(r, "Firma el consentimiento")

from django.test import TestCase, Client
from django.urls import reverse
from web.test_recepcion import profesional
from .test_agenda import solicitud


class RegistroYDecision(TestCase):
    def setUp(self):
        self.a=profesional()
        self.b=profesional("otraartista")
        self.p=solicitud(self.a)
        self.client.force_login(self.a.usuario)

    def paso(self,accion):
        return reverse("nucleo:gestion_paso",args=[self.p.referencia,accion])

    def test_aceptar_saca_de_pendientes_y_conserva_en_registro(self):
        r=self.client.post(self.paso("aceptar"),{"accion":"aceptar","version":self.p.actualizada_en.isoformat(),"precio_final":100000,"abono_solicitado":30000,"continuar":"1"})
        self.assertRedirects(r,self.paso("abono")+"?guiado=1")
        self.assertNotContains(self.client.get(reverse("nucleo:cotizaciones")),str(self.p.referencia))
        self.assertContains(self.client.get(reverse("nucleo:registro")),str(self.p.referencia))
        self.p.refresh_from_db()
        self.assertIsNone(self.p.abono_verificado_en)
        self.assertEqual(self.p.sesiones.count(),0)
        r=self.client.post(self.paso("abono"),{"accion":"abono","version":self.p.actualizada_en.isoformat(),"monto_abono":30000,"verificado":"on","continuar":"1"})
        self.assertRedirects(r,reverse("nucleo:agenda_nuevo")+"?solicitud="+str(self.p.referencia))

    def test_rechazo_guiado_exige_motivo_y_pasa_al_registro(self):
        datos={"accion":"rechazar","version":self.p.actualizada_en.isoformat(),"continuar":"1"}
        r=self.client.post(self.paso("rechazar"),datos)
        self.assertEqual(r.status_code,400)
        self.assertContains(r,'name="continuar"',status_code=400)
        datos["motivo"]="No corresponde al trabajo ofrecido"
        self.assertRedirects(self.client.post(self.paso("rechazar"),datos),reverse("nucleo:registro")+"?bandeja=rechazadas")
        self.assertNotContains(self.client.get(reverse("nucleo:cotizaciones")),str(self.p.referencia))
        self.assertContains(self.client.get(reverse("nucleo:registro")),str(self.p.referencia))

    def test_registro_privado_y_filtros_no_reintroducen_pendientes(self):
        otra=solicitud(self.b); otra.estado="RECHAZADA"; otra.save()
        self.assertNotContains(self.client.get(reverse("nucleo:registro")),str(otra.referencia))
        self.assertNotContains(self.client.get(reverse("nucleo:registro"),{"estado":"RECIBIDA"}),str(self.p.referencia))
        self.p.estado="RESERVADA"; self.p.save()
        self.assertNotContains(self.client.get(reverse("nucleo:cotizaciones"),{"estado":"RESERVADA"}),str(self.p.referencia))
        r=self.client.get(reverse("nucleo:registro"),{"bandeja":"agendadas"})
        self.assertContains(r,str(self.p.referencia))
        self.assertEqual(r.context["resumen_registro"],{"aceptadas":1,"rechazadas":0})
        self.assertEqual(Client().get(reverse("nucleo:registro")).status_code,302)

    def test_dialogo_no_muta_y_pantalla_completa_sigue_disponible(self):
        r=self.client.get(reverse("nucleo:cotizacion_detalle",args=[self.p.referencia]),{"guiado":"1"})
        self.assertContains(r,'id="decision-solicitud"')
        self.assertContains(r,"Cerrar y revisar detalles")
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,"RECIBIDA")
        self.assertEqual(self.client.get(self.paso("aceptar")).status_code,200)
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(self.paso("aceptar")).status_code,404)

    def test_abono_parcial_no_salta_a_reserva(self):
        self.p.estado="ACEPTADA"; self.p.precio_final=100000; self.p.abono_solicitado=30000; self.p.save()
        r=self.client.post(self.paso("abono"),{"accion":"abono","version":self.p.actualizada_en.isoformat(),"monto_abono":10000,"verificado":"on","continuar":"1"})
        self.assertRedirects(r,reverse("nucleo:cotizacion_detalle",args=[self.p.referencia]))

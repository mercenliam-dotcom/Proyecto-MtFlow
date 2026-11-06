from datetime import timedelta, time, datetime
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from web.test_recepcion import profesional, propuesta
from web.models import BloqueHorario, MovimientoCobro, HorarioTrabajo
from web.forms import CotizacionForm
from web.disponibilidad import libres_del_dia
from apps.nucleo.forms_agenda import BloqueForm
from apps.nucleo.operaciones_agenda import gestionar, guardar_bloque
from .test_agenda import solicitud


class FlujoAgendaPublica(TestCase):
    def setUp(self):
        self.a=profesional()
        self.b=profesional("otraartista")
        self.p=solicitud(self.a)
        hoy=timezone.localdate()
        self.lunes=hoy+timedelta(days=(7-hoy.weekday())%7+7)
        self.client.force_login(self.a.usuario)

    def url_paso(self, accion):
        return reverse("nucleo:gestion_paso",args=[self.p.referencia,accion])

    def aceptar(self):
        r=self.client.get(self.url_paso("aceptar"))
        self.assertContains(r,"Aceptar solicitud")
        self.assertNotContains(r,'name="monto_abono"')
        self.assertNotContains(r,'name="verificado"')
        r=self.client.post(self.url_paso("aceptar"),{"accion":"aceptar","version":self.p.actualizada_en.isoformat(),"precio_final":100000,"abono_solicitado":30000})
        self.assertEqual(r.status_code,302)
        self.p.refresh_from_db()

    def datos_cita(self):
        return {"tipo":"CITA","postulacion":self.p.pk,"fecha":self.lunes.isoformat(),"hora_inicio":"10:00","hora_fin":"12:00"}

    def publico(self, artista=None, dia=None):
        dia=dia or self.lunes
        return Client().get(reverse("web:disponibilidad"),{"tatuadora":(artista or self.a).pk,"start":dia.isoformat(),"end":(dia+timedelta(days=1)).isoformat()})

    def test_flujo_http_aceptar_confirmar_pago_externo_y_crear_primera_sesion(self):
        self.aceptar()
        r=self.client.get(self.url_paso("abono"))
        self.assertContains(r,"Confirmar pago externo")
        self.assertNotContains(r,'name="precio_final"')
        datos={"accion":"abono","version":self.p.actualizada_en.isoformat(),"monto_abono":30000,"verificado":"on"}
        self.assertEqual(self.client.post(self.url_paso("abono"),datos).status_code,302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.total_cobrado,30000)
        self.assertContains(self.client.get(reverse("nucleo:cotizacion_detalle",args=[self.p.referencia])),"Agendar una sesión")
        self.assertEqual(self.client.post(reverse("nucleo:agenda_nuevo"),self.datos_cita()).status_code,302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado,"RESERVADA")
        self.assertEqual(self.p.sesiones.count(),1)
        self.assertEqual(self.p.total_cobrado,30000)

    def test_pago_externo_ya_registrado_habilita_sin_duplicar_importe(self):
        self.aceptar()
        MovimientoCobro.objects.create(postulacion=self.p,tipo="PAGO",monto=30000,detalle="Transferencia comprobada",verificado_por=self.a.usuario)
        self.assertEqual(self.client.post(reverse("nucleo:agenda_nuevo"),self.datos_cita()).status_code,302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.total_cobrado,30000)
        self.assertIsNone(self.p.monto_abono)

    def test_no_confirma_sin_marcar_pago_ni_permite_accion_distinta(self):
        self.aceptar()
        d={"accion":"abono","version":self.p.actualizada_en.isoformat(),"monto_abono":30000}
        self.assertEqual(self.client.post(self.url_paso("abono"),d).status_code,400)
        self.p.refresh_from_db()
        self.assertIsNone(self.p.abono_verificado_en)
        d["accion"]="rechazar"
        self.assertEqual(self.client.post(self.url_paso("abono"),d).status_code,400)

    def test_otra_tatuadora_no_modifica_el_acuerdo(self):
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(self.url_paso("aceptar")).status_code,404)

    def test_publico_muestra_trabajo_sin_identidades_ni_notas(self):
        bloque=BloqueHorario.objects.create(tatuadora=self.a,fecha=self.lunes,tipo="BLOQUEO",estado="BLOQUEADO",hora_inicio=time(11),hora_fin=time(12),nota="Detalle privado")
        r=self.publico()
        self.assertEqual(r.status_code,200)
        texto=r.content.decode()
        for secreto in ("Detalle privado",str(bloque.referencia),"Cliente privado","solo@example.test"):
            self.assertNotIn(secreto,texto)
        eventos=r.json()["eventos"]
        self.assertEqual(len(eventos),3)
        self.assertEqual([(e["start"][11:16],e["end"][11:16]) for e in eventos if e["extendedProps"]["disponible"]],[("10:00","11:00"),("12:00","19:00")])
        self.assertEqual(len(self.publico(self.b).json()["eventos"]),1)
        bloque.estado="CANCELADA"; bloque.save()
        self.assertEqual(len(self.publico().json()["eventos"]),1)

    def test_domingo_cerrado_y_excepcion_diez_a_catorce(self):
        domingo=self.lunes+timedelta(days=6)
        self.assertEqual(self.publico(dia=domingo).json()["eventos"],[])
        guardar_bloque(self.a.usuario,{"tipo":"DISPONIBILIDAD","fecha":domingo,"hora_inicio":time(10),"hora_fin":time(14)})
        e=self.publico(dia=domingo).json()["eventos"][0]
        self.assertEqual((e["start"][11:16],e["end"][11:16]),("10:00","14:00"))

    def test_propuesta_ocupada_fuera_jornada_y_pasada_se_rechazan(self):
        BloqueHorario.objects.create(tatuadora=self.a,fecha=self.lunes,tipo="BLOQUEO",estado="BLOQUEADO",hora_inicio=time(11),hora_fin=time(12))
        for fecha,hora in [(self.lunes,"11:00"),(self.lunes,"09:00"),(self.lunes,"19:00"),(timezone.localdate()-timedelta(days=1),"10:00")]:
            datos=propuesta(self.a,fecha_propuesta=fecha.isoformat(),hora_propuesta=hora)
            imagen=datos.pop("imagen")
            form=CotizacionForm(datos,{"imagen":imagen})
            self.assertFalse(form.is_valid(),(fecha,hora))
            self.assertTrue("fecha_propuesta" in form.errors or "hora_propuesta" in form.errors)

    def test_hoy_rechaza_hora_pasada_en_formulario_y_operacion(self):
        ahora=timezone.make_aware(datetime.combine(self.lunes,time(14)))
        with patch("django.utils.timezone.now",return_value=ahora):
            d={"tipo":"BLOQUEO","fecha":self.lunes,"hora_inicio":time(13),"hora_fin":time(15)}
            self.assertFalse(BloqueForm(d,tatuadora=self.a).is_valid())
            with self.assertRaises(ValidationError): guardar_bloque(self.a.usuario,d)
            for e in self.publico().json()["eventos"]:
                self.assertGreaterEqual(e["start"][11:16],"14:00")

    def test_horario_semanal_editable_y_no_invalida_reserva(self):
        self.aceptar()
        gestionar(self.a.usuario,self.p.referencia,{"accion":"abono","monto_abono":30000,"verificado":True})
        guardar_bloque(self.a.usuario,self.datos_cita())
        datos={"form-TOTAL_FORMS":"7","form-INITIAL_FORMS":"7"}
        for dia in range(7):
            datos.update({f"form-{dia}-dia":dia,f"form-{dia}-activo":"on",f"form-{dia}-hora_inicio":"13:00",f"form-{dia}-hora_fin":"18:00"})
        url=reverse("nucleo:horario_trabajo")
        self.assertEqual(self.client.post(url,datos).status_code,400)
        datos["form-0-hora_inicio"]="10:00"
        self.assertEqual(self.client.post(url,datos).status_code,302)
        self.assertEqual(HorarioTrabajo.objects.filter(tatuadora=self.a).count(),7)
        self.assertEqual(libres_del_dia(self.a,self.lunes),[(time(12),time(18))])

    def test_intervalo_publico_acotado_y_artista_inactiva(self):
        url=reverse("web:disponibilidad")
        self.assertEqual(Client().get(url,{"tatuadora":self.a.pk,"start":"2030-01-01","end":"2031-01-01"}).status_code,400)
        self.a.activa=False; self.a.save()
        self.assertEqual(self.publico().status_code,404)

from datetime import timedelta, time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError, transaction, connections, close_old_connections
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from web.test_recepcion import profesional
from web.models import ContactoSolicitud, BloqueHorario, Cliente, Postulacion, EventoSolicitud, Imagen, Estilo, Prediccion
from apps.nucleo.forms_agenda import BloqueForm, GestionForm
from apps.nucleo.operaciones_agenda import gestionar, guardar_bloque, cerrar_bloque


def solicitud(artista):
    cliente = Cliente.objects.create(nombres="Cliente privado", apellidos="Prueba", correo="solo@example.test")
    p = Postulacion.objects.create(cliente=cliente, tatuadora=artista, zona_cuerpo="brazo", alto_cm=10, ancho_cm=5, descripcion="Idea", estado="RECIBIDA")
    ContactoSolicitud.objects.create(postulacion=p, nombres=cliente.nombres, correo=cliente.correo)
    return p


class Agenda(TestCase):
    def setUp(self):
        self.a = profesional()
        self.b = profesional("otra")
        self.p = solicitud(self.a)
        self.fecha = timezone.localdate() + timedelta(days=10)
        self.client.force_login(self.a.usuario)

    def datos(self, tipo="DISPONIBILIDAD", inicio=9, fin=18, **extra):
        return dict(tipo=tipo, fecha=self.fecha, hora_inicio=time(inicio), hora_fin=time(fin), nota="", postulacion=self.p if tipo == "CITA" else None, **extra)

    def aceptar(self):
        gestionar(self.a.usuario, self.p.referencia, {"accion": "aceptar", "precio_final": 100000})
        gestionar(self.a.usuario, self.p.referencia, {"accion": "abono", "monto_abono": 30000, "verificado": True})
        self.p.refresh_from_db()

    def reservar(self):
        self.aceptar()
        guardar_bloque(self.a.usuario, self.datos())
        return guardar_bloque(self.a.usuario, self.datos("CITA", 10, 11))

    def test_horarios_dejan_de_ser_publicos(self):
        c = Client()
        self.assertRedirects(c.get(reverse("web:horarios")), reverse("nucleo:agenda"), fetch_redirect_response=False)
        self.assertEqual(c.get(reverse("nucleo:agenda")).status_code, 302)
        self.assertNotContains(c.get(reverse("web:portafolio")), 'href="/horarios/"')

    def test_agenda_renderiza_y_nonce_no_relaja_scripts(self):
        r = self.client.get(reverse("nucleo:agenda"))
        self.assertContains(r, "Mi agenda")
        self.assertContains(r, 'name="csp-nonce"')
        self.assertIn("'nonce-", r["Content-Security-Policy"])
        self.assertIn("script-src 'self';", r["Content-Security-Policy"])
        self.assertIn("no-store", r["Cache-Control"])

    def test_formulario_de_horario_muestra_calendario(self):
        # Sin el nonce, la CSP bloquea los estilos de FullCalendar y el calendario queda vacío.
        for url in (reverse("nucleo:agenda_nuevo"), reverse("nucleo:agenda_nuevo") + f"?solicitud={self.p.referencia}"):
            r = self.client.get(url)
            self.assertContains(r, 'id="agenda-calendar"')
            self.assertContains(r, 'name="csp-nonce"')
            self.assertContains(r, "vendor/fullcalendar/index.global.min.js")

    def test_cuenta_no_tatuadora_no_puede_abrir_agenda(self):
        self.a.usuario.es_tatuadora = False
        self.a.usuario.save()
        self.assertEqual(self.client.get(reverse("nucleo:agenda")).status_code, 403)

    def test_flujo_acuerdo_abono_reserva_e_historial(self):
        b = self.reservar()
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "RESERVADA")
        self.assertEqual(self.p.sesiones.get(), b)
        self.assertEqual(self.p.abono_verificado_por, self.a.usuario)
        self.assertEqual(self.p.eventos.count(), 3)
        # Con una sesión ya reservada no se ofrece agendar otra.
        self.assertNotContains(self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.p.referencia])), "Agendar una sesión")

    def test_historial_de_reprogramacion_es_legible(self):
        from web.models import EventoSolicitud
        b = self.reservar()
        datos = self.datos("CITA", 12, 13)
        datos["version"] = b.actualizada_en.isoformat()
        guardar_bloque(self.a.usuario, datos, b.referencia)
        evento = EventoSolicitud.objects.filter(postulacion=self.p, tipo="reprogramada").latest("pk")
        self.assertNotIn("datetime", evento.detalle)
        self.assertIn(f"Ahora: {datos['fecha']:%d/%m/%Y} 12:00–13:00", evento.detalle)

    def test_solicitud_con_sesion_reservada_no_agenda_otra(self):
        self.reservar()
        with self.assertRaisesMessage(ValidationError, "ya tiene una sesión reservada"):
            guardar_bloque(self.a.usuario, self.datos("CITA", 12, 13))
        self.assertEqual(self.p.sesiones.count(), 1)

    def test_sesion_exige_abono_y_disponibilidad(self):
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos("CITA", 10, 11))
        self.aceptar()
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos("CITA", 8, 9))
        self.assertEqual(BloqueHorario.objects.count(), 0)

    def test_intervalos_solapados_rechazados_contiguos_permitidos(self):
        self.reservar()
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos("CITA", 10, 12))
        guardar_bloque(self.a.usuario, self.datos("BLOQUEO", 11, 12))
        self.assertEqual(BloqueHorario.objects.filter(tipo="BLOQUEO").count(), 1)

    def test_bloqueo_personal_impide_reserva(self):
        self.reservar()
        guardar_bloque(self.a.usuario, self.datos("BLOQUEO", 12, 14))
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos("CITA", 13, 15))

    def test_database_impide_solape_incluso_sin_servicio(self):
        self.reservar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BloqueHorario.objects.create(tatuadora=self.a, fecha=self.fecha, hora_inicio=time(10, 30), hora_fin=time(11, 30), tipo="BLOQUEO", estado="BLOQUEADO")
        BloqueHorario.objects.create(tatuadora=self.b, fecha=self.fecha, hora_inicio=time(10), hora_fin=time(11), tipo="BLOQUEO", estado="BLOQUEADO")

    def test_database_impide_intervalo_invertido(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BloqueHorario.objects.create(tatuadora=self.a, fecha=self.fecha, hora_inicio=time(12), hora_fin=time(11), tipo="BLOQUEO", estado="BLOQUEADO")

    def test_cancelar_libera_hora_sin_borrar_historial(self):
        b = self.reservar()
        cerrar_bloque(self.a.usuario, b.referencia, "cancelar", "Cliente reprograma", b.actualizada_en.isoformat())
        guardar_bloque(self.a.usuario, self.datos("CITA", 10, 11))
        b.refresh_from_db()
        self.assertEqual(b.estado, "CANCELADA")
        self.assertEqual(self.p.sesiones.count(), 2)

    def test_no_quitar_disponibilidad_con_reservas(self):
        self.reservar()
        d = BloqueHorario.objects.get(tipo="DISPONIBILIDAD")
        with self.assertRaises(ValidationError):
            cerrar_bloque(self.a.usuario, d.referencia, "cancelar", "Cambio", d.actualizada_en.isoformat())
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos(inicio=12, version=d.actualizada_en.isoformat()), d.referencia)

    def test_edicion_obsoleta_no_pisa_cambios(self):
        b = self.reservar()
        version = b.actualizada_en.isoformat()
        guardar_bloque(self.a.usuario, self.datos("CITA", 12, 13, version=version), b.referencia)
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos("CITA", 14, 15, version=version), b.referencia)
        b.refresh_from_db()
        self.assertEqual(b.hora_inicio, time(12))

    def test_fallo_reprogramacion_no_altera_reserva(self):
        b = self.reservar()
        guardar_bloque(self.a.usuario, self.datos("BLOQUEO", 12, 13))
        eventos = EventoSolicitud.objects.count()
        with self.assertRaises(ValidationError):
            guardar_bloque(self.a.usuario, self.datos("CITA", 12, 13, version=b.actualizada_en.isoformat()), b.referencia)
        b.refresh_from_db()
        self.assertEqual(b.hora_inicio, time(10))
        self.assertEqual(EventoSolicitud.objects.count(), eventos)

    def test_otra_tatuadora_no_ve_ni_cambia_solicitud_o_bloque(self):
        b = self.reservar()
        self.client.force_login(self.b.usuario)
        for nombre, ref in [("agenda_editar", b.referencia), ("cotizacion_detalle", self.p.referencia)]:
            self.assertEqual(self.client.get(reverse("nucleo:" + nombre, args=[ref])).status_code, 404)
        self.assertEqual(self.client.post(reverse("nucleo:cotizacion_gestion", args=[self.p.referencia]), {"accion": "revisar"}).status_code, 404)
        r = self.client.get(reverse("nucleo:agenda_eventos"), {"start": str(self.fecha), "end": str(self.fecha + timedelta(days=1))})
        self.assertEqual([e for e in r.json() if e.get("display") != "background"], [])

    def test_feed_limita_intervalo_y_no_filtra_contacto(self):
        self.reservar()
        url = reverse("nucleo:agenda_eventos")
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, {"start": str(self.fecha), "end": str(self.fecha + timedelta(days=101))}).status_code, 400)
        r = self.client.get(url, {"start": str(self.fecha), "end": str(self.fecha + timedelta(days=1))})
        self.assertEqual(len([e for e in r.json() if e.get("display") != "background"]), 2)
        self.assertNotContains(r, "solo@example.test")

    def test_formulario_rechaza_sesion_de_otro_cliente(self):
        self.aceptar()
        f = BloqueForm(self.datos("CITA", 10, 11) | {"postulacion": self.p.pk}, tatuadora=self.b)
        self.assertFalse(f.is_valid())

    def test_abono_requiere_confirmacion_y_no_excede_precio(self):
        self.assertFalse(GestionForm({"accion": "abono", "monto_abono": 20000}).is_valid())
        self.aceptar()
        for monto in (20000, 120000):
            with self.assertRaises(ValidationError):
                gestionar(self.a.usuario, self.p.referencia, {"accion": "abono", "monto_abono": monto, "verificado": True})

#    def test_sesion_futura_no_puede_completarse(self):
#        b = self.reservar()
#        with self.assertRaises(ValidationError):
#            cerrar_bloque(self.a.usuario, b.referencia, "realizar", "", b.actualizada_en.isoformat())

    def test_rechazo_conserva_solicitud_para_revision(self):
        gestionar(self.a.usuario, self.p.referencia, {"accion": "rechazar", "motivo": "Estilo fuera de especialidad"})
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "RECHAZADA")
        self.assertEqual(self.p.eventos.count(), 1)

    def test_post_protegido_con_csrf(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.a.usuario)
        self.assertEqual(c.post(reverse("nucleo:agenda_nuevo"), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse("nucleo:cotizacion_gestion", args=[self.p.referencia])).status_code, 405)

    def test_post_disponibilidad_persiste(self):
        r = self.client.post(reverse("nucleo:agenda_nuevo"), {"tipo": "DISPONIBILIDAD", "fecha": self.fecha, "hora_inicio": "09:00", "hora_fin": "18:00"})
        self.assertRedirects(r, reverse("nucleo:agenda"))
        self.assertEqual(BloqueHorario.objects.count(), 1)

    def test_confianza_visible_solo_en_buzon_con_orden_priorizado(self):
        estilo, _ = Estilo.objects.get_or_create(codigo="E-01", defaults={"nombre": "Alto contraste"})
        for p, valor in [(self.p, ".90"), (solicitud(self.a), ".70")]:
            im = Imagen.objects.create(postulacion=p, url=f"prueba-{p.pk}.jpg", orden=1, es_principal=True, formato="JPEG", ancho_px=300, alto_px=300, tamano_bytes=1000)
            Prediccion.objects.create(imagen=im, version_modelo="local:test", estilo_sugerido=estilo, confianza_maxima=valor, tiempo_inferencia_ms=1)
        r = self.client.get(reverse("nucleo:cotizaciones"), {"orden": "confianza"})
        self.assertContains(r, "90.0 %")
        self.assertEqual(r.context["pagina"][0].pk, self.p.pk)

    def test_identificador_invalido_no_produce_error_interno(self):
        r = self.client.get(reverse("nucleo:agenda_nuevo"), {"solicitud": "no-es-uuid"})
        self.assertEqual(r.status_code, 404)

    def test_ultima_sesion_requiere_cierre_explicito_del_trabajo(self):
        # Varias sesiones, de a una: la siguiente se agenda cuando la anterior se cierra.
        primero = self.reservar()
        ayer = timezone.localdate() - timedelta(days=1)
        BloqueHorario.objects.filter(pk=primero.pk).update(fecha=ayer)
        primero.refresh_from_db()
        cerrar_bloque(self.a.usuario, primero.referencia, "realizar", "", primero.actualizada_en.isoformat())
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "ACEPTADA")
        segundo = guardar_bloque(self.a.usuario, self.datos("CITA", 11, 12))
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "RESERVADA")
        BloqueHorario.objects.filter(pk=segundo.pk).update(fecha=ayer)
        segundo.refresh_from_db()
        cerrar_bloque(self.a.usuario, segundo.referencia, "realizar", "", segundo.actualizada_en.isoformat())
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "ACEPTADA")
        from apps.nucleo.flujo import aplicar
        if self.p.saldo_pendiente:
            aplicar(self.a.usuario, self.p.referencia, "cobro", {"version": self.p.actualizada_en.isoformat(), "tipo": "PAGO", "monto": self.p.saldo_pendiente, "verificado": True, "detalle": "Pago final"})
            self.p.refresh_from_db()
        aplicar(self.a.usuario, self.p.referencia, "terminar", {"version": self.p.actualizada_en.isoformat(), "confirmado": True})
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "REALIZADA")
        self.assertIsNotNone(self.p.realizada_en)

    def test_formulario_finalizado_no_ofrece_acciones_invalidas(self):
        self.p.estado = "RECHAZADA"
        self.assertEqual(GestionForm(solicitud=self.p).fields["accion"].choices, [])


class ReservasSimultaneas(TransactionTestCase):
    def test_dos_peticiones_mismo_intervalo_solo_guardan_una(self):
        a = profesional("concurrente")
        barrera = Barrier(2)
        def reservar():
            close_old_connections()
            try:
                barrera.wait(timeout=5)
                with transaction.atomic():
                    BloqueHorario.objects.create(tatuadora_id=a.pk, fecha=timezone.localdate() + timedelta(days=10), hora_inicio=time(10), hora_fin=time(11), tipo="BLOQUEO", estado="BLOQUEADO")
                return True
            except DatabaseError:
                return False
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(lambda _: reservar(), range(2)))
        self.assertEqual(resultados.count(True), 1)
        self.assertEqual(BloqueHorario.objects.count(), 1)

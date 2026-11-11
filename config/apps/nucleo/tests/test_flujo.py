from datetime import timedelta, time
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from web.models import Postulacion, Imagen, Estilo, Prediccion, EtiquetaConsolidada, BloqueHorario, Sesion, TrabajoPortafolio
from web.test_recepcion import profesional, propuesta
from .test_agenda import solicitud
from .utilidades import jpg_valido
from apps.nucleo.flujo import aplicar
from apps.nucleo.operaciones_agenda import gestionar, cerrar_bloque, guardar_bloque
from apps.nucleo.metricas import calcular


class FlujoCompleto(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.a, self.b = profesional(), profesional("otra")
        self.p = solicitud(self.a)
        self.client.force_login(self.a.usuario)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ctx = self.settings(MEDIA_ROOT=self.tmp.name)
        ctx.enable()
        self.addCleanup(ctx.disable)

    def accion(self, accion, **datos):
        self.p.refresh_from_db()
        return aplicar(self.a.usuario, self.p.referencia, accion, {"version": self.p.actualizada_en.isoformat(), **datos})

    def aceptar(self):
        gestionar(self.a.usuario, self.p.referencia, {"accion": "aceptar", "precio_final": 100000, "abono_solicitado": 30000, "alto_final_cm": 12, "ancho_final_cm": 6})
        gestionar(self.a.usuario, self.p.referencia, {"accion": "abono", "monto_abono": 30000, "verificado": True})
        self.p.refresh_from_db()

    def sesion(self, estado="RESERVADA", inicio=10):
        b = BloqueHorario.objects.create(tatuadora=self.a, tipo="CITA", fecha=timezone.localdate()-timedelta(days=1), hora_inicio=time(inicio), hora_fin=time(inicio+1), estado=estado)
        Sesion.objects.create(bloque=b, postulacion=self.p)
        return b

    def test_propuesta_guarda_contacto_preferencia_ignora_presupuesto_sin_reservar(self):
        r = Client().post(reverse("web:cotizacion"), propuesta(self.a, primer_apellido="Pérez", segundo_apellido="Soto", canal_preferido="instagram", usuario_social="@cliente", presupuesto=90000, fecha_propuesta=(timezone.localdate()+timedelta(days=5)).isoformat(), hora_propuesta="11:00"))
        self.assertEqual(r.status_code, 200)
        p = Postulacion.objects.latest("pk")
        self.assertEqual((p.contacto.apellidos, p.contacto.segundo_apellido), ("Pérez", "Soto"))
        self.assertIsNone(p.presupuesto_estimado)
        self.assertEqual(p.hora_propuesta, time(11))
        self.assertFalse(p.sesiones.exists())

    def test_preferencia_incompleta_y_contacto_sin_numero_se_rechazan(self):
        r = Client().post(reverse("web:cotizacion"), propuesta(self.a, fecha_propuesta="2030-01-10", canal_preferido="whatsapp"))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Postulacion.objects.count(), 1)

    def test_cobro_total_no_duplica_abono_y_devolucion_reduce_total(self):
        self.aceptar()
        self.accion("cobro", tipo="PAGO", monto=70000, verificado=True, detalle="Transferencia saldo")
        self.p.refresh_from_db()
        self.assertEqual(self.p.total_cobrado, 100000)
        self.assertEqual(self.p.saldo_pendiente, 0)
        self.accion("cobro", tipo="DEVOLUCION", monto=10000, verificado=True, detalle="Devolución parcial")
        self.assertEqual(self.p.total_cobrado, 90000)

    def test_doble_envio_pago_no_duplica_y_no_sobrepaga(self):
        self.aceptar()
        datos = {"version": self.p.actualizada_en.isoformat(), "tipo": "PAGO", "monto": 70000, "verificado": True, "detalle": "Saldo"}
        aplicar(self.a.usuario, self.p.referencia, "cobro", datos)
        with self.assertRaises(ValidationError):
            aplicar(self.a.usuario, self.p.referencia, "cobro", datos)
        with self.assertRaises(ValidationError):
            self.accion("cobro", tipo="PAGO", monto=1, verificado=True, detalle="Extra")
        self.assertEqual(self.p.movimientos.count(), 1)

    def test_devolucion_no_puede_exceder_recibido(self):
        self.aceptar()
        with self.assertRaises(ValidationError):
            self.accion("cobro", tipo="DEVOLUCION", monto=30001, verificado=True, detalle="Error")
        self.assertFalse(self.p.movimientos.exists())

    def test_no_asistencia_no_retiene_automaticamente_y_preserva_horario(self):
        self.aceptar()
        b = self.sesion()
        cerrar_bloque(self.a.usuario, b.referencia, "inasistencia", "No se presentó", b.actualizada_en.isoformat())
        self.p.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(b.estado, "NO_ASISTIO")
        self.assertEqual(self.p.destino_abono, "PENDIENTE")
        self.assertEqual(self.p.total_cobrado, 30000)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BloqueHorario.objects.create(tatuadora=self.a, tipo="BLOQUEO", fecha=b.fecha, hora_inicio=b.hora_inicio, hora_fin=b.hora_fin, estado="BLOQUEADO")
        self.accion("inasistencia", destino_abono="RETENIDO", detalle="Confirmado con el cliente")
        self.assertEqual(self.p.total_cobrado, 30000)

    def test_cierre_exige_sesion_realizada_y_no_anticipa_pago(self):
        self.aceptar()
        with self.assertRaises(ValidationError):
            self.accion("terminar", confirmado=True)
        self.sesion("REALIZADA")
        self.accion("terminar", confirmado=True)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "REALIZADA")
        self.assertEqual(self.p.saldo_pendiente, 70000)
        self.accion("cobro", tipo="PAGO", monto=70000, verificado=True, detalle="Pago final")
        self.assertEqual(self.p.saldo_pendiente, 0)

    def test_revision_conserva_prediccion_y_no_habilita_entrenamiento(self):
        im = Imagen.objects.create(postulacion=self.p, url="privada.jpg", orden=1, es_principal=True, formato="JPEG", ancho_px=300, alto_px=300, tamano_bytes=1000)
        e = Estilo.objects.create(codigo="ZZ-1", nombre="Estilo uno")
        otro = Estilo.objects.create(codigo="ZZ-2", nombre="Estilo dos")
        pred = Prediccion.objects.create(imagen=im, version_modelo="roboflow:test", estilo_sugerido=e, confianza_maxima=.8, tiempo_inferencia_ms=10)
        self.accion("estilo", estilo=otro.pk)
        etiqueta = EtiquetaConsolidada.objects.get(imagen=im)
        pred.refresh_from_db()
        self.assertTrue(etiqueta.fue_corregida)
        self.assertFalse(etiqueta.apta_entrenamiento)
        self.assertEqual(pred.estilo_sugerido, e)

    def test_otro_profesional_no_accede_a_gestion_metricas_ni_imagen_privada(self):
        self.client.force_login(self.b.usuario)
        r = self.client.get(reverse("nucleo:flujo", args=[self.p.referencia, "cobro"]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(calcular(self.b, timezone.localdate(), timezone.localdate())["recibidas"], 0)

    def test_metricas_no_multiplican_montos_por_sesiones(self):
        self.aceptar()
        self.sesion("REALIZADA", 10)
        self.sesion("REALIZADA", 12)
        self.accion("cobro", tipo="PAGO", monto=20000, verificado=True, detalle="Pago parcial")
        d = calcular(self.a, timezone.localdate(), timezone.localdate())
        self.assertEqual(d["totales"]["recibido"], 50000)
        self.assertEqual(d["totales"]["saldo"], 50000)
        self.assertEqual(d["ingresos"], [("Sin revisión humana", 50000)])

    def test_paginas_y_bandejas_renderizan(self):
        for nombre in ("nucleo:metricas", "nucleo:portafolio", "nucleo:portafolio_nuevo"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)
        r = self.client.get(reverse("nucleo:cotizaciones"), {"bandeja": "rechazadas"}, follow=True)
        self.assertEqual(r.context["pagina"].paginator.count, 0)
        self.assertContains(self.client.get(reverse("nucleo:metricas")), "js/metricas.js")

    def test_portafolio_publicacion_retiro_y_archivo_privado(self):
        r = self.client.post(reverse("nucleo:portafolio_nuevo"), {"titulo": "El estudio", "tipo": "ESTUDIO", "imagen": jpg_valido(), "visible": "on", "en_carrusel": "on", "autorizacion_publicacion": "on"})
        self.assertEqual(r.status_code, 302)
        trabajo = TrabajoPortafolio.objects.get()
        url = reverse("web:imagen_portafolio", args=[trabajo.referencia])
        publico = Client()
        respuesta = publico.get(url)
        self.assertEqual(respuesta.status_code, 200)
        respuesta.close()
        self.assertContains(publico.get(reverse("web:portafolio")), "El estudio")
        r = self.client.post(reverse("nucleo:portafolio_editar", args=[trabajo.referencia]), {"titulo": "Borrador", "tipo": "ESTUDIO", "version": trabajo.actualizada_en.isoformat()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(publico.get(url).status_code, 404)
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_portafolio_quitar_fotografia_borra_registro_y_archivo(self):
        from pathlib import Path
        from django.conf import settings
        self.client.post(reverse("nucleo:portafolio_nuevo"), {"titulo": "Rosa para quitar", "tipo": "ESTUDIO", "imagen": jpg_valido(), "visible": "on", "autorizacion_publicacion": "on"})
        trabajo = TrabajoPortafolio.objects.get()
        archivo = Path(settings.MEDIA_ROOT) / trabajo.url
        self.assertTrue(archivo.is_file())
        quitar = reverse("nucleo:portafolio_eliminar", args=[trabajo.referencia])
        self.assertContains(self.client.get(reverse("nucleo:portafolio_editar", args=[trabajo.referencia])), quitar)
        self.assertEqual(self.client.get(quitar).status_code, 405)
        self.client.post(quitar)  # sin confirmar no borra
        self.assertTrue(TrabajoPortafolio.objects.exists())
        self.client.force_login(self.b.usuario if hasattr(self, "b") else profesional("ajenaporta").usuario)
        self.assertEqual(self.client.post(quitar, {"confirmar": "si"}).status_code, 404)
        self.client.force_login(self.a.usuario)
        self.assertRedirects(self.client.post(quitar, {"confirmar": "si"}), reverse("nucleo:portafolio"))
        self.assertFalse(TrabajoPortafolio.objects.exists())
        self.assertFalse(archivo.exists())
        self.assertNotContains(Client().get(reverse("web:portafolio")), "Rosa para quitar")

    def test_portafolio_publicar_requiere_autorizacion(self):
        r = self.client.post(reverse("nucleo:portafolio_nuevo"), {"titulo": "No autorizado", "tipo": "ESTUDIO", "imagen": jpg_valido(), "visible": "on"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(TrabajoPortafolio.objects.exists())
        self.assertFalse(list(Path(self.tmp.name).rglob("*.jpg")))

    def test_post_privado_requiere_csrf(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.a.usuario)
        self.assertEqual(c.post(reverse("nucleo:flujo", args=[self.p.referencia, "cobro"]), {}).status_code, 403)

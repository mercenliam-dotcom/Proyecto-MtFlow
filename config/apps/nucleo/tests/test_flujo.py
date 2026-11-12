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

    def test_cobro_con_comprobante_privado_y_validado(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from web.models import MovimientoCobro
        self.aceptar()
        url = reverse("nucleo:flujo", args=[self.p.referencia, "cobro"])
        base = {"tipo": "PAGO", "monto": 5000, "verificado": "on", "detalle": "Transferencia"}
        r = self.client.get(url)  # precio 100.000, abono 30.000: resta 70.000 y viene sugerido
        self.assertContains(r, "Resta por cobrar")
        self.assertContains(r, "$70.000")
        self.assertContains(r, 'value="70000"')
        # Un PDF o un archivo que solo dice ser imagen se rechazan y no se guarda nada.
        for falso in (SimpleUploadedFile("comprobante.pdf", b"%PDF-1.4 falso", content_type="application/pdf"),
                      SimpleUploadedFile("comprobante.jpg", b"no soy una imagen", content_type="image/jpeg")):
            r = self.client.post(url, {**base, "version": self.p.actualizada_en.isoformat(), "comprobante": falso})
            self.assertEqual(r.status_code, 400)
        self.assertFalse(MovimientoCobro.objects.exists())
        self.assertFalse((Path(self.tmp.name) / "comprobantes").exists())
        r = self.client.post(url, {**base, "version": self.p.actualizada_en.isoformat(), "comprobante": jpg_valido()})
        self.assertRedirects(r, reverse("nucleo:cotizacion_detalle", args=[self.p.referencia]))
        m = MovimientoCobro.objects.get()
        self.assertTrue(m.comprobante.startswith(f"comprobantes/{self.p.referencia.hex}/"), m.comprobante)
        ver = reverse("nucleo:cobro_comprobante", args=[self.p.referencia, m.pk])
        self.assertContains(self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.p.referencia])), ver)
        r = self.client.get(ver)
        self.assertEqual((r.status_code, r["Content-Type"], r["X-Content-Type-Options"]), (200, "image/jpeg", "nosniff"))
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(ver).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(ver).status_code, 302)

    def test_cobro_rechazado_no_deja_archivo_huerfano(self):
        self.aceptar()
        url = reverse("nucleo:flujo", args=[self.p.referencia, "cobro"])
        r = self.client.post(url, {"tipo": "PAGO", "monto": 999999, "verificado": "on", "detalle": "Excede", "version": self.p.actualizada_en.isoformat(), "comprobante": jpg_valido()})
        self.assertEqual(r.status_code, 409)
        carpeta = Path(self.tmp.name) / "comprobantes"
        self.assertFalse(carpeta.exists() and any(carpeta.rglob("*.*")))

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

    def test_cierre_exige_sesion_realizada_y_pago_final(self):
        self.aceptar()
        with self.assertRaises(ValidationError):
            self.accion("terminar", confirmado=True)
        self.sesion("REALIZADA")
        # Sin el pago final no se puede terminar: queda el saldo pendiente.
        with self.assertRaisesMessage(ValidationError, "Falta confirmar el pago final"):
            self.accion("terminar", confirmado=True)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "ACEPTADA")
        self.accion("cobro", tipo="PAGO", monto=40000, verificado=True, detalle="Pago parcial")
        with self.assertRaisesMessage(ValidationError, "30.000"):
            self.accion("terminar", confirmado=True)
        self.accion("cobro", tipo="PAGO", monto=30000, verificado=True, detalle="Pago final")
        self.accion("terminar", confirmado=True)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "REALIZADA")
        self.assertEqual(self.p.saldo_pendiente, 0)

    def test_detalle_pide_pago_final_antes_de_terminar(self):
        self.aceptar()
        self.sesion("REALIZADA")
        self.client.force_login(self.a.usuario)
        url = reverse("nucleo:cotizacion_detalle", args=[self.p.referencia])
        r = self.client.get(url)
        self.assertContains(r, "Confirma el pago final")
        self.assertContains(r, "70.000")
        self.assertNotContains(r, reverse("nucleo:flujo", args=[self.p.referencia, "terminar"]))
        r = self.client.get(reverse("nucleo:flujo", args=[self.p.referencia, "terminar"]))
        self.assertContains(r, "Falta confirmar el pago final")
        self.accion("cobro", tipo="PAGO", monto=70000, verificado=True, detalle="Pago final")
        r = self.client.get(url)
        self.assertContains(r, "Pago final confirmado")
        self.assertContains(r, reverse("nucleo:flujo", args=[self.p.referencia, "terminar"]))

    def sesion_en(self, dias, estado="RESERVADA"):
        b = BloqueHorario.objects.create(tatuadora=self.a, tipo="CITA", fecha=timezone.localdate()+timedelta(days=dias), hora_inicio=time(10), hora_fin=time(12), estado=estado)
        Sesion.objects.create(bloque=b, postulacion=self.p)
        Postulacion.objects.filter(pk=self.p.pk).update(estado="RESERVADA")
        return b

    def test_pago_final_ofrece_terminar_y_cerrar_deja_solo_lectura(self):
        self.aceptar()
        hoy = self.sesion_en(0)
        url = reverse("nucleo:flujo", args=[self.p.referencia, "cobro"])
        self.p.refresh_from_db()
        r = self.client.get(url)
        self.assertContains(r, "Registrar pago final")
        r = self.client.post(url, {"version": self.p.actualizada_en.isoformat(), "tipo": "PAGO", "monto": 70000, "verificado": "on", "detalle": "Pago final"})
        detalle = reverse("nucleo:cotizacion_detalle", args=[self.p.referencia])
        self.assertRedirects(r, detalle + "?cerrar=1")
        r = self.client.get(detalle + "?cerrar=1")
        self.assertContains(r, "¿Deseas terminar los pasos ahora o continuar después?")
        self.assertContains(r, "data-abrir-al-cargar")
        self.assertNotContains(self.client.get(detalle), "data-abrir-al-cargar")  # «continuar después»
        # «Terminar ahora» envía el formulario del diálogo.
        self.p.refresh_from_db()
        r = self.client.post(reverse("nucleo:flujo", args=[self.p.referencia, "terminar"]), {"version": self.p.actualizada_en.isoformat(), "confirmado": "on"})
        self.assertRedirects(r, detalle)
        self.p.refresh_from_db(); hoy.refresh_from_db()
        self.assertEqual((self.p.estado, hoy.estado), ("REALIZADA", "REALIZADA"))
        # Cerrada: solo lectura.
        r = self.client.get(detalle)
        self.assertContains(r, "Trabajo terminado")
        self.assertNotContains(r, "Todas las acciones de esta solicitud")
        self.assertNotContains(r, url)
        self.assertRedirects(self.client.get(url), detalle)
        with self.assertRaisesMessage(ValidationError, "solicitud quedó cerrada"):
            self.accion("cobro", tipo="DEVOLUCION", monto=1000, verificado=True, detalle="Después del cierre")

    def test_no_termina_con_sesion_futura(self):
        self.aceptar()
        self.sesion_en(3)
        self.accion("cobro", tipo="PAGO", monto=70000, verificado=True, detalle="Pago adelantado")
        with self.assertRaisesMessage(ValidationError, "aún no ocurre"):
            self.accion("terminar", confirmado=True)
        r = self.client.get(reverse("nucleo:cotizacion_detalle", args=[self.p.referencia]))
        self.assertNotContains(r, 'id="dialogo-cierre"')

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
        self.assertNotContains(Client().get(reverse("web:catalogo")), "Rosa para quitar")

    def test_portafolio_varias_fotografias_a_la_vez(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        estilo = Estilo.objects.exclude(codigo="E-99").first()
        datos = {"titulo": "Rosa", "tipo": "TATUAJE", "estilo": estilo.pk, "visible": "on", "autorizacion_publicacion": "on"}
        r = self.client.post(reverse("nucleo:portafolio_nuevo"), {**datos, "imagen": [jpg_valido(), jpg_valido(), jpg_valido()]})
        self.assertRedirects(r, reverse("nucleo:portafolio"))
        self.assertEqual(sorted(TrabajoPortafolio.objects.values_list("titulo", flat=True)), ["Rosa (1/3)", "Rosa (2/3)", "Rosa (3/3)"])
        self.assertEqual(len(set(TrabajoPortafolio.objects.values_list("url", flat=True))), 3)
        # Si una es inválida, no se guarda ninguna ni queda archivo suelto.
        antes = TrabajoPortafolio.objects.count()
        falsa = SimpleUploadedFile("falsa.jpg", b"no es imagen", content_type="image/jpeg")
        r = self.client.post(reverse("nucleo:portafolio_nuevo"), {**datos, "imagen": [jpg_valido(), falsa]})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "falsa.jpg", status_code=400)
        self.assertEqual(TrabajoPortafolio.objects.count(), antes)
        # Más de 10 archivos: Django rechaza el envío completo (DATA_UPLOAD_MAX_NUMBER_FILES).
        r = self.client.post(reverse("nucleo:portafolio_nuevo"), {**datos, "imagen": [jpg_valido() for _ in range(11)]}, follow=True)
        self.assertContains(r, "hasta 10 fotografías a la vez")
        self.assertEqual(TrabajoPortafolio.objects.count(), antes)

    def test_portafolio_relaciona_trabajos_con_sesion_realizada(self):
        url = reverse("nucleo:portafolio_nuevo")
        self.assertContains(self.client.get(url), "Aún no tienes trabajos con sesiones realizadas")
        self.aceptar()
        self.sesion("REALIZADA")  # sesión realizada, trabajo aún sin cerrar
        r = self.client.get(url)
        self.assertContains(r, f'value="{self.p.pk}"')
        self.assertContains(r, "sesión realizada")

    def test_portafolio_publicar_requiere_autorizacion(self):
        r = self.client.post(reverse("nucleo:portafolio_nuevo"), {"titulo": "No autorizado", "tipo": "ESTUDIO", "imagen": jpg_valido(), "visible": "on"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(TrabajoPortafolio.objects.exists())
        self.assertFalse(list(Path(self.tmp.name).rglob("*.jpg")))

    def test_post_privado_requiere_csrf(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.a.usuario)
        self.assertEqual(c.post(reverse("nucleo:flujo", args=[self.p.referencia, "cobro"]), {}).status_code, 403)

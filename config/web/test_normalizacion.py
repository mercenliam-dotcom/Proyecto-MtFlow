from datetime import timedelta, time
from unittest.mock import patch
import tempfile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib import admin

from .models import (Cliente, ContactoSolicitud, Postulacion, BloqueHorario, Sesion,
                     Imagen, Estilo, Prediccion, ConfianzaEstilo)
from .test_recepcion import profesional, propuesta
from apps.nucleo.tests.test_agenda import solicitud
from apps.nucleo.operaciones_agenda import gestionar, guardar_bloque


class NormalizacionYValidaciones(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.a = profesional()
        self.p = solicitud(self.a)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        contexto = self.settings(MEDIA_ROOT=self.tmp.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.client.force_login(self.a.usuario)

    def test_atributos_independientes_y_derivados_no_persistidos(self):
        campos = {f.name for f in Postulacion._meta.fields}
        self.assertTrue({"color", "nivel_detalle", "cobertura"} <= campos)
        self.assertFalse({"area_cm2", "categoria_tamano", "bloque"} & campos)
        self.assertNotIn("postulacion", {f.name for f in BloqueHorario._meta.fields})
        self.p.alto_cm, self.p.ancho_cm = 8, 4
        self.assertEqual(self.p.area_cm2, 32)
        self.assertEqual(self.p.categoria_tamano, "mediano")

    def test_nuevo_envio_guarda_cliente_y_contacto_historico(self):
        identidades = Cliente.objects.count()
        r = self.client.post(reverse("web:cotizacion"), propuesta(self.a, nombre="Persona nueva", color="color", detalle="alto", cobertura="on"))
        self.assertContains(r, "Propuesta recibida")
        p = Postulacion.objects.latest("pk")
        self.assertIsNotNone(p.cliente_id)
        self.assertIsNone(p.cliente.usuario_id)
        self.assertEqual(Cliente.objects.count(), identidades + 1)
        self.assertEqual(p.contacto.nombres, "Persona nueva")
        self.assertEqual((p.descripcion, p.color, p.nivel_detalle, p.cobertura), ("Una flor", "color", "alto", True))

    def test_cambio_identidad_no_reescribe_contacto_de_solicitud(self):
        antes = self.p.contacto.nombres
        Cliente.objects.filter(pk=self.p.cliente_id).update(nombres="Otro nombre")
        self.p.refresh_from_db()
        self.assertEqual(self.p.contacto.nombres, antes)

    def test_contacto_unico_por_envio(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContactoSolicitud.objects.create(postulacion=self.p, nombres="Duplicado")

    def test_formulario_rechaza_controles_telefono_y_dimensiones_invalidas(self):
        for extra in ({"nombre": "Persona\nOtra"}, {"idea": "texto\x00oculto"}, {"telefono": "https://malicioso"}, {"alto_cm": "NaN"}, {"ancho_cm": "0"}, {"alto_cm": "1000"}):
            with self.subTest(extra=extra), patch("web.views.clasificar") as ml:
                r = self.client.post(reverse("web:cotizacion"), propuesta(self.a, **extra))
                self.assertEqual(r.status_code, 400)
                ml.assert_not_called()
        self.assertEqual(Postulacion.objects.count(), 1)

    def test_servicio_rechaza_importes_y_acciones_sin_confiar_en_la_vista(self):
        for datos in ({"accion": "aceptar", "precio_final": -1}, {"accion": "aceptar", "precio_final": 100000001}, {"accion": "inventada"}, {"accion": "rechazar", "motivo": ""}):
            with self.subTest(datos=datos), self.assertRaises(ValidationError):
                gestionar(self.a.usuario, self.p.referencia, datos)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "RECIBIDA")
        self.assertFalse(self.p.eventos.exists())

    def test_reenvio_abono_no_duplica_verificacion(self):
        gestionar(self.a.usuario, self.p.referencia, {"accion": "aceptar", "precio_final": 100000})
        datos = {"accion": "abono", "monto_abono": 30000, "verificado": True}
        p = gestionar(self.a.usuario, self.p.referencia, datos)
        fecha = p.abono_verificado_en
        p = gestionar(self.a.usuario, self.p.referencia, datos)
        self.assertEqual(p.abono_verificado_en, fecha)
        self.assertEqual(p.eventos.filter(tipo="abono").count(), 1)

    def test_http_exige_version_y_rechaza_formulario_obsoleto(self):
        url = reverse("nucleo:cotizacion_gestion", args=[self.p.referencia])
        datos = {"accion": "aceptar", "precio_final": 100000}
        self.assertEqual(self.client.post(url, datos).status_code, 400)
        datos["version"] = self.p.actualizada_en.isoformat()
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        r = self.client.post(url, datos | {"precio_final": 90000})
        self.assertContains(r, "cambió en otra ventana", status_code=409)
        self.p.refresh_from_db()
        self.assertEqual(self.p.precio_final, 100000)

    def test_base_rechaza_datos_invalidos_aun_sin_formulario(self):
        for valores in ({"alto_cm": 0}, {"ancho_cm": 1000}, {"precio_final": -1}, {"precio_final": 100, "monto_abono": 200}, {"estado": "INVENTADO"}, {"color": "inventado"}, {"nivel_detalle": "inventado"}, {"abono_verificado_en": timezone.now()}):
            with self.subTest(valores=valores), self.assertRaises(IntegrityError), transaction.atomic():
                Postulacion.objects.filter(pk=self.p.pk).update(**valores)

    def bloque(self, artista=None, tipo="CITA", estado="RESERVADA"):
        return BloqueHorario.objects.create(tatuadora=artista or self.a, fecha=timezone.localdate()+timedelta(days=10), hora_inicio=time(10), hora_fin=time(11), tipo=tipo, estado=estado)

    def test_sesion_no_admite_otra_tatuadora_ni_bloque_personal(self):
        otra = profesional("segunda")
        for bloque in [self.bloque(otra), self.bloque(tipo="BLOQUEO", estado="BLOQUEADO")]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                Sesion.objects.create(bloque=bloque, postulacion=self.p)

    def test_no_se_puede_reasignar_solicitud_ni_bloque_con_sesion(self):
        bloque = self.bloque()
        Sesion.objects.create(bloque=bloque, postulacion=self.p)
        otra = profesional("segunda")
        for objeto in (self.p, bloque):
            with self.assertRaises(IntegrityError), transaction.atomic():
                type(objeto).objects.filter(pk=objeto.pk).update(tatuadora=otra)

    def test_admin_operativo_es_solo_lectura(self):
        request = type("Request", (), {"user": self.a.usuario})()
        for modelo in (Postulacion, BloqueHorario, Sesion, Imagen, ContactoSolicitud):
            administrador = admin.site._registry[modelo]
            self.assertFalse(administrador.has_add_permission(request))
            self.assertFalse(administrador.has_change_permission(request))
            self.assertFalse(administrador.has_delete_permission(request))

    def test_imagen_principal_y_confianzas_restringidas(self):
        campos = dict(postulacion=self.p, url="prueba.jpg", orden=1, es_principal=True, formato="JPEG", ancho_px=300, alto_px=300, tamano_bytes=100)
        imagen = Imagen.objects.create(**campos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Imagen.objects.create(**(campos | {"orden": 2, "url": "otra.jpg"}))
        estilo = Estilo.objects.create(codigo="TEST", nombre="Prueba")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Prediccion.objects.create(imagen=imagen, version_modelo="prueba", estilo_sugerido=estilo, confianza_maxima="1.1", tiempo_inferencia_ms=1)

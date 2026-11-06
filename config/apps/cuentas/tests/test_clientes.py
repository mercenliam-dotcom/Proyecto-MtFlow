from datetime import time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.cache import cache
from django.db import transaction, IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.cuentas.models import Usuario, Rol, PerfilCliente
from apps.nucleo.firmas import url_archivo
from apps.nucleo.tests.test_agenda import solicitud
from web.models import Postulacion, Tatuadora, Imagen, BloqueHorario, Sesion, EventoSolicitud, Prediccion, Estilo
from web.test_recepcion import profesional, propuesta


def cliente(nombre="cliente1", **extra):
    return Usuario.objects.create_user(nombre, f"{nombre}@example.test", "Clave2026PersonalSegura", nombre="María", apellido="Pérez", rol=Rol.CLIENTE, debe_cambiar_contrasena=False, **extra)


class PortalClientes(TestCase):
    def setUp(self):
        cache.clear()
        self.a = profesional()
        self.u, self.otro = cliente(), cliente("cliente2")
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        contexto = self.settings(MEDIA_ROOT=self.tmp.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.client.force_login(self.u)

    def envio(self, **extra):
        r = self.client.post(reverse("web:cotizacion"), propuesta(self.a, **extra))
        self.assertEqual(r.status_code, 200)
        return Postulacion.objects.latest("pk")

    def test_registro_no_permite_elegir_rol_o_privilegios(self):
        c = Client()
        datos = {"nombre_usuario": "nuevo123", "nombre": "Persona", "apellido": "Nueva", "email": "nuevo@example.test", "password1": "Clave2026PersonalSegura", "password2": "Clave2026PersonalSegura", "rol": "ADMIN", "es_tatuadora": "on", "is_superuser": "on", "is_staff": "on", "es_admin_desarrollo": "on", "debe_cambiar_contrasena": "on"}
        r = c.post(reverse("clientes:registro"), datos)
        self.assertRedirects(r, reverse("clientes:inicio"))
        u = Usuario.objects.get(nombre_usuario="nuevo123")
        self.assertEqual(u.rol, Rol.CLIENTE)
        self.assertFalse(any([u.es_tatuadora, u.is_superuser, u.is_staff, u.es_admin_desarrollo, u.debe_cambiar_contrasena]))
        self.assertTrue(u.check_password(datos["password1"]))
        self.assertTrue(PerfilCliente.objects.filter(usuario=u).exists())
        self.assertFalse(Tatuadora.objects.filter(usuario=u).exists())

    def test_registro_valida_contrasena_y_limita_intentos(self):
        c = Client()
        datos = {"nombre_usuario": "nuevo123", "nombre": "Persona", "apellido": "Nueva", "email": "nuevo@example.test", "password1": "123", "password2": "123"}
        for _ in range(5):
            self.assertEqual(c.post(reverse("clientes:registro"), datos).status_code, 400)
        self.assertEqual(c.post(reverse("clientes:registro"), datos).status_code, 429)
        self.assertFalse(Usuario.objects.filter(nombre_usuario="nuevo123").exists())

    def test_registro_y_perfil_exigen_csrf(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(reverse("clientes:registro"), {}).status_code, 403)
        c.force_login(self.u)
        self.assertEqual(c.post(reverse("clientes:perfil"), {}).status_code, 403)

    def test_base_impide_cliente_tatuadora_o_superusuario(self):
        for campos in ({"es_tatuadora": True}, {"is_superuser": True}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Usuario.objects.filter(pk=self.u.pk).update(**campos)

    def test_cliente_no_accede_a_urls_del_equipo(self):
        p = solicitud(self.a)
        rutas = [("cuentas:lista", []), ("cuentas:crear", []), ("cuentas:editar", [self.a.usuario.uuid]), ("cuentas:restablecer", [self.a.usuario.uuid]), ("nucleo:cotizaciones", []), ("nucleo:cotizacion_detalle", [p.referencia]), ("nucleo:agenda", []), ("nucleo:agenda_nuevo", []), ("nucleo:agenda_eventos", []), ("nucleo:metricas", []), ("nucleo:portafolio", []), ("nucleo:portafolio_nuevo", []), ("nucleo:equipo_cotizaciones", []), ("clasificacion:probar", [])]
        for nombre, args in rutas:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 403)
        self.assertEqual(self.client.post(reverse("nucleo:cotizacion_gestion", args=[p.referencia]), {"accion": "aceptar", "precio_final": 1}).status_code, 403)
        self.assertEqual(self.client.post(reverse("nucleo:flujo", args=[p.referencia, "cobro"]), {"monto": 999999}).status_code, 403)
        p.refresh_from_db()
        self.assertIsNone(p.precio_final)

    def test_anonimo_no_accede_y_equipo_no_se_confunde_con_cliente(self):
        self.assertEqual(Client().get(reverse("clientes:inicio")).status_code, 302)
        self.client.force_login(self.a.usuario)
        self.assertEqual(self.client.get(reverse("clientes:inicio")).status_code, 403)
        self.assertEqual(self.client.get(reverse("nucleo:cotizaciones")).status_code, 200)

    def test_inicio_y_login_dirigen_al_portal_sin_redireccion_externa(self):
        self.assertRedirects(self.client.get(reverse("nucleo:inicio")), reverse("clientes:inicio"))
        for destino in ("/panel/metricas/", "https://malicioso.example/", "//malicioso.example/"):
            c = Client()
            r = c.post(reverse("cuentas:login"), {"nombre_usuario": self.u.nombre_usuario, "password": "Clave2026PersonalSegura", "next": destino})
            self.assertRedirects(r, reverse("clientes:inicio"))

    def test_navegacion_cliente_sin_opciones_del_equipo(self):
        r = self.client.get(reverse("clientes:inicio"))
        self.assertContains(r, "Mis solicitudes")
        self.assertContains(r, "Mi perfil")
        for nombre in ("nucleo:agenda", "nucleo:metricas", "cuentas:crear", "nucleo:portafolio", "clasificacion:probar"):
            self.assertNotContains(r, f'href="{reverse(nombre)}"')

    def test_solicitud_se_asocia_solo_a_sesion_no_al_id_enviado(self):
        p = self.envio(cuenta_cliente=self.otro.pk, usuario=self.otro.pk, estado="REALIZADA", precio_final=1)
        self.assertEqual(p.cuenta_cliente, self.u)
        self.assertEqual(p.estado, "RECIBIDA")
        self.assertIsNone(p.precio_final)
        self.assertContains(self.client.get(reverse("clientes:inicio")), str(p.referencia))
        self.client.force_login(self.otro)
        self.assertNotContains(self.client.get(reverse("clientes:inicio")), str(p.referencia))
        self.assertEqual(self.client.get(reverse("clientes:detalle", args=[p.referencia])).status_code, 404)
        self.assertEqual(self.client.post(reverse("clientes:detalle", args=[p.referencia]), {}).status_code, 405)

    def test_imagen_privada_del_cliente_y_prohibicion_del_archivo_del_equipo(self):
        p = self.envio()
        url = reverse("clientes:imagen", args=[p.referencia, 1])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-store", r["Cache-Control"])
        r.close()
        self.assertEqual(self.client.get(url_archivo(p.imagen_set.get().url)).status_code, 403)
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 302)

    def test_correo_coincidente_no_recupera_solicitudes_anonimas(self):
        c = Client()
        r = c.post(reverse("web:cotizacion"), propuesta(self.a, email=self.u.email, cuenta_cliente=self.u.pk))
        self.assertEqual(r.status_code, 200)
        p = Postulacion.objects.latest("pk")
        self.assertIsNone(p.cuenta_cliente_id)
        self.assertEqual(self.client.get(reverse("clientes:detalle", args=[p.referencia])).status_code, 404)

    def test_repetir_envio_ajeno_no_lo_vincula_ni_revela(self):
        from web.forms import token_envio
        token = token_envio()
        p = self.envio(envio=token)
        self.client.force_login(self.otro)
        r = self.client.post(reverse("web:cotizacion"), propuesta(self.a, envio=token))
        self.assertEqual(r.status_code, 409)
        self.assertNotContains(r, str(p.referencia), status_code=409)
        self.assertEqual(Postulacion.objects.count(), 1)
        p.refresh_from_db()
        self.assertEqual(p.cuenta_cliente, self.u)

    def test_repetir_envio_propio_es_idempotente(self):
        from web.forms import token_envio
        token = token_envio()
        p = self.envio(envio=token)
        r = self.client.post(reverse("web:cotizacion"), propuesta(self.a, envio=token))
        self.assertContains(r, "ya fue recibida")
        self.assertEqual(Postulacion.objects.count(), 1)
        self.assertContains(r, reverse("clientes:detalle", args=[p.referencia]))

    def test_detalle_no_revela_confianza_notas_ni_historial_interno(self):
        p = self.envio()
        p.precio_final, p.monto_abono, p.estado, p.abono_verificado_en = 100000, 30000, "RESERVADA", timezone.now()
        p.motivo_rechazo = "NOTA_PRIVADA_RECHAZO"
        p.save()
        EventoSolicitud.objects.create(postulacion=p, actor=self.a.usuario, tipo="interno", detalle="EVENTO_PRIVADO")
        b = BloqueHorario.objects.create(tatuadora=self.a, tipo="CITA", estado="RESERVADA", fecha=timezone.localdate()+timedelta(days=1), hora_inicio=time(11), hora_fin=time(12), nota="NOTA_PRIVADA_AGENDA")
        Sesion.objects.create(bloque=b, postulacion=p)
        Prediccion.objects.create(imagen=p.imagen_set.get(), version_modelo="MODELO_PRIVADO", estilo_sugerido=Estilo.objects.get(codigo="E-05"), confianza_maxima=".918765", tiempo_inferencia_ms=10)
        r = self.client.get(reverse("clientes:detalle", args=[p.referencia]))
        self.assertContains(r, "100000 CLP")
        self.assertContains(r, "30000 CLP")
        self.assertContains(r, "70000 CLP")
        self.assertContains(r, "11:00")
        for secreto in ("NOTA_PRIVADA", "EVENTO_PRIVADO", "MODELO_PRIVADO", "91,8765", "Confianza", "historial"):
            self.assertNotContains(r, secreto)

    def test_perfil_no_modifica_rol_ni_solicitudes_anteriores_y_precarga_nuevas(self):
        p = self.envio(nombre="Nombre original")
        datos = {"datos-nombre": "Nombre nuevo", "datos-apellido": "Soto", "datos-email": self.u.email, "contacto-segundo_apellido": "Díaz", "contacto-telefono": "+56912345678", "contacto-canal_preferido": "whatsapp", "rol": "ADMIN", "es_tatuadora": "on", "usuario": self.otro.pk}
        self.assertRedirects(self.client.post(reverse("clientes:perfil"), datos), reverse("clientes:perfil"))
        self.u.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(self.u.rol, Rol.CLIENTE)
        self.assertFalse(self.u.es_tatuadora)
        self.assertEqual(p.contacto.nombres, "Nombre original")
        self.assertEqual(self.u.nombre, "Nombre nuevo")
        r = self.client.get(reverse("web:cotizacion"))
        self.assertEqual(r.context["form"].initial["nombre"], "Nombre nuevo")
        self.assertEqual(r.context["form"].initial["telefono"], "+56912345678")

    def test_cambio_correo_exige_contrasena_actual(self):
        datos = {"datos-nombre": self.u.nombre, "datos-apellido": self.u.apellido, "datos-email": "nuevo@example.test", "contacto-canal_preferido": "correo"}
        self.assertEqual(self.client.post(reverse("clientes:perfil"), datos).status_code, 400)
        self.u.refresh_from_db()
        self.assertEqual(self.u.email, "cliente1@example.test")
        datos["datos-actual"] = "Clave2026PersonalSegura"
        self.assertEqual(self.client.post(reverse("clientes:perfil"), datos).status_code, 302)
        self.u.refresh_from_db()
        self.assertEqual(self.u.email, "nuevo@example.test")

    def test_cliente_cambia_su_contrasena_sin_obtener_acceso_al_equipo(self):
        r = self.client.post(reverse("cuentas:mi_contrasena"), {"actual": "Clave2026PersonalSegura", "password1": "OtraClave2027PersonalSegura", "password2": "OtraClave2027PersonalSegura"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Mis solicitudes")
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("OtraClave2027PersonalSegura"))
        self.assertEqual(self.client.get(reverse("nucleo:agenda")).status_code, 403)

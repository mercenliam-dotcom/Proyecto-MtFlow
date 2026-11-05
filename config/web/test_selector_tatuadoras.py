import tempfile

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.cuentas.forms import EditarCuentaForm
from apps.cuentas.models import Rol, Usuario

from .forms import CotizacionForm
from .models import Postulacion, Tatuadora
from .test_recepcion import profesional, propuesta


class SelectorTatuadoras(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media_settings = self.settings(MEDIA_ROOT=self.tmp.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.artista = profesional()
        self.url = reverse("web:cotizacion")

    def test_selector_muestra_nombre_de_la_cuenta_no_alias_antiguo(self):
        Tatuadora.objects.filter(pk=self.artista.pk).update(nombre_artistico="Nueva Artista")
        self.artista.usuario.nombre = "Amanda"
        self.artista.usuario.apellido = "Maldonado"
        self.artista.usuario.save(update_fields=["nombre", "apellido"])
        r = self.client.get(self.url)
        self.assertContains(r, f'value="{self.artista.pk}">Amanda Maldonado</option>')
        self.assertNotContains(r, "Nueva Artista")

    def test_cambios_en_cuenta_se_reflejan_sin_editar_perfil(self):
        user = self.artista.usuario
        user.nombre = "Nombre Actual"
        user.save(update_fields=["nombre"])
        opciones = dict((str(obj.pk), str(obj)) for obj in CotizacionForm().fields["tatuadora"].queryset)
        self.assertEqual(opciones[str(self.artista.pk)], "Nombre Actual Rojas")

    def test_no_ofrece_perfiles_ni_cuentas_desactivados(self):
        inactiva = profesional("inactiva")
        cuenta_inactiva = profesional("sinacceso")
        Tatuadora.objects.filter(pk=inactiva.pk).update(activa=False)
        user = cuenta_inactiva.usuario
        user.is_active = False
        user.save(update_fields=["is_active"])
        opciones = set(CotizacionForm().fields["tatuadora"].queryset.values_list("pk", flat=True))
        self.assertEqual(opciones, {self.artista.pk})

    def test_propuesta_llega_a_la_cuenta_elegida_y_no_a_otra(self):
        elegida = profesional("elegida")
        Tatuadora.objects.filter(pk=elegida.pk).update(nombre_artistico="Nombre antiguo")
        r = self.client.post(self.url, propuesta(elegida))
        self.assertEqual(r.status_code, 200)
        postulacion = Postulacion.objects.get()
        self.assertEqual(postulacion.tatuadora.usuario_id, elegida.usuario_id)
        self.assertNotContains(r, "Nombre antiguo")
        self.client.force_login(elegida.usuario)
        r = self.client.get(reverse("nucleo:cotizaciones"))
        self.assertContains(r, str(postulacion.referencia))
        self.client.force_login(self.artista.usuario)
        self.assertNotContains(self.client.get(reverse("nucleo:cotizaciones")), str(postulacion.referencia))

    def test_administradora_tatuadora_puede_recibir_y_consultar(self):
        admin = Usuario.objects.create_superuser("admin01", "admin@example.com", "Tinta2026segura", nombre="Amanda", apellido="Rojas", es_tatuadora=True)
        perfil = Tatuadora.objects.get(usuario=admin)
        self.assertIn(perfil, CotizacionForm().fields["tatuadora"].queryset)
        self.assertEqual(self.client.post(self.url, propuesta(perfil)).status_code, 200)
        p = Postulacion.objects.get()
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("nucleo:cotizaciones")), str(p.referencia))

    def test_administracion_sin_funcion_tatuadora_no_aparece(self):
        admin = Usuario.objects.create_superuser("admin01", "admin@example.com", "Tinta2026segura", nombre="Admin", apellido="Local")
        self.assertFalse(Tatuadora.objects.filter(usuario=admin).exists())
        self.assertNotIn(admin.pk, CotizacionForm().fields["tatuadora"].queryset.values_list("usuario_id", flat=True))

    def test_editar_cuenta_habilita_funcion_sin_cambiar_rol_y_sin_duplicar(self):
        admin = Usuario.objects.create_superuser("admin01", "admin@example.com", "Tinta2026segura", nombre="Amanda", apellido="Rojas")
        form = EditarCuentaForm(data=dict(nombre=admin.nombre, apellido=admin.apellido, email=admin.email, rol=Rol.ADMIN, es_tatuadora="on", is_active="on"), instance=admin, editor=admin)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        admin.refresh_from_db()
        admin.save()
        self.assertTrue(admin.es_admin)
        self.assertTrue(admin.es_tatuadora)
        self.assertEqual(Tatuadora.objects.filter(usuario=admin).count(), 1)

    def test_quitar_funcion_oculta_selector_y_conserva_historial(self):
        self.client.post(self.url, propuesta(self.artista))
        user = self.artista.usuario
        user.es_tatuadora = False
        user.save(update_fields=["es_tatuadora"])
        self.assertNotIn(self.artista, CotizacionForm().fields["tatuadora"].queryset)
        self.assertTrue(Tatuadora.objects.filter(pk=self.artista.pk).exists())
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("nucleo:cotizaciones")), str(Postulacion.objects.get().referencia))

    def test_ser_tatuadora_no_concede_administracion(self):
        self.assertTrue(self.artista.usuario.es_tatuadora)
        self.assertFalse(self.artista.usuario.es_admin)
        self.client.force_login(self.artista.usuario)
        self.assertEqual(self.client.get(reverse("cuentas:lista")).status_code, 403)

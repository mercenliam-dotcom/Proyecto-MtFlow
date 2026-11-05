import asyncio
from unittest.mock import AsyncMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.db.models.deletion import RestrictedError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.cuentas.arranque import ArranqueASGI, preparar_admin_entorno
from apps.cuentas.models import Rol, Usuario


@override_settings(DEBUG=True)
class AdminDesarrollo(TestCase):
    def test_crea_admin_sin_perfil_de_tatuadora_y_sin_forzar_cambio(self):
        preparar_admin_entorno()
        admin = Usuario.objects.get(nombre_usuario="admin")
        self.assertTrue(admin.es_admin_desarrollo)
        self.assertTrue(admin.es_admin)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("admin"))
        self.assertNotEqual(admin.password, "admin")
        self.assertFalse(admin.debe_cambiar_contrasena)
        self.assertFalse(admin.es_tatuadora)

    def test_repetir_arranque_no_duplica_y_restaura_cuenta_predeterminada(self):
        preparar_admin_entorno()
        admin = Usuario.objects.get(nombre_usuario="admin")
        admin.is_active = False
        admin.set_password("otra-password")
        admin.save()
        preparar_admin_entorno()
        admin.refresh_from_db()
        self.assertEqual(Usuario.objects.filter(nombre_usuario="admin").count(), 1)
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.check_password("admin"))

    def test_no_sobrescribe_un_admin_legitimo(self):
        admin = Usuario.objects.create_superuser("admin", "real@example.test", "ClaveReal2026",
                                                 nombre="Ana", apellido="Rojas")
        preparar_admin_entorno()
        admin.refresh_from_db()
        self.assertFalse(admin.es_admin_desarrollo)
        self.assertTrue(admin.check_password("ClaveReal2026"))

    def test_produccion_elimina_default_incluso_renombrado_y_conserva_otros(self):
        preparar_admin_entorno()
        admin = Usuario.objects.get(nombre_usuario="admin")
        admin.nombre_usuario = "anterioradmin"
        admin.save()
        real = Usuario.objects.create_superuser("admin", "real@example.test", "ClaveReal2026",
                                                nombre="Ana", apellido="Rojas")
        with self.settings(DEBUG=False):
            preparar_admin_entorno()
            preparar_admin_entorno()
        self.assertFalse(Usuario.objects.filter(es_admin_desarrollo=True).exists())
        self.assertTrue(Usuario.objects.filter(pk=real.pk).exists())

    def test_no_crea_default_en_produccion(self):
        with self.settings(DEBUG=False):
            preparar_admin_entorno()
        self.assertFalse(Usuario.objects.filter(nombre_usuario="admin").exists())

    def test_dependencias_impiden_produccion_y_desactivan_la_cuenta(self):
        preparar_admin_entorno()
        with self.settings(DEBUG=False), patch.object(Usuario, "delete", side_effect=RestrictedError("vinculado", [])):
            with self.assertRaises(ImproperlyConfigured):
                preparar_admin_entorno()
        admin = Usuario.objects.get(nombre_usuario="admin")
        self.assertFalse(admin.is_active)
        self.assertFalse(admin.has_usable_password())


class ArranqueAsincrono(SimpleTestCase):
    async def test_asgi_prepara_una_vez_ante_peticiones_concurrentes(self):
        app = AsyncMock()
        wrapper = ArranqueASGI(app)
        with patch("apps.cuentas.arranque.preparar_admin_entorno") as preparar:
            await asyncio.gather(*(wrapper({}, AsyncMock(), AsyncMock()) for _ in range(4)))
        preparar.assert_called_once()
        self.assertEqual(app.await_count, 4)

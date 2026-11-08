from django.test import TestCase, Client
from django.urls import reverse
from web.test_recepcion import profesional
from .test_clientes import cliente


class PerfilPersonal(TestCase):
    def setUp(self):
        self.a = profesional()
        self.b = profesional('otraartista')
        self.client.force_login(self.a.usuario)
        self.url = reverse('cuentas:perfil')

    def datos(self, **extra):
        return {'datos-nombre':'Amanda','datos-apellido':'Rojas','datos-email':self.a.usuario.email,'contacto-telefono':'+56912345678', **extra}

    def test_edita_solo_cuenta_propia_y_sin_permisos(self):
        r = self.client.post(self.url, self.datos(usuario=self.b.usuario_id, rol='USUARIO', es_tatuadora=''))
        self.assertRedirects(r, self.url)
        self.a.refresh_from_db(); self.b.refresh_from_db(); self.a.usuario.refresh_from_db()
        self.assertEqual(self.a.telefono, '+56912345678')
        self.assertEqual(self.b.telefono, '')
        self.assertEqual(self.a.usuario.nombre, 'Amanda')
        self.assertEqual(self.a.usuario.rol, 'ADMIN')
        self.assertTrue(self.a.usuario.es_tatuadora)

    def test_correo_exige_clave_y_telefono_valido(self):
        self.assertEqual(self.client.post(self.url, self.datos(**{'datos-email':'nuevo@example.test'})).status_code, 400)
        self.assertEqual(self.client.post(self.url, self.datos(**{'contacto-telefono':'no-es-telefono'})).status_code, 400)
        self.a.refresh_from_db()
        self.assertEqual(self.a.telefono, '')

    def test_cliente_ve_su_perfil_sin_portafolio_ni_otras_cuentas(self):
        u = cliente()
        self.client.force_login(u)
        self.assertRedirects(self.client.get(self.url), reverse('clientes:perfil'))
        r = self.client.get(reverse('clientes:perfil'))
        self.assertContains(r, 'Editar mis datos')
        self.assertNotContains(r, 'Editar mi portafolio')
        self.assertNotContains(r, 'Cuentas del equipo')
        self.assertContains(r, 'Cambiar de cuenta')

    def test_perfil_privado_csrf_y_menu(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        c = Client(enforce_csrf_checks=True); c.force_login(self.a.usuario)
        self.assertEqual(c.post(self.url, self.datos()).status_code, 403)
        r = self.client.get(self.url)
        self.assertIn('no-store', r['Cache-Control'])
        self.assertContains(r, 'Editar mi portafolio')
        self.assertContains(r, 'aria-controls="barra-lateral"')
        self.assertContains(r, 'Cerrar sesión')

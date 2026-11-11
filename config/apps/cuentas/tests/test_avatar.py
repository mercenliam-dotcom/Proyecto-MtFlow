import io
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from PIL import Image
from web.test_recepcion import profesional
from .test_clientes import cliente


def icono(formato="PNG", lado=96):
    """Ícono plano (sin textura): debe aceptarse aunque no sea «nítido»."""
    buf = io.BytesIO()
    Image.new("RGBA" if formato == "PNG" else "RGB", (lado, lado), (98, 65, 139)).save(buf, format=formato)
    ext = "png" if formato == "PNG" else "jpg"
    return SimpleUploadedFile(f"icono.{ext}", buf.getvalue(), content_type=f"image/{'png' if ext == 'png' else 'jpeg'}")


class FotoDePerfil(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ctx = self.settings(MEDIA_ROOT=self.tmp.name)
        ctx.enable()
        self.addCleanup(ctx.disable)
        self.a, self.b = profesional(), profesional("otraavatar")
        self.client.force_login(self.a.usuario)

    def test_subir_icono_plano_se_recorta_y_se_muestra(self):
        self.assertRedirects(self.client.post(reverse("cuentas:avatar_subir"), {"avatar": icono(lado=300)}), reverse("cuentas:perfil"))
        self.a.usuario.refresh_from_db()
        ruta = Path(self.tmp.name) / self.a.usuario.avatar
        self.assertTrue(ruta.is_file())
        self.assertEqual(Image.open(ruta).size, (320, 320))
        url = reverse("cuentas:avatar_imagen", args=[self.a.usuario.uuid])
        self.assertContains(self.client.get(reverse("cuentas:perfil")), url)
        r = self.client.get(url)
        self.assertEqual((r.status_code, r["Content-Type"], r["X-Content-Type-Options"]), (200, "image/png", "nosniff"))
        # El equipo la ve; un cliente o alguien sin sesión, no.
        self.client.force_login(self.b.usuario)
        self.assertEqual(self.client.get(url).status_code, 200)
        c = Client(); c.force_login(cliente("clienteavatar"))
        self.assertEqual(c.get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 302)

    def test_reemplazar_y_quitar_borra_archivos(self):
        self.client.post(reverse("cuentas:avatar_subir"), {"avatar": icono()})
        self.a.usuario.refresh_from_db(); primera = Path(self.tmp.name) / self.a.usuario.avatar
        self.client.post(reverse("cuentas:avatar_subir"), {"avatar": icono("JPEG")})
        self.a.usuario.refresh_from_db(); segunda = Path(self.tmp.name) / self.a.usuario.avatar
        self.assertFalse(primera.exists()); self.assertTrue(segunda.exists())
        self.client.post(reverse("cuentas:avatar_quitar"))
        self.a.usuario.refresh_from_db()
        self.assertEqual(self.a.usuario.avatar, ""); self.assertFalse(segunda.exists())

    def test_rechaza_lo_que_no_es_jpg_png(self):
        for falso in (SimpleUploadedFile("foto.png", b"<svg onload=alert(1)>", content_type="image/png"),
                      SimpleUploadedFile("foto.gif", b"GIF89a" + b"0" * 50, content_type="image/gif"),
                      icono(lado=32)):
            self.client.post(reverse("cuentas:avatar_subir"), {"avatar": falso})
        self.a.usuario.refresh_from_db()
        self.assertEqual(self.a.usuario.avatar, "")
        self.assertEqual(self.client.get(reverse("cuentas:avatar_subir")).status_code, 405)

    def test_perfil_sin_acceso_social_por_defecto(self):
        self.assertNotContains(self.client.get(reverse("cuentas:perfil")), "Google y Facebook")
        self.assertNotContains(Client().get(reverse("cuentas:login")), "Continuar con Google")

"""Seguridad a nivel HTTP: host, cabeceras, plantillas, URLs firmadas."""
from pathlib import Path
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.cuentas.models import Rol, Usuario
from apps.nucleo.firmas import firmar_ruta, url_archivo

from . import utilidades as u


def usuario():
    x = Usuario.objects.create_user("tatuadora1", "t@e.cl", "Tinta2026segura",
                                    nombre="Ana", apellido="Rojas", rol=Rol.USUARIO)
    x.debe_cambiar_contrasena = False
    x.save()
    return x


class HostHeader(TestCase):
    def test_host_falso_rechazado(self):
        r = self.client.get(reverse("cuentas:login"), HTTP_HOST="sitio-malicioso.com")
        self.assertEqual(r.status_code, 400)

    def test_x_forwarded_host_ignorado(self):
        r = self.client.get(reverse("nucleo:inicio"), HTTP_X_FORWARDED_HOST="sitio-malicioso.com")
        self.assertNotIn("sitio-malicioso", r.get("Location", ""))


class Cabeceras(TestCase):
    def test_cabeceras_de_seguridad(self):
        r = self.client.get(reverse("cuentas:login"))
        csp = r["Content-Security-Policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("media-src 'none'", csp)
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("camera=()", r["Permissions-Policy"])

    def test_paginas_autenticadas_no_se_guardan_en_cache(self):
        self.client.force_login(usuario())
        self.assertEqual(self.client.get(reverse("nucleo:inicio"))["Cache-Control"], "no-store")

    def test_plantillas_escapan_html(self):
        x = usuario()
        x.nombre = "Ana"
        x.apellido = "Rojas"
        x.save()
        # Un valor malicioso que llegara a la plantilla se muestra como texto
        Usuario.objects.filter(pk=x.pk).update(nombre="<script>alert(1)</script>")
        self.client.force_login(Usuario.objects.get(pk=x.pk))
        r = self.client.get(reverse("nucleo:inicio"))
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")

    def test_no_hay_scripts_en_linea_en_plantillas(self):
        base = Path(__file__).resolve().parents[3]
        plantillas = list((base / "templates").rglob("*.html")) + list((base / "web" / "templates").rglob("*.html"))
        self.assertGreater(len(plantillas), 10)
        for plantilla in plantillas:
            texto = plantilla.read_text(encoding="utf-8")
            # Se permiten scripts externos propios (<script src=...>), no código en línea
            self.assertNotRegex(texto, r"<script(?![^>]*\bsrc=)", plantilla.name)
            self.assertNotIn("|safe", texto, plantilla.name)
            self.assertNotIn("autoescape off", texto, plantilla.name)
            self.assertNotRegex(texto, r"\sstyle=", plantilla.name)  # data-style= sí se permite

    def test_error_404_no_filtra_detalles(self):
        r = self.client.get("/no-existe/../../etc/passwd")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"Traceback", r.content)


class UrlsFirmadas(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.media = Path(self.tmp.name)
        (self.media / "postulaciones").mkdir()
        (self.media / "postulaciones" / "abc.jpg").write_bytes(u.imagen_bytes())
        (self.media / "secreto.txt").write_text("no")

    def tearDown(self):
        self.tmp.cleanup()

    def test_url_firmada_sirve_archivo(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.client.force_login(usuario())
            r = self.client.get(url_archivo("postulaciones/abc.jpg"))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r["Content-Type"], "image/jpeg")
            r.close()  # FileResponse mantiene abierto el archivo; cerrar también en Windows.

    def test_url_firmada_requiere_sesion(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.assertEqual(self.client.get(url_archivo("postulaciones/abc.jpg")).status_code, 302)

    def test_token_alterado_da_404(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.client.force_login(usuario())
            url = url_archivo("postulaciones/abc.jpg")
            alterada = url[:-3] + ("A" if url[-3] != "A" else "B") + url[-2:]
            self.assertEqual(self.client.get(alterada).status_code, 404)

    def test_token_caducado_da_404(self):
        with override_settings(MEDIA_ROOT=self.media, URL_FIRMADA_SEGUNDOS=-1):
            self.client.force_login(usuario())
            self.assertEqual(self.client.get(url_archivo("postulaciones/abc.jpg")).status_code, 404)

    def test_no_sale_de_media_aunque_este_firmado(self):
        with override_settings(MEDIA_ROOT=self.media / "postulaciones"):
            self.client.force_login(usuario())
            for ruta in ("../secreto.txt", "/etc/passwd"):
                r = self.client.get(reverse("nucleo:archivo", args=[firmar_ruta(ruta)]))
                self.assertEqual(r.status_code, 404, ruta)

    def test_solo_sirve_imagenes(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.client.force_login(usuario())
            self.assertEqual(self.client.get(url_archivo("secreto.txt")).status_code, 404)


class SitioPublico(TestCase):
    """Las pantallas del equipo (app web) siguen siendo públicas y protegidas por CSP."""

    def test_paginas_publicas_sin_sesion(self):
        for nombre in ("web:portafolio", "web:horarios", "web:cotizacion"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertIn("script-src 'self'", r["Content-Security-Policy"])

    def test_cotizacion_solo_acepta_jpg_png(self):
        r = self.client.get(reverse("web:cotizacion"))
        self.assertContains(r, 'accept="image/jpeg,image/png"')
        self.assertNotContains(r, "webp")
        self.assertNotContains(r, "WEBP")

    def test_scripts_del_sitio_existen(self):
        from django.contrib.staticfiles import finders
        for js in ("web/js/cotizacion.js", "web/js/horarios.js", "web/js/portafolio.js"):
            self.assertIsNotNone(finders.find(js), js)

    def test_enlace_al_acceso_del_equipo(self):
        r = self.client.get(reverse("web:portafolio"))
        self.assertContains(r, reverse("cuentas:login"))

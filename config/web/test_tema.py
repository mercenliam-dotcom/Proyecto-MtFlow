"""Tema oscuro: hojas, fuente e íconos locales (sin CDN por la CSP)."""
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class TemaOscuro(TestCase):
    def test_paginas_cargan_el_tema_y_los_iconos_locales(self):
        for url in (reverse("web:portafolio"), reverse("cuentas:login")):
            r = self.client.get(url)
            self.assertContains(r, "css/tema-oscuro.css")
            self.assertContains(r, "img/iconos.svg#")
            self.assertNotContains(r, "fonts.googleapis.com")

    def test_recursos_existen(self):
        base = Path(settings.BASE_DIR) / "static"
        for ruta in ("css/tema-oscuro.css", "css/tema-oscuro-colores.css", "img/iconos.svg", "fonts/inter-latin-wght-normal.woff2"):
            self.assertTrue((base / ruta).is_file(), ruta)
        sprite = (base / "img/iconos.svg").read_text()
        for icono in ("inicio", "agenda", "solicitudes", "portafolio", "analitica", "pluma"):
            self.assertIn(f'id="{icono}"', sprite)

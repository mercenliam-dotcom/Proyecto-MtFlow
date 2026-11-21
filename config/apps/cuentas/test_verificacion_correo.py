"""Revisión automática del correo: dominio por DNS y sugerencias de errores típicos."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import verificacion_correo as vc


class RevisarCorreo(TestCase):
    def setUp(self):
        cache.clear()

    def revisar(self, email):
        return self.client.get(reverse("cuentas:correo_revisar"), {"email": email}).json()

    def test_error_tipico_sugiere_la_correccion(self):
        r = self.revisar("ana@gmial.com")
        self.assertFalse(r["ok"])
        self.assertEqual(r["sugerencia"], "ana@gmail.com")

    def test_formato_invalido(self):
        self.assertIn("correo válido", self.revisar("ana@")["mensaje"])

    @override_settings(VERIFICACION_DNS_ACTIVA=True)
    def test_dominio_inexistente(self):
        import dns.resolver
        def resolver(dominio, *a, **k):
            if dominio == "gmail.com":
                return [object()]
            raise dns.resolver.NXDOMAIN
        with mock.patch("dns.resolver.resolve", side_effect=resolver):
            r = self.revisar("ana@noexiste-xyz.cl")
        self.assertFalse(r["ok"])
        self.assertIn("no existe", r["mensaje"])

    @override_settings(VERIFICACION_DNS_ACTIVA=True)
    def test_red_con_dns_que_niega_todo_no_bloquea(self):
        import dns.resolver
        with mock.patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
            self.assertTrue(self.revisar("ana@correo-raro.cl")["ok"])

    @override_settings(VERIFICACION_DNS_ACTIVA=True)
    def test_proveedores_conocidos_no_consultan(self):
        with mock.patch("dns.resolver.resolve", side_effect=AssertionError("no debía consultar")):
            self.assertTrue(self.revisar("ana@gmail.com")["ok"])

    @override_settings(VERIFICACION_DNS_ACTIVA=True)
    def test_dominio_valido(self):
        with mock.patch("dns.resolver.resolve", return_value=[object()]):
            self.assertTrue(self.revisar("ana@correo.cl")["ok"])

    @override_settings(VERIFICACION_DNS_ACTIVA=True)
    def test_sin_internet_no_bloquea(self):
        import dns.exception
        with mock.patch("dns.resolver.resolve", side_effect=dns.exception.Timeout):
            self.assertEqual(vc.revisar_dominio("a@correo.cl"), "")

    def test_registro_rechaza_dominio_mal_escrito(self):
        datos = {"nombre_usuario": "anacliente", "nombre": "Ana", "apellido": "Rojas", "email": "ana@gmial.com",
                 "password1": "Tinta2026segura!", "password2": "Tinta2026segura!"}
        r = self.client.post(reverse("clientes:registro"), datos)
        self.assertContains(r, "gmail.com", status_code=400)

    def test_paginas_con_correo_cargan_la_revision(self):
        r = self.client.get(reverse("web:cotizacion"))
        self.assertContains(r, "js/revisar-correo.js")
        self.assertContains(r, reverse("cuentas:correo_revisar"))

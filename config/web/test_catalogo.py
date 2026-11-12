"""Portafolio público agrupado por estilo y catálogo completo filtrable."""
import tempfile
import uuid

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Estilo, TrabajoPortafolio
from .test_recepcion import profesional


class CatalogoPublico(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ajuste = self.settings(MEDIA_ROOT=tmp.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.artista = profesional()
        self.anime, _ = Estilo.objects.get_or_create(codigo="E-02", defaults={"nombre": "Anime"})
        self.linea, _ = Estilo.objects.get_or_create(codigo="E-05", defaults={"nombre": "Línea fina"})

    def foto(self, titulo, estilo=None, visible=True, **extra):
        return TrabajoPortafolio.objects.create(
            tatuadora=self.artista, estilo=estilo, titulo=titulo, url=f"portafolio/{uuid.uuid4().hex}.jpg",
            visible=visible, autorizacion_publicacion=visible, tipo="TATUAJE" if estilo else "ESTUDIO",
            publicado_en=timezone.localdate(), **extra)

    def test_portafolio_muestra_una_tarjeta_por_estilo_no_una_por_foto(self):
        for n in range(30):
            self.foto(f"Anime {n}", self.anime)
        self.foto("Rama fina", self.linea)
        r = Client().get(reverse("web:portafolio"))
        grupos = {g["nombre"]: g for g in r.context["grupos"]}
        self.assertEqual(grupos["Anime"]["cantidad"], 30)
        self.assertEqual(grupos["Línea fina"]["cantidad"], 1)
        self.assertEqual(grupos["Lettering"]["cantidad"], 0)  # aparece como «Próximamente»
        self.assertNotIn("El estudio", grupos)  # sin fotos del estudio no hay tarjeta vacía
        self.assertEqual(r.content.decode().count('class="estilo-tarjeta"'), 2)
        self.assertContains(r, "30 trabajos")
        self.assertContains(r, reverse("web:catalogo") + "?estilo=anime")
        self.assertContains(r, "31 trabajos publicados")

    def test_catalogo_filtra_por_estilo_y_pagina(self):
        for n in range(30):
            self.foto(f"Anime {n}", self.anime)
        self.foto("Rama fina", self.linea)
        self.foto("Nuestro espacio")  # foto del estudio, sin estilo
        self.foto("Borrador", self.anime, visible=False)
        url = reverse("web:catalogo")
        r = Client().get(url)
        self.assertEqual(r.context["pagina"].paginator.count, 32)
        self.assertEqual(len(r.context["pagina"].object_list), 24)
        self.assertNotContains(r, "Borrador")
        r = Client().get(url, {"estilo": "linea-fina"})
        self.assertContains(r, "Rama fina")
        self.assertNotContains(r, "Anime 0<")
        r = Client().get(url, {"estilo": "el-estudio"})
        self.assertContains(r, "Nuestro espacio")
        self.assertEqual(r.context["pagina"].paginator.count, 1)
        r = Client().get(url, {"estilo": "anime", "pagina": 2})
        self.assertEqual(len(r.context["pagina"].object_list), 6)
        self.assertContains(r, "Página 2 de 2")
        # Un estilo desconocido muestra todo en vez de fallar.
        self.assertEqual(Client().get(url, {"estilo": "no-existe"}).context["pagina"].paginator.count, 32)

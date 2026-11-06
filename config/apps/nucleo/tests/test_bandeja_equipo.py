from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Usuario
from web.models import ContactoSolicitud, Cliente, Postulacion
from web.test_recepcion import profesional


class BandejaEquipo(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser("admin01", "admin@example.com", "Tinta2026segura", nombre="Admin", apellido="Local")
        self.ana = profesional("tatuadora1")
        self.bea = profesional("tatuadora2")
        self.bea.usuario.nombre = "Beatriz"
        self.bea.usuario.save(update_fields=["nombre"])
        self.p1 = self.crear(self.ana, "Cliente Ana", "RECIBIDA", datetime(2026, 11, 1, 9))
        self.p2 = self.crear(self.bea, "Cliente Beatriz", "EN_REVISION", datetime(2026, 11, 4, 9))
        self.url = reverse("nucleo:equipo_cotizaciones")
        self.detalle = reverse("nucleo:equipo_cotizacion_detalle", args=[self.p2.referencia])
        self.client.force_login(self.admin)

    def crear(self, tatuadora, nombre, estado="RECIBIDA", fecha=None):
        cliente = Cliente.objects.create(nombres=nombre, apellidos="", correo="cliente@example.com")
        p = Postulacion.objects.create(tatuadora=tatuadora, cliente=cliente, zona_cuerpo="brazo", alto_cm=5, ancho_cm=5, descripcion="Referencia del cliente", estado=estado)
        ContactoSolicitud.objects.create(postulacion=p, nombres=cliente.nombres, correo=cliente.correo)
        if fecha:
            Postulacion.objects.filter(pk=p.pk).update(creada_en=timezone.make_aware(fecha))
        return p

    def test_admin_ve_todas_y_detalle_de_cualquier_tatuadora(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Cliente Ana")
        self.assertContains(r, "Cliente Beatriz")
        self.assertEqual(r.context["total"], 2)
        self.assertContains(r, self.detalle)
        self.assertContains(r, "Beatriz Rojas")
        r = self.client.get(self.detalle)
        self.assertContains(r, "Cliente Beatriz")
        self.assertContains(r, "Referencia del cliente")
        self.assertContains(r, 'href="' + self.url + '"')

    def test_tatuadora_administradora_puede_consultar_equipo(self):
        self.client.force_login(self.ana.usuario)
        for url in (self.url, self.detalle):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Cliente Beatriz")

    def test_sin_sesion_redirige_a_login(self):
        self.client.logout()
        for url in (self.url, self.detalle):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_mis_cotizaciones_mantiene_aislamiento(self):
        r = self.client.get(reverse("nucleo:cotizaciones"))
        self.assertEqual(r.context["total"], 0)
        self.client.force_login(self.ana.usuario)
        r = self.client.get(reverse("nucleo:cotizaciones"))
        self.assertContains(r, "Cliente Ana")
        self.assertNotContains(r, "Cliente Beatriz")

    def test_filtra_tatuadora_y_estado(self):
        r = self.client.get(self.url, {"tatuadora": str(self.bea.usuario.uuid), "estado": "EN_REVISION"})
        self.assertEqual(r.context["pagina"].paginator.count, 1)
        self.assertContains(r, "Cliente Beatriz")
        self.assertNotContains(r, "Cliente Ana")

    def test_fechas_inclusivas_segun_zona_local(self):
        self.crear(self.ana, "Inicio del día", fecha=datetime(2026, 11, 4, 0, 0))
        self.crear(self.ana, "Fin del día", fecha=datetime(2026, 11, 4, 23, 59))
        r = self.client.get(self.url, {"desde": "2026-11-04", "hasta": "2026-11-04"})
        self.assertEqual(r.context["pagina"].paginator.count, 3)
        self.assertContains(r, "Inicio del día")
        self.assertContains(r, "Fin del día")
        self.assertNotContains(r, "Cliente Ana")

    def test_filtros_invalidos_muestran_error_y_no_todas_las_propuestas(self):
        for filtros in ({"desde": "2026-11-05", "hasta": "2026-11-01"}, {"desde": "no-es-fecha"}, {"tatuadora": "inventada"}, {"estado": "INVENTADO"}):
            with self.subTest(filtros=filtros):
                r = self.client.get(self.url, filtros)
                self.assertContains(r, "Revisa los filtros", status_code=400)
                self.assertEqual(r.context["pagina"].paginator.count, 0)

    def test_sin_resultados_muestra_estado_vacio(self):
        r = self.client.get(self.url, {"desde": "2027-01-01"})
        self.assertContains(r, "No hay cotizaciones para mostrar")
        self.assertEqual(r.context["total"], 2)

    def test_paginacion_conserva_filtros(self):
        for i in range(21):
            self.crear(self.ana, f"Cliente {i}")
        filtros = {"tatuadora": str(self.ana.usuario.uuid), "estado": "RECIBIDA"}
        r = self.client.get(self.url, filtros)
        self.assertEqual(r.context["pagina"].paginator.count, 22)
        self.assertEqual(len(r.context["pagina"]), 20)
        self.assertContains(r, "pagina=2&amp;tatuadora=" + str(self.ana.usuario.uuid) + "&amp;estado=RECIBIDA")

    def test_solo_consulta_y_no_cache(self):
        for url in (self.url, self.detalle):
            self.assertIn("no-store", self.client.get(url)["Cache-Control"])
            self.assertEqual(self.client.post(url, {"estado": "ACEPTADA"}).status_code, 405)
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.estado, "EN_REVISION")

    def test_enlace_de_equipo_solo_para_admin(self):
        self.assertContains(self.client.get(reverse("nucleo:inicio")), self.url)
        self.client.force_login(self.ana.usuario)
        self.assertContains(self.client.get(reverse("nucleo:inicio")), self.url)

    def test_se_puede_consultar_historial_de_profesional_desactivada(self):
        self.bea.activa = False
        self.bea.save()
        r = self.client.get(self.url, {"tatuadora": str(self.bea.usuario.uuid)})
        self.assertContains(r, "Cliente Beatriz")

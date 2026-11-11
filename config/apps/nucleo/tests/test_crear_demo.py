from io import StringIO
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import TestCase
from web.models import Postulacion
from web.test_recepcion import profesional


class ComandoDemo(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ctx = self.settings(MEDIA_ROOT=self.tmp.name)
        ctx.enable()
        self.addCleanup(ctx.disable)
        self.a, self.b = profesional("demouno"), profesional("demodos")

    def test_reparte_entre_tatuadoras_y_cliente_y_se_puede_borrar(self):
        call_command("crear_demo", "--cantidad", "20", "--sin-ml", "--tatuadoras", "demouno,demodos", stdout=StringIO(), stderr=StringIO())
        demo = Postulacion.objects.filter(contacto__correo__endswith="@demo.mtflow.cl")
        self.assertEqual(demo.count(), 20)
        self.assertEqual(demo.filter(tatuadora=self.a).count(), 10)
        self.assertTrue(demo.filter(cliente__usuario__nombre_usuario="clientedemo").exists())
        self.assertTrue(demo.filter(cliente__usuario__isnull=True).exists())
        self.assertGreater(len(set(demo.values_list("estado", flat=True))), 3)
        for p in demo.filter(abono_verificado_en__isnull=False):
            self.assertTrue(p.precio_final * 30 <= p.monto_abono * 100 <= p.precio_final * 40)
        call_command("crear_demo", "--solo-borrar", stdout=StringIO())
        self.assertFalse(Postulacion.objects.filter(contacto__correo__endswith="@demo.mtflow.cl").exists())

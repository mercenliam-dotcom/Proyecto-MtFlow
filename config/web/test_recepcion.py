from decimal import Decimal
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.cache import cache
from django.db import IntegrityError, OperationalError, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.clasificacion.cliente_ml import ResultadoClasificacion, ServicioMLNoDisponible
from apps.cuentas.models import Usuario
from apps.nucleo.firmas import url_archivo
from apps.nucleo.tests.utilidades import jpg_valido, png_valido
from .forms import token_envio
from .models import ContactoSolicitud, Cliente, ConfianzaEstilo, Imagen, Postulacion, Prediccion, Tatuadora


def profesional(nombre="artista1"):
    user = Usuario.objects.create_user(nombre, f"{nombre}@example.com", "Tinta2026segura", nombre="Ana", apellido="Rojas", debe_cambiar_contrasena=False, es_tatuadora=True, rol="ADMIN")
    return Tatuadora.objects.get(usuario=user)


def propuesta(profesional_elegida, **extra):
    datos = dict(envio=token_envio(), nombre="Cliente", email="cliente@example.com", telefono="",
                 tatuadora=str(profesional_elegida.pk), zona="antebrazo", alto_cm="5", ancho_cm="5",
                 color="negro", detalle="normal", idea="Una flor", imagen=jpg_valido())
    datos.update(extra)
    return datos


class RecepcionPersistente(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_context = self.settings(MEDIA_ROOT=self.tmp.name)
        self.settings_context.enable()
        self.addCleanup(self.settings_context.disable)
        self.artista = profesional()
        self.url = reverse("web:cotizacion")

    def archivos(self):
        return [p for p in Path(self.tmp.name).rglob("*") if p.is_file()]

    def test_json_bajo_60_guarda_e99_y_siete_confianzas_originales(self):
        from unittest.mock import Mock
        vector = {"E-01": .59999998, **{f"E-{i:02}": .40000002 / 6 for i in range(2, 8)}}
        respuesta = Mock(status_code=200, json=lambda: {
            "version_modelo": "efficientnet_b0:v1:test", "confianzas": vector,
            "estilo_sugerido": "E-99", "confianza_maxima": .59999998, "umbral_confianza": .60,
        })
        with patch("requests.post", return_value=respuesta):
            r = self.client.post(self.url, propuesta(self.artista, analizar="on"))
        self.assertEqual(r.status_code, 200)
        p = Prediccion.objects.get()
        self.assertEqual(p.estilo_sugerido.codigo, "E-99")
        self.assertLess(p.confianza_maxima, Decimal(".60"))
        self.assertEqual(p.umbral_confianza, Decimal(".60"))
        self.assertEqual(ConfianzaEstilo.objects.count(), 7)
        self.assertFalse(ConfianzaEstilo.objects.filter(estilo__codigo="E-99").exists())
        self.assertEqual(Postulacion.objects.get().estado_ml, "COMPLETADO")
        self.assertEqual(Postulacion.objects.get().estado, "RECIBIDA")

    def test_json_con_60_guarda_categoria_sin_rechazar_la_propuesta(self):
        from unittest.mock import Mock
        vector = {"E-01": .60, **{f"E-{i:02}": .4 / 6 for i in range(2, 8)}}
        respuesta = Mock(status_code=200, json=lambda: {
            "version_modelo": "efficientnet_b0:v1:test", "confianzas": vector,
            "estilo_sugerido": "E-01", "confianza_maxima": .60, "umbral_confianza": .60,
        })
        with patch("requests.post", return_value=respuesta):
            r = self.client.post(self.url, propuesta(self.artista, analizar="on"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Prediccion.objects.get().estilo_sugerido.codigo, "E-01")
        self.assertEqual(Postulacion.objects.get().estado, "RECIBIDA")

    def test_guarda_propuesta_y_archivo_recodificado_con_medidas_reales(self):
        original = jpg_valido(tamano=(500, 350))
        contenido_original = original.read()
        original.seek(0)
        with patch("web.views.clasificar", side_effect=ServicioMLNoDisponible) as ml:
            r = self.client.post(self.url, propuesta(self.artista, imagen=original, alto_cm="5.25", ancho_cm="3.10", analizar=""))
        ml.assert_called_once()
        self.assertContains(r, "Propuesta recibida")
        p = Postulacion.objects.get()
        imagen = Imagen.objects.get(postulacion=p)
        archivo = Path(self.tmp.name) / imagen.url
        self.assertEqual(p.tatuadora, self.artista)
        self.assertEqual(p.area_cm2, Decimal("16.2750"))
        self.assertEqual(p.estado, "RECIBIDA")
        self.assertEqual(p.estado_ml, "NO_DISPONIBLE")
        self.assertFalse(p.sesiones.exists())
        self.assertEqual((imagen.ancho_px, imagen.alto_px), (500, 350))
        self.assertGreater(imagen.nitidez, 0)
        self.assertTrue(archivo.is_file())
        self.assertNotEqual(archivo.read_bytes(), contenido_original)
        self.assertEqual(imagen.tamano_bytes, archivo.stat().st_size)
        self.assertNotIn("referencia.jpg", imagen.url)
        self.assertFalse(Prediccion.objects.exists())

    def test_png_se_guarda_como_png(self):
        self.assertEqual(self.client.post(self.url, propuesta(self.artista, imagen=png_valido())).status_code, 200)
        imagen = Imagen.objects.get()
        self.assertEqual(imagen.formato, "PNG")
        self.assertTrue((Path(self.tmp.name) / imagen.url).read_bytes().startswith(b"\x89PNG"))

    def test_sin_eleccion_no_asigna_automaticamente(self):
        with patch("web.views.clasificar") as ml:
            r = self.client.post(self.url, propuesta(self.artista, tatuadora="", analizar="on"))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Postulacion.objects.exists())
        self.assertEqual(self.archivos(), [])
        ml.assert_not_called()

    def test_sin_tatuadoras_no_guarda_contacto_ni_archivo(self):
        Tatuadora.objects.update(activa=False)
        r = self.client.post(self.url, propuesta(self.artista))
        self.assertContains(r, "No hay tatuadoras habilitadas", status_code=400)
        self.assertFalse(ContactoSolicitud.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_tatuadora_con_cuenta_desactivada_no_se_puede_elegir(self):
        Usuario.objects.filter(pk=self.artista.usuario_id).update(is_active=False)
        self.assertEqual(self.client.post(self.url, propuesta(self.artista)).status_code, 400)
        self.assertFalse(Postulacion.objects.exists())

    def test_tatuadora_desactivada_durante_envio_no_se_reemplaza(self):
        with patch("web.recepcion.Tatuadora.objects.select_for_update") as consulta:
            consulta.return_value.filter.return_value.first.return_value = None
            r = self.client.post(self.url, propuesta(self.artista))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ContactoSolicitud.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_reenvio_mismo_token_no_duplica_ni_repite_ml(self):
        token = token_envio()
        resultado = ResultadoClasificacion({"E-05": .92}, "E-05", .92, "simulado-0.2")
        with patch("web.views.clasificar", return_value=resultado) as ml:
            self.client.post(self.url, propuesta(self.artista, envio=token, analizar="on"))
            r = self.client.post(self.url, propuesta(self.artista, envio=token, analizar="on"))
        self.assertContains(r, "Esta propuesta ya fue recibida")
        self.assertEqual(Postulacion.objects.count(), 1)
        self.assertEqual(ContactoSolicitud.objects.count(), 1)
        self.assertEqual(len(self.archivos()), 1)
        ml.assert_called_once()

    def test_token_manipulado_no_guarda(self):
        r = self.client.post(self.url, propuesta(self.artista, envio="inventado"))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Postulacion.objects.exists())

    def test_ml_caido_conserva_solicitud_y_marca_pendiente(self):
        with patch("web.views.clasificar", side_effect=ServicioMLNoDisponible):
            r = self.client.post(self.url, propuesta(self.artista, analizar="on"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Postulacion.objects.get().estado_ml, "NO_DISPONIBLE")
        self.assertEqual(len(self.archivos()), 1)
        self.assertFalse(Prediccion.objects.exists())

    def test_confianzas_version_larga_y_tiempo_real(self):
        version = "roboflow-workflow:" + "v" * 100
        resultado = ResultadoClasificacion({"E-05": .4182, "E-02": .12}, "E-05", .4182, version)
        with patch("web.views.clasificar", return_value=resultado), patch("web.recepcion.perf_counter", side_effect=[10, 10.321]):
            r = self.client.post(self.url, propuesta(self.artista, analizar="on"))
        self.assertEqual(r.status_code, 200)
        prediccion = Prediccion.objects.get()
        self.assertEqual(prediccion.version_modelo, version)
        self.assertEqual(prediccion.tiempo_inferencia_ms, 321)
        self.assertEqual(ConfianzaEstilo.objects.count(), 2)
        self.assertEqual(ConfianzaEstilo.objects.get(estilo__codigo="E-05").confianza, Decimal(".4182"))
        self.assertEqual(Postulacion.objects.get().alerta_ml, "REVISION_ESPECIAL")

    def test_fallo_bd_revierte_registros_y_borra_archivo(self):
        with patch("web.recepcion.Imagen.objects.create", side_effect=IntegrityError("prueba")):
            r = self.client.post(self.url, propuesta(self.artista))
        self.assertEqual(r.status_code, 503)
        self.assertFalse(ContactoSolicitud.objects.exists())
        self.assertFalse(Postulacion.objects.exists())
        self.assertEqual(self.archivos(), [])
        self.assertNotContains(r, "Propuesta recibida", status_code=503)

    def test_fallo_disco_no_crea_registros(self):
        with patch("web.recepcion.FileSystemStorage.save", side_effect=OSError("disco lleno")):
            r = self.client.post(self.url, propuesta(self.artista))
        self.assertEqual(r.status_code, 503)
        self.assertFalse(ContactoSolicitud.objects.exists())
        self.assertFalse(Postulacion.objects.exists())

    def test_fallo_durante_escritura_limpia_archivo_parcial(self):
        def escritura_interrumpida(storage, nombre, archivo):
            destino = Path(storage.path(nombre))
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(b"parcial")
            raise OSError("disco lleno durante escritura")

        with patch("web.recepcion.FileSystemStorage.save", autospec=True, side_effect=escritura_interrumpida):
            r = self.client.post(self.url, propuesta(self.artista))
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.archivos(), [])
        self.assertFalse(Postulacion.objects.exists())

    def test_solicitud_manual_no_guarda_precio_cero(self):
        self.client.post(self.url, propuesta(self.artista, cobertura="on"))
        self.assertIsNone(Postulacion.objects.get().precio_sugerido)

    def test_contacto_nuevo_no_sobrescribe_solicitudes_anteriores(self):
        self.client.post(self.url, propuesta(self.artista, nombre="Primero"))
        self.client.post(self.url, propuesta(self.artista, nombre="Segundo"))
        self.assertEqual(list(Postulacion.objects.order_by("pk").values_list("contacto__nombres", flat=True)), ["Primero", "Segundo"])

    def test_imagen_privada_solo_para_tatuadora_elegida_o_admin(self):
        self.client.post(self.url, propuesta(self.artista))
        imagen = Imagen.objects.get()
        url = url_archivo(imagen.url)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.artista.usuario)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r.close()
        otra = profesional("artista2")
        self.client.force_login(otra.usuario)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)  # La tatuadora también es administradora.
        r.close()
        admin = Usuario.objects.create_superuser("admin01", "admin@example.com", "Tinta2026segura", nombre="Admin", apellido="Local")
        self.client.force_login(admin)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r.close()


class CommitDeRecepcion(TransactionTestCase):
    def test_fallo_commit_no_deja_archivo_ni_contacto(self):
        cache.clear()
        artista = profesional()
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            with patch.object(connection, "commit", side_effect=OperationalError("commit fallido")):
                r = self.client.post(reverse("web:cotizacion"), propuesta(artista))
            self.assertEqual(r.status_code, 503)
            self.assertFalse(Postulacion.objects.exists())
            self.assertFalse(ContactoSolicitud.objects.exists())
            self.assertEqual([p for p in Path(media).rglob("*") if p.is_file()], [])

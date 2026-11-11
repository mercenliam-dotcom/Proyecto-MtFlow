import tempfile
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.clasificacion.cliente_ml import _validar_respuesta, ServicioMLNoDisponible
from apps.clasificacion.catalogo import recomendar
from apps.nucleo.tests.utilidades import jpg_valido
from .models import Prediccion, Postulacion, ConfianzaEstilo
from .test_recepcion import profesional, propuesta


def respuesta_ood(distancia=.8, confianza=.94):
    fuera = distancia > .5
    motivo = 'fuera_distribucion' if fuera else 'confianza_insuficiente' if confianza < .6 else None
    return dict(version_modelo='efficientnet_b0:v2:test:ood:' + 'a' * 16,
        confianzas={'E-01': confianza, **{f'E-{i:02}': (1 - confianza) / 6 for i in range(2, 8)}},
        estilo_sugerido='E-99' if motivo else 'E-01', confianza_maxima=confianza,
        umbral_confianza=.6, motivo_abstencion=motivo,
        ood=dict(version='a' * 64, distancia=distancia, umbral=.5, fuera_distribucion=fuera))


class ContratoOOD(SimpleTestCase):
    def test_ood_alta_confianza_tambien_se_abstiene(self):
        r = _validar_respuesta(respuesta_ood())
        self.assertEqual(r.estilo_sugerido, 'E-99')
        self.assertEqual(r.confianza_maxima, .94)
        self.assertEqual(recomendar(r.estilo_sugerido, r.confianza_maxima, r.motivo_abstencion).titulo, 'Revisión manual')

    def test_igualdad_pasa_ood_pero_no_rebaja_el_60(self):
        self.assertEqual(_validar_respuesta(respuesta_ood(.5, .6)).estilo_sugerido, 'E-01')
        r = _validar_respuesta(respuesta_ood(.5, .59999998))
        self.assertEqual(r.motivo_abstencion, 'confianza_insuficiente')

    def test_respuestas_manipuladas_se_rechazan(self):
        for cambio in ({'ood': None}, {'motivo_abstencion': None}, {'estilo_sugerido': 'E-01'},
                       {'ood': {**respuesta_ood()['ood'], 'fuera_distribucion': False}},
                       {'ood': {**respuesta_ood()['ood'], 'distancia': float('inf')}},
                       {'ood': {**respuesta_ood()['ood'], 'umbral': True}},
                       {'ood': {**respuesta_ood()['ood'], 'version': 'b' * 64}}):
            with self.subTest(cambio=cambio), self.assertRaises(ServicioMLNoDisponible):
                _validar_respuesta({**respuesta_ood(), **cambio})


class FlujoOOD(TestCase):
    def setUp(self):
        cache.clear()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        contexto = self.settings(MEDIA_ROOT=temporal.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.artista = profesional()
        self.respuesta = Mock(status_code=200, json=respuesta_ood)

    def test_analisis_previo_sin_guardado(self):
        with patch('requests.post', return_value=self.respuesta):
            r = self.client.post(reverse('web:analizar_referencia'), {'analizar': 'on', 'imagen': jpg_valido()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['motivo_abstencion'], 'fuera_distribucion')
        self.assertFalse(Postulacion.objects.exists())

    def test_recepcion_guarda_ood_sin_rechazar_ni_asignar_otra_profesional(self):
        with patch('requests.post', return_value=self.respuesta):
            r = self.client.post(reverse('web:cotizacion'), propuesta(self.artista, analizar='on'))
        self.assertContains(r, 'La referencia se aleja')
        p = Prediccion.objects.get()
        self.assertEqual(p.ood, respuesta_ood()['ood'])
        self.assertEqual(p.motivo_abstencion, 'fuera_distribucion')
        self.assertEqual(p.estilo_sugerido.codigo, 'E-99')
        self.assertEqual(ConfianzaEstilo.objects.count(), 7)
        solicitud = Postulacion.objects.get()
        self.assertEqual(solicitud.estado, 'RECIBIDA')
        self.assertEqual(solicitud.estado_ml, 'COMPLETADO')
        self.assertEqual(solicitud.alerta_ml, 'REVISION_ESPECIAL')
        self.assertEqual(solicitud.tatuadora_id, self.artista.pk)
        self.client.force_login(self.artista.usuario)
        detalle = self.client.get(reverse('nucleo:cotizacion_detalle', args=[solicitud.referencia]))
        self.assertContains(detalle, 'La referencia se aleja')
        self.assertNotContains(detalle, 'Ningún estilo alcanzó el umbral')
        self.assertContains(detalle, 'Detalle del detector')

    def test_pantalla_de_prueba_muestra_motivo_y_distancia(self):
        self.client.force_login(self.artista.usuario)
        with patch('requests.post', return_value=self.respuesta):
            r = self.client.post(reverse('clasificacion:probar'), {'imagen': jpg_valido()})
        self.assertContains(r, 'Revisión manual')
        self.assertContains(r, 'La referencia se aleja')
        self.assertContains(r, 'Detalle del detector')

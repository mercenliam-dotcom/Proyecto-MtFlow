import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app import config, main
from app.decision import CODIGOS, construir_respuesta
from app.ood import DetectorOOD
from app.predictor import PredictorNoDisponible

CALIBRACION = Path(__file__).resolve().parents[1] / "calibracion_ood_v2.json"
VERSION = "efficientnet_b0:v2:test:ood:" + "a" * 16


def metadatos(distancia=.8, umbral=.5):
    return dict(version="a" * 64, distancia=distancia, umbral=umbral, fuera_distribucion=distancia > umbral)


@pytest.mark.parametrize("distancia,maxima,estilo,motivo", [
    (.8, .99, "E-99", "fuera_distribucion"),
    (.5, .60, "E-01", None),
    (.4, .59999998, "E-99", "confianza_insuficiente"),
])
def test_ood_y_confianza_se_aplican_por_separado(distancia, maxima, estilo, motivo):
    vector = dict(zip(CODIGOS, [maxima] + [(1 - maxima) / 6] * 6))
    r = construir_respuesta(VERSION, vector, metadatos(distancia))
    assert r['estilo_sugerido'] == estilo
    assert r['motivo_abstencion'] == motivo
    assert r['confianzas'] == vector


def test_metadatos_ausentes_o_manipulados_no_se_aceptan():
    vector = dict(zip(CODIGOS, [.7] + [.05] * 6))
    for ood in (None, {}, {**metadatos(), 'distancia': float('nan')},
                {**metadatos(), 'fuera_distribucion': False}, {**metadatos(), 'umbral': True},
                {**metadatos(), 'version': 'b' * 64}):
        with pytest.raises(PredictorNoDisponible):
            construir_respuesta(VERSION, vector, ood)


def test_calibracion_real_y_formula_colab():
    cfg = json.loads(CALIBRACION.read_text())
    detector = DetectorOOD(CALIBRACION, cfg['modelo_sha256'], cfg['clases'])
    e = np.random.default_rng(42).normal(size=1280).astype('float32')
    esperado = float(np.clip(1 - np.max((e / np.linalg.norm(e)) @ detector.centroides.T), 0, 2))
    assert detector.evaluar(e)['distancia'] == esperado
    assert detector.umbral == .5373511910438538
    with pytest.raises(ValueError, match='Embedding'):
        detector.evaluar(np.zeros(1280))


@pytest.mark.parametrize("campo,valor", [
    ('modelo_sha256', 'modelo distinto'), ('clases', ['otra']), ('capa', 'styles'),
    ('metodo', 'otro'), ('umbral_distancia', float('nan')), ('centroides', [[0] * 1280] * 7),
])
def test_artefacto_incompatible_no_arranca(tmp_path, campo, valor):
    original = json.loads(CALIBRACION.read_text())
    cfg = copy.deepcopy(original)
    cfg[campo] = valor
    ruta = tmp_path / 'ood.json'
    ruta.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        DetectorOOD(ruta, original['modelo_sha256'], original['clases'])


def test_http_confianza_alta_ood_devuelve_revision_no_error(monkeypatch):
    vector = dict(zip(CODIGOS, [.94] + [.01] * 6))
    monkeypatch.setattr(main, 'predictor', SimpleNamespace(version=VERSION,
        analizar_bytes=lambda datos: (vector, metadatos())))
    contenido = io.BytesIO()
    Image.new('RGB', (224, 224)).save(contenido, 'PNG')
    respuesta = TestClient(main.app).post('/clasificar', headers={'X-API-Key': config.API_KEY},
        files={'imagen': ('prueba.png', contenido.getvalue(), 'image/png')})
    assert respuesta.status_code == 200
    assert respuesta.json()['estilo_sugerido'] == 'E-99'
    assert respuesta.json()['motivo_abstencion'] == 'fuera_distribucion'
    assert len(respuesta.json()['confianzas']) == 7

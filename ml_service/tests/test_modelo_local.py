import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import config
from app.decision import CODIGOS, construir_respuesta
from app.modelo_local import CLASES_LOCALES, leer_bundle, validar_puntuaciones
from app.predictor import PredictorNoDisponible


@pytest.mark.parametrize("maxima,esperado", [
    (0.60, "E-01"), (0.6000001, "E-01"), (0.59999998, "E-99"), (0.50, "E-99"),
])
def test_umbral_exacto_sin_redondeo(maxima, esperado):
    confianzas = dict(zip(CODIGOS, [maxima] + [(1 - maxima) / 6] * 6))
    resultado = construir_respuesta("efficientnet_b0:v1:prueba", confianzas)
    assert resultado["estilo_sugerido"] == esperado
    assert resultado["confianza_maxima"] == maxima
    assert resultado["umbral_confianza"] == .60
    assert resultado["confianzas"] == confianzas
    assert "E-99" not in resultado["confianzas"]


@pytest.mark.parametrize("malo", [None, {}, {"E-01": .99},
    dict(zip(CODIGOS, [float("nan")] + [0.] * 6)),
    dict(zip(CODIGOS, [float("inf")] + [0.] * 6)),
    dict(zip(CODIGOS, [True] + [0.] * 6)),
    dict(zip(CODIGOS, [0.] * 7)), dict(zip(CODIGOS, [.5] * 7))])
def test_respuestas_invalidas_no_se_disfrazan_de_fuera_catalogo(malo):
    with pytest.raises(PredictorNoDisponible):
        construir_respuesta("x", malo)


def bundle(tmp_path):
    clases = list(CLASES_LOCALES)
    cfg = dict(architecture="EfficientNetB0", class_ids=clases,
               image_size=[224, 224], input_range=[0, 255], resize="bilinear")
    (tmp_path / "class_names.json").write_text(json.dumps(clases))
    (tmp_path / "training_config.json").write_text(json.dumps(cfg))
    datos = b"pesos ficticios: las pruebas de contrato no ejecutan Keras"
    (tmp_path / "MTFlow_EfficientNetB0_v1.keras").write_bytes(datos)
    (tmp_path / "model_sha256.txt").write_text(hashlib.sha256(datos).hexdigest())
    return cfg


def test_bundle_corrupto_se_rechaza_antes_de_cargar_tensorflow(tmp_path):
    bundle(tmp_path)
    (tmp_path / "MTFlow_EfficientNetB0_v1.keras").write_bytes(b"archivo cambiado")
    with pytest.raises(ValueError, match="SHA-256"):
        leer_bundle(tmp_path)


def test_clase_extra_y_orden_inconsistente_se_rechazan(tmp_path):
    cfg = bundle(tmp_path)
    (tmp_path / "class_names.json").write_text(json.dumps(cfg["class_ids"][::-1]))
    with pytest.raises(ValueError, match="siete estilos"):
        leer_bundle(tmp_path)
    cfg["class_ids"][-1] = "Fuera de catalogo"
    (tmp_path / "class_names.json").write_text(json.dumps(cfg["class_ids"]))
    (tmp_path / "training_config.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="siete estilos"):
        leer_bundle(tmp_path)


def test_orden_exportado_se_traduce_por_nombre_no_por_posicion(tmp_path):
    cfg = bundle(tmp_path)
    cfg["class_ids"] = cfg["class_ids"][::-1]
    (tmp_path / "class_names.json").write_text(json.dumps(cfg["class_ids"]))
    (tmp_path / "training_config.json").write_text(json.dumps(cfg))
    _, codigos, _ = leer_bundle(tmp_path)
    assert codigos == list(CODIGOS)[::-1]


@pytest.mark.parametrize("valores", [[.9] * 7, [float("nan")] * 7, [-.1] + [.2] * 6, [1.]])
def test_vector_local_invalido(valores):
    with pytest.raises(PredictorNoDisponible):
        validar_puntuaciones(valores, CODIGOS)


def test_local_no_falla_silenciosamente_a_simulacion(monkeypatch, tmp_path):
    from app.predictor import cargar_predictor
    monkeypatch.setattr(config, "FORZAR_STUB", False)
    monkeypatch.setattr(config, "MODO_PREDICTOR", "local")
    monkeypatch.setattr(config, "MTFLOW_MODEL_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        cargar_predictor()


def test_fastapi_usa_bytes_validados_y_declara_abstencion(monkeypatch):
    import io
    from PIL import Image
    from fastapi.testclient import TestClient
    from app import main
    contenido = io.BytesIO()
    Image.new("RGB", (300, 300)).save(contenido, "PNG")
    originales = contenido.getvalue()

    def predecir_bytes(datos):
        assert datos == originales
        return dict(zip(CODIGOS, [.4, .1, .1, .1, .1, .1, .1]))

    monkeypatch.setattr(main, "predictor", SimpleNamespace(version="efficientnet_b0:v1:test", predecir_bytes=predecir_bytes))
    r = TestClient(main.app).post("/clasificar", headers={"X-API-Key": config.API_KEY},
                                  files={"imagen": ("a.png", originales, "image/png")})
    assert r.status_code == 200
    assert r.json()["estilo_sugerido"] == "E-99"
    assert r.json()["confianza_maxima"] == .4
    assert len(r.json()["confianzas"]) == 7

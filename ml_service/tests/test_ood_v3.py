import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.ood import DetectorOOD

ROOT = Path(__file__).resolve().parents[1] / "modelos/efficientnet_b0_v3"


def fixture_knn(tmp_path, **changes):
    cfg = json.loads((ROOT / "ood/calibracion_ood_v3.json").read_text(encoding="utf-8"))
    references = np.random.default_rng(42).normal(size=(14, 1280)).astype("float32")
    references /= np.linalg.norm(references, axis=1, keepdims=True)
    file = tmp_path / "referencias_knn_v3.npz"
    np.savez_compressed(file, embeddings=references, labels=np.tile(np.arange(7), 2),
                        paths=np.array([f"train/{i}.jpg" for i in range(14)]))
    cfg.update(n_train=14, referencias_sha256=hashlib.sha256(file.read_bytes()).hexdigest(), **changes)
    path = tmp_path / "calibracion_ood_v3.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path, cfg


def test_knn_real_reproduce_la_distancia_al_quinto_vecino():
    path = ROOT / "ood/calibracion_ood_v3.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    detector = DetectorOOD(path, cfg["modelo_sha256"], cfg["clases"])
    embedding = np.random.default_rng(27).normal(size=1280)
    expected = np.sort(np.clip(1 - (embedding / np.linalg.norm(embedding)) @ detector.referencias.T, 0, 2))[4]
    result = detector.evaluar(embedding)
    assert result["distancia"] == pytest.approx(expected, abs=1e-12)
    assert result["umbral"] == 0.4379139110950403
    assert result["version"] == "7e69048d17c680d16c0228e0c7e368911fdfc855713884c8a65bfbad5efe162f"


def test_igualdad_en_umbral_knn_se_acepta(tmp_path):
    path, cfg = fixture_knn(tmp_path)
    embedding = np.random.default_rng(15).normal(size=1280)
    detector = DetectorOOD(path, cfg["modelo_sha256"], cfg["clases"])
    cfg["umbral_distancia"] = detector.evaluar(embedding)["distancia"]
    path.write_text(json.dumps(cfg), encoding="utf-8")
    detector = DetectorOOD(path, cfg["modelo_sha256"], cfg["clases"])
    assert detector.evaluar(embedding)["fuera_distribucion"] is False


@pytest.mark.parametrize("changes", [{"k": True}, {"k": 0}, {"k": 100},
    {"model_version": "v2"}, {"embedding_dimension": 7}, {"preprocessing": {}}])
def test_calibracion_knn_incompatible_no_arranca(tmp_path, changes):
    path, cfg = fixture_knn(tmp_path, **changes)
    with pytest.raises(ValueError):
        DetectorOOD(path, cfg["modelo_sha256"], cfg["clases"])


def test_referencias_modificadas_no_arrancan(tmp_path):
    path, cfg = fixture_knn(tmp_path)
    with (tmp_path / "referencias_knn_v3.npz").open("ab") as file:
        file.write(b"alterado")
    with pytest.raises(ValueError, match="SHA-256"):
        DetectorOOD(path, cfg["modelo_sha256"], cfg["clases"])


@pytest.mark.parametrize("embedding", [np.zeros(1280), np.full(1280, np.nan), np.ones(7)])
def test_embedding_knn_invalido_se_rechaza(tmp_path, embedding):
    path, cfg = fixture_knn(tmp_path)
    detector = DetectorOOD(path, cfg["modelo_sha256"], cfg["clases"])
    with pytest.raises(ValueError, match="Embedding"):
        detector.evaluar(embedding)

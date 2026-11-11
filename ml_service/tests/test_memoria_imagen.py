import io
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageOps

from app import main, config
from app.modelo_local import PredictorEfficientNetKeras

VECTOR = {f"E-{i:02}": (.7 if i == 1 else .05) for i in range(1, 8)}
HEADERS = {"X-API-Key": config.API_KEY}


def foto(size=(300, 300)):
    with Image.new("RGB", size, (90, 110, 150)) as img, io.BytesIO() as out:
        img.save(out, format="JPEG")
        return out.getvalue()


def enviar(cliente, datos):
    return cliente.post("/clasificar", headers=HEADERS,
                        files={"imagen": ("foto.jpg", datos, "image/jpeg")})


def test_foto_3024_4032_se_abre_una_vez_y_libera_sus_pixeles(monkeypatch):
    datos = foto((3024, 4032))
    capturada = []

    def analizar_imagen(img, originales):
        assert img.size == (3024, 4032)
        assert originales == datos
        assert img.getpixel((0, 0))
        capturada.append(img)
        return VECTOR, None

    monkeypatch.setattr(main, "predictor", SimpleNamespace(version="prueba", analizar_imagen=analizar_imagen))
    with patch("app.main.Image.open", wraps=Image.open) as abrir:
        assert enviar(TestClient(main.app), datos).status_code == 200
        assert abrir.call_count == 1
    with pytest.raises(ValueError, match="closed"):
        capturada[0].getpixel((0, 0))


def test_solicitud_simultanea_no_decodifica_ni_espera_y_salud_responde(monkeypatch):
    entro, continuar = threading.Event(), threading.Event()

    def analizar_imagen(img, datos):
        entro.set()
        assert continuar.wait(10)
        return VECTOR, None

    monkeypatch.setattr(main, "predictor", SimpleNamespace(version="prueba", analizar_imagen=analizar_imagen))
    cliente = TestClient(main.app)
    datos = foto()
    with ThreadPoolExecutor(max_workers=1) as executor:
        primera = executor.submit(enviar, cliente, datos)
        try:
            assert entro.wait(5)
            with patch("app.main.Image.open", side_effect=AssertionError("No debe decodificar otra foto")):
                segunda = enviar(cliente, datos)
            assert segunda.status_code == 503
            assert segunda.headers["Retry-After"] == "3"
            assert cliente.get("/salud").status_code == 200
        finally:
            continuar.set()
        assert primera.result(timeout=5).status_code == 200
    assert enviar(cliente, datos).status_code == 200


def test_limite_pixeles_se_rechaza_antes_de_decodificar_y_libera_cupo(monkeypatch):
    datos = foto()
    with monkeypatch.context() as cambio:
        cambio.setattr(config, "MAX_PIXELES", 80_000)
        with patch.object(Image.Image, "load", side_effect=AssertionError("No debe decodificar")):
            assert enviar(TestClient(main.app), datos).status_code == 413
    assert enviar(TestClient(main.app), datos).status_code == 200


def test_archivo_truncado_no_retiene_cupo():
    cliente = TestClient(main.app)
    assert enviar(cliente, foto()[:300]).status_code == 422
    assert enviar(cliente, foto()).status_code == 200


@pytest.mark.parametrize("modo", ["RGB", "RGBA", "L", "CMYK", "P"])
@pytest.mark.parametrize("orientacion", range(1, 9))
def test_entrada_v3_es_identica_al_preprocesamiento_original(modo, orientacion):
    rng = np.random.default_rng(123)
    with Image.fromarray(rng.integers(0, 256, (307, 401, 3), dtype=np.uint8)) as base:
        imagen = base.convert(modo)
    try:
        imagen.getexif()[274] = orientacion
        esperado = np.asarray(ImageOps.exif_transpose(imagen).convert("RGB").resize(
            (224, 224), Image.Resampling.BILINEAR))[None, ...]
        predictor = object.__new__(PredictorEfficientNetKeras)
        predictor.tf = SimpleNamespace(convert_to_tensor=lambda valor: valor)
        np.testing.assert_array_equal(predictor.preparar_imagen(imagen), esperado)
    finally:
        imagen.close()

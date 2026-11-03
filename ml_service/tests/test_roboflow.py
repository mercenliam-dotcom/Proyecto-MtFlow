"""
Pruebas del conector con Roboflow. No llaman a Internet: se simula la
respuesta HTTP con el formato documentado por Roboflow para clasificación.
"""
import base64
import io
from unittest import mock

import pytest
import requests
from PIL import Image

from app import config
from app.predictor import PredictorNoDisponible, PredictorRoboflow, _clave_nombre

RESPUESTA_UNA_ETIQUETA = {
    "time": 0.19,
    "image": {"width": 224, "height": 224},
    "predictions": [
        {"class": "Linea Fina", "class_id": 4, "confidence": 0.9132},
        {"class": "Ornamentos", "class_id": 5, "confidence": 0.0411},
        {"class": "Alto contraste", "class_id": 0, "confidence": 0.0203},
        {"class": "Lettering", "class_id": 3, "confidence": 0.0119},
        {"class": "Anime", "class_id": 1, "confidence": 0.0071},
        {"class": "Tribal-Neotribal", "class_id": 6, "confidence": 0.0042},
        {"class": "Cibersigilismo", "class_id": 2, "confidence": 0.0022},
    ],
    "top": "Linea Fina",
    "confidence": 0.9132,
    "prediction_type": "ClassificationModel",
}


def _pred():
    return PredictorRoboflow("clave-secreta", "https://serverless.roboflow.com",
                             "martin-stgmar-gmail-com/tattoo-styles-2-resnet18-t1",
                             5, 640, config.CLASES_ROBOFLOW)


def _img(lado=1200):
    return Image.new("RGB", (lado, lado), (120, 40, 40))


def _respuesta(json_data, status=200):
    r = mock.Mock(status_code=status)
    r.json = lambda: json_data
    return r


def test_mapea_las_siete_clases_a_codigos():
    with mock.patch("requests.post", return_value=_respuesta(RESPUESTA_UNA_ETIQUETA)):
        conf = _pred().predecir(_img())
    assert set(conf) == {"E-01", "E-02", "E-03", "E-04", "E-05", "E-06", "E-07"}
    assert max(conf, key=conf.get) == "E-05"          # Linea Fina
    assert abs(sum(conf.values()) - 1) < 1e-6


def test_formato_multietiqueta():
    datos = {"predictions": {"Anime": {"confidence": 0.8}, "Lettering": {"confidence": 0.2}}}
    with mock.patch("requests.post", return_value=_respuesta(datos)):
        conf = _pred().predecir(_img())
    assert conf["E-02"] == pytest.approx(0.8)
    assert conf["E-01"] == 0.0


def test_tolera_tildes_y_mayusculas_en_nombres():
    assert _clave_nombre("Línea  Fina") == _clave_nombre("Linea Fina")
    assert _clave_nombre("TRIBAL - neotribal") == _clave_nombre("Tribal-Neotribal")


def test_clase_desconocida_se_rechaza():
    datos = {"predictions": [{"class": "Realismo", "confidence": 0.99}]}
    with mock.patch("requests.post", return_value=_respuesta(datos)):
        with pytest.raises(PredictorNoDisponible, match="desconocida"):
            _pred().predecir(_img())


@pytest.mark.parametrize("datos", [
    None, [], {}, {"predictions": []},
    {"predictions": [{"class": "Anime", "confidence": "0.9"}]},
    {"predictions": [{"class": "Anime", "confidence": 1.7}]},
    {"predictions": [{"class": "Anime", "confidence": float("nan")}]},
    {"predictions": [{"class": "Anime", "confidence": 0.0}]},
])
def test_respuestas_invalidas(datos):
    with mock.patch("requests.post", return_value=_respuesta(datos)):
        with pytest.raises(PredictorNoDisponible):
            _pred().predecir(_img())


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_errores_http(status):
    with mock.patch("requests.post", return_value=_respuesta({}, status)):
        with pytest.raises(PredictorNoDisponible):
            _pred().predecir(_img())


def test_sin_conexion():
    with mock.patch("requests.post", side_effect=requests.ConnectionError):
        with pytest.raises(PredictorNoDisponible):
            _pred().predecir(_img())


def test_peticion_bien_formada():
    with mock.patch("requests.post", return_value=_respuesta(RESPUESTA_UNA_ETIQUETA)) as post:
        _pred().predecir(_img(1200))
    args, kwargs = post.call_args
    assert args[0] == "https://serverless.roboflow.com/martin-stgmar-gmail-com/tattoo-styles-2-resnet18-t1"
    assert kwargs["params"] == {"api_key": "clave-secreta"}
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == 5
    # La imagen viaja reducida (máx. 640 px) y como JPEG
    enviada = Image.open(io.BytesIO(base64.b64decode(kwargs["data"])))
    assert enviada.format == "JPEG"
    assert max(enviada.size) == 640


def test_sin_api_key_no_arranca():
    with pytest.raises(ValueError):
        PredictorRoboflow("", "https://x", "m", 5, 640, config.CLASES_ROBOFLOW)


def test_servicio_responde_503_si_roboflow_falla(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    monkeypatch.setattr(main, "predictor", _pred())
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (1, 2, 3)).save(buf, "PNG")
    with mock.patch("requests.post", side_effect=requests.Timeout):
        r = TestClient(main.app).post(
            "/clasificar", files={"imagen": ("a.png", buf.getvalue(), "image/png")},
            headers={"X-API-Key": main.config.API_KEY},
        )
    assert r.status_code == 503
    assert "clave-secreta" not in r.text

"""
Pruebas del cliente del Roboflow Workflow, sin red.

La forma de la respuesta sigue la definición real del workflow
(entrada `image`, salida `predictions` = predicción del bloque
roboflow_classification_model@v3) y el formato de clasificación de Roboflow.
"""
import io
from unittest import mock

import pytest
import requests
from PIL import Image

from app import config
from app import roboflow_workflow as rfw
from app.predictor import PredictorNoDisponible, PredictorRoboflowWorkflow

PREDICCION = {
    "inference_id": "abc-123",
    "time": 0.08,
    "image": {"width": 224, "height": 224},
    "predictions": [
        {"class": "Ornamentos", "class_id": 5, "confidence": 0.8812},
        {"class": "Linea Fina", "class_id": 4, "confidence": 0.0711},
        {"class": "Alto contraste", "class_id": 0, "confidence": 0.0233},
        {"class": "Anime", "class_id": 1, "confidence": 0.0121},
        {"class": "Lettering", "class_id": 3, "confidence": 0.0063},
        {"class": "Tribal-Neotribal", "class_id": 6, "confidence": 0.0042},
        {"class": "Cibersigilismo", "class_id": 2, "confidence": 0.0018},
    ],
    "top": "Ornamentos",
    "confidence": 0.8812,
    "prediction_type": "classification",
}
RESPUESTA = {"outputs": [{"predictions": PREDICCION}], "profiler_trace": []}


def _cfg(**kw):
    base = dict(api_key="clave-secreta", reintentos=2, espera_inicial=0, timeout=7)
    base.update(kw)
    return rfw.ConfigWorkflow(**base)


def _resp(datos, status=200):
    r = mock.Mock(status_code=status)
    r.json = lambda: datos
    return r


def _img():
    return Image.new("RGB", (900, 700), (90, 30, 30))


# --- Petición -------------------------------------------------------------
def test_peticion_respeta_la_definicion_del_workflow():
    with mock.patch("requests.post", return_value=_resp(RESPUESTA)) as post:
        rfw.clasificar_tatuaje(_img(), _cfg())
    args, kwargs = post.call_args
    assert args[0] == ("https://serverless.roboflow.com/martin-stgmar-gmail-com/"
                       "workflows/tattoo-styles-vtattoo-styles-2-resnet18-t1-logic")
    # Solo la entrada declarada; el workflow no declara parámetros
    assert set(kwargs["json"]) == {"inputs"}
    assert set(kwargs["json"]["inputs"]) == {"image"}
    assert kwargs["json"]["inputs"]["image"]["type"] == "base64"
    # API key en la cabecera Bearer, nunca en la URL ni en el cuerpo
    assert kwargs["headers"] == {"Authorization": "Bearer clave-secreta"}
    assert "clave-secreta" not in args[0]
    assert "clave-secreta" not in str(kwargs["json"])
    assert kwargs["timeout"] == 7
    assert kwargs["allow_redirects"] is False


def test_imagen_enviada_reducida():
    import base64
    with mock.patch("requests.post", return_value=_resp(RESPUESTA)) as post:
        rfw.clasificar_tatuaje(_img(), _cfg(lado_max=640))
    valor = post.call_args.kwargs["json"]["inputs"]["image"]["value"]
    enviada = Image.open(io.BytesIO(base64.b64decode(valor)))
    assert enviada.format == "JPEG" and max(enviada.size) == 640


# --- Respuesta ------------------------------------------------------------
def test_extrae_confianzas_por_nombre():
    with mock.patch("requests.post", return_value=_resp(RESPUESTA)):
        r = rfw.clasificar_tatuaje(_img(), _cfg())
    assert r.top == "Ornamentos"
    assert r.inference_id == "abc-123"
    assert r.confianzas["Ornamentos"] == pytest.approx(0.8812)
    assert len(r.confianzas) == 7


@pytest.mark.parametrize("datos", [
    None, [], {}, {"outputs": []}, {"outputs": [{}]},
    {"outputs": [{"otra_salida": 1}]},
    {"outputs": [{"predictions": "x"}]},
    {"outputs": [{"predictions": {"top": "Anime"}}]},          # sin lista de clases
    {"outputs": [{"predictions": {"predictions": [{"class": "Anime", "confidence": 2}]}}]},
    {"outputs": [{"predictions": {"predictions": [{"class": 3, "confidence": 0.5}]}}]},
])
def test_respuestas_invalidas(datos):
    with mock.patch("requests.post", return_value=_resp(datos)):
        with pytest.raises(rfw.RoboflowRespuestaInvalidaError):
            rfw.clasificar_tatuaje(_img(), _cfg())


def test_mensaje_dice_que_salidas_llegaron():
    with mock.patch("requests.post", return_value=_resp({"outputs": [{"resultado": {}}]})):
        with pytest.raises(rfw.RoboflowRespuestaInvalidaError, match="resultado"):
            rfw.clasificar_tatuaje(_img(), _cfg())


# --- Errores y reintentos -------------------------------------------------
@pytest.mark.parametrize("status,error", [
    (401, rfw.RoboflowAutenticacionError),
    (403, rfw.RoboflowAutenticacionError),
    (404, rfw.RoboflowNoEncontradoError),
    (400, rfw.RoboflowRespuestaInvalidaError),
])
def test_errores_que_no_se_reintentan(status, error):
    with mock.patch("requests.post", return_value=_resp({}, status)) as post:
        with pytest.raises(error):
            rfw.clasificar_tatuaje(_img(), _cfg())
    assert post.call_count == 1


@pytest.mark.parametrize("status,error", [
    (429, rfw.RoboflowLimiteError),
    (503, rfw.RoboflowNoDisponibleError),
])
def test_reintenta_y_luego_falla(status, error):
    with mock.patch("requests.post", return_value=_resp({}, status)) as post:
        with pytest.raises(error):
            rfw.clasificar_tatuaje(_img(), _cfg(reintentos=2))
    assert post.call_count == 3


def test_reintento_exitoso_tras_timeout():
    with mock.patch("requests.post", side_effect=[requests.Timeout, _resp(RESPUESTA)]) as post:
        r = rfw.clasificar_tatuaje(_img(), _cfg())
    assert post.call_count == 2 and r.top == "Ornamentos"


def test_espera_crece_entre_reintentos():
    with mock.patch("requests.post", side_effect=requests.ConnectionError), \
            mock.patch("time.sleep") as dormir:
        with pytest.raises(rfw.RoboflowNoDisponibleError):
            rfw.clasificar_tatuaje(_img(), _cfg(reintentos=2, espera_inicial=0.5))
    assert [c.args[0] for c in dormir.call_args_list] == [0.5, 1.0]


def test_sin_api_key():
    with pytest.raises(rfw.RoboflowAutenticacionError):
        rfw.clasificar_tatuaje(_img(), _cfg(api_key=""))


# --- Integración con el servicio -----------------------------------------
def _predictor():
    return PredictorRoboflowWorkflow(_cfg(), config.CLASES_ROBOFLOW)


def test_predictor_traduce_a_codigos():
    with mock.patch("requests.post", return_value=_resp(RESPUESTA)):
        conf = _predictor().predecir(_img())
    assert max(conf, key=conf.get) == "E-06"           # Ornamentos
    assert set(conf) == {f"E-0{i}" for i in range(1, 8)}
    assert abs(sum(conf.values()) - 1) < 1e-6


def test_clases_bajo_umbral_omitidas_no_se_inflan():
    # El bloque usa umbral 0,4: si Roboflow solo informa la clase que lo supera,
    # su confianza NO debe re-escalarse a 100 %.
    solo_top = {"outputs": [{"predictions": {
        "predictions": [{"class": "Anime", "confidence": 0.62}], "top": "Anime"}}]}
    with mock.patch("requests.post", return_value=_resp(solo_top)):
        conf = _predictor().predecir(_img())
    assert conf["E-02"] == pytest.approx(0.62)
    assert sum(conf.values()) == pytest.approx(0.62)


def test_respuesta_real_con_una_sola_clase():
    # Forma exacta observada en el smoke test real (2026-11-03)
    real = {"outputs": [{"predictions": {"predictions": [{"class": "Linea Fina", "confidence": 0.4182}],
                                         "top": "Linea Fina"}}], "profiler_trace": []}
    with mock.patch("requests.post", return_value=_resp(real)):
        conf = _predictor().predecir(_img())
    assert conf["E-05"] == pytest.approx(0.4182)


def test_ninguna_clase_sobre_el_umbral_es_fuera_de_catalogo():
    vacia = {"outputs": [{"predictions": {"predictions": [], "top": None}}], "profiler_trace": []}
    with mock.patch("requests.post", return_value=_resp(vacia)):
        assert rfw.clasificar_tatuaje(_img(), _cfg()).confianzas == {}
        conf = _predictor().predecir(_img())
    assert conf["E-99"] == 1.0
    assert sum(v for c, v in conf.items() if c != "E-99") == 0


def test_clase_desconocida():
    otra = {"outputs": [{"predictions": {"predictions": [{"class": "Realismo", "confidence": 0.9}]}}]}
    with mock.patch("requests.post", return_value=_resp(otra)):
        with pytest.raises(PredictorNoDisponible, match="desconocida"):
            _predictor().predecir(_img())


def test_error_de_roboflow_se_convierte_en_no_disponible():
    with mock.patch("requests.post", return_value=_resp({}, 401)):
        with pytest.raises(PredictorNoDisponible, match="API key"):
            _predictor().predecir(_img())


def test_seleccion_por_defecto_con_clave(monkeypatch):
    from app import predictor as mod
    monkeypatch.setattr(mod.config, "FORZAR_STUB", False)
    monkeypatch.setattr(mod.config, "MODO_PREDICTOR", "auto")
    monkeypatch.setattr(mod.config, "ROBOFLOW_API_KEY", "x")
    p = mod.cargar_predictor()
    assert isinstance(p, PredictorRoboflowWorkflow)
    assert p.version == ("roboflow-workflow:martin-stgmar-gmail-com/"
                         "tattoo-styles-vtattoo-styles-2-resnet18-t1-logic")

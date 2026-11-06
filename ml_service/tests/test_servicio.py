import io
import os

os.environ["ML_SERVICE_API_KEY"] = "clave-de-prueba"
os.environ["ML_FORZAR_STUB"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402

cliente = TestClient(app)
CABECERA = {"X-API-Key": "clave-de-prueba"}


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_salud():
    assert cliente.get("/salud").json()["estado"] == "ok"


def test_limite_diez_mb_en_servicio():
    limite = 10 * 1024 * 1024
    png = _png()
    datos = png + b"\0" * (limite - len(png))
    assert cliente.post("/clasificar", files={"imagen": ("limite.png", datos, "image/png")}, headers=CABECERA).status_code == 200
    assert cliente.post("/clasificar", files={"imagen": ("exceso.png", datos + b"\0", "image/png")}, headers=CABECERA).status_code == 413


def test_sin_clave_rechaza():
    r = cliente.post("/clasificar", files={"imagen": ("a.png", _png(), "image/png")})
    assert r.status_code == 401


def test_clave_incorrecta_rechaza():
    r = cliente.post("/clasificar", files={"imagen": ("a.png", _png(), "image/png")},
                     headers={"X-API-Key": "otra"})
    assert r.status_code == 401


def test_clasifica_y_suma_uno():
    r = cliente.post("/clasificar", files={"imagen": ("a.png", _png(), "image/png")}, headers=CABECERA)
    assert r.status_code == 200
    conf = r.json()["confianzas"]
    assert list(conf) == ["E-01", "E-02", "E-03", "E-04", "E-05", "E-06", "E-07", "E-99"]
    assert abs(sum(conf.values()) - 1) < 1e-6


def test_determinista():
    a = cliente.post("/clasificar", files={"imagen": ("a.png", _png(), "image/png")}, headers=CABECERA).json()
    b = cliente.post("/clasificar", files={"imagen": ("b.png", _png(), "image/png")}, headers=CABECERA).json()
    assert a == b


def test_rechaza_no_imagen():
    r = cliente.post("/clasificar", files={"imagen": ("v.png", b"\x00\x00\x00\x18ftypmp42" + b"0" * 100, "image/png")},
                     headers=CABECERA)
    assert r.status_code == 415


def test_sin_documentacion_publica():
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404

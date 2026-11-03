"""
Smoke test contra el Roboflow Workflow REAL (usa la red y consume créditos).

Se omite salvo que se pida explícitamente:

    cd ml_service
    ROBOFLOW_SMOKE=1 python -m pytest tests/test_smoke_roboflow.py -s

La API key se lee de ml_service/.env (ROBOFLOW_API_KEY). Para probar con una
foto propia: ROBOFLOW_SMOKE_IMAGEN=ruta/a/tatuaje.jpg
"""
import os

import pytest
from PIL import Image

from app import config
from app import roboflow_workflow as rfw

pytestmark = pytest.mark.skipif(
    os.environ.get("ROBOFLOW_SMOKE") != "1",
    reason="Smoke test real: activar con ROBOFLOW_SMOKE=1",
)


def _imagen_de_prueba() -> Image.Image:
    ruta = os.environ.get("ROBOFLOW_SMOKE_IMAGEN")
    if ruta:
        return Image.open(ruta)
    # Imagen sintética: sirve para comprobar el contrato (claves de salida),
    # no la calidad de la clasificación.
    img = Image.new("RGB", (448, 448), (235, 225, 215))
    for x in range(40, 408, 8):
        for y in range(40, 408, 8):
            if (x // 8 + y // 8) % 3 == 0:
                img.putpixel((x, y), (20, 20, 20))
    return img


def _resumen(valor, nivel=0):
    """Estructura de la respuesta sin volcar contenido largo (p. ej. base64)."""
    if isinstance(valor, dict):
        return {k: _resumen(v, nivel + 1) for k, v in valor.items()} if nivel < 3 else "{…}"
    if isinstance(valor, list):
        return [_resumen(valor[0], nivel + 1), f"… {len(valor)} elementos"] if valor else []
    if isinstance(valor, str) and len(valor) > 80:
        return f"<texto de {len(valor)} caracteres>"
    return valor


def test_workflow_real_devuelve_las_salidas_declaradas():
    if not config.ROBOFLOW_API_KEY:
        pytest.fail("Falta ROBOFLOW_API_KEY en ml_service/.env")
    cfg = rfw.ConfigWorkflow(
        api_key=config.ROBOFLOW_API_KEY,
        api_url=config.ROBOFLOW_API_URL,
        workspace=config.ROBOFLOW_WORKSPACE,
        workflow_id=config.ROBOFLOW_WORKFLOW_ID,
        timeout=config.ROBOFLOW_TIMEOUT,
    )
    img = _imagen_de_prueba()

    # 1. Respuesta cruda: contrato del workflow
    cuerpo = {"inputs": {"image": {"type": "base64", "value": rfw._imagen_base64(img, cfg.lado_max)}}}
    datos = rfw._post_con_reintentos(cfg, cuerpo).json()
    print("\nEstructura de la respuesta:", _resumen(datos))
    assert isinstance(datos.get("outputs"), list) and datos["outputs"], "Sin 'outputs'"
    entrada = datos["outputs"][0]
    assert rfw.SALIDA_PREDICCIONES in entrada, f"Salidas recibidas: {sorted(entrada)}"

    # 2. La función de la integración
    resultado = rfw.clasificar_tatuaje(img, cfg)
    print("Top:", resultado.top, "| confianzas:", resultado.confianzas)
    if not resultado.confianzas:
        print("Ningún estilo superó el umbral de 0,4 (fuera de catálogo).")
    conocidas = {n.lower() for n in config.CLASES_ROBOFLOW}
    desconocidas = [n for n in resultado.confianzas if n.lower() not in conocidas]
    assert not desconocidas, f"Clases que el catálogo no conoce: {desconocidas}"

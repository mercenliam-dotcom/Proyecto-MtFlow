"""
Cliente del Roboflow Workflow "Tattoo styles vtattoo-styles-2-resnet18-t1 Logic".

Definición real (leída de Roboflow el 2026-11-03):

    workspace : martin-stgmar-gmail-com
    workflow  : tattoo-styles-vtattoo-styles-2-resnet18-t1-logic
    entradas  : image (InferenceImage)          -> sin parámetros declarados
    pasos     : sub-workflow "tattoo-styles" con el modelo
                martin-stgmar-gmail-com/tattoo-styles-2-resnet18-t1
                (bloque roboflow_classification_model@v3, umbral 0,4 por defecto)
    salidas   : predictions (JsonField)        -> la predicción de clasificación

Se usa la API REST con `requests` (ya es dependencia del servicio) en vez de
`inference-sdk`, que agrega ~35 paquetes nativos (OpenCV, SciPy, FFmpeg).

La API key viaja en `Authorization: Bearer`, nunca en la URL ni en el cuerpo.
"""
from __future__ import annotations

import base64
import io
import logging
import time
from dataclasses import dataclass

import requests
from PIL import Image

log = logging.getLogger("mtflow.ml")

API_URL_POR_DEFECTO = "https://serverless.roboflow.com"
WORKSPACE_POR_DEFECTO = "martin-stgmar-gmail-com"
WORKFLOW_POR_DEFECTO = "tattoo-styles-vtattoo-styles-2-resnet18-t1-logic"
SALIDA_PREDICCIONES = "predictions"   # nombre de la salida declarada en el workflow


# ---------------------------------------------------------------------------
# Errores tipados
# ---------------------------------------------------------------------------
class RoboflowError(Exception):
    """Error base de la integración con Roboflow."""


class RoboflowAutenticacionError(RoboflowError):
    """401/403: la API key no es válida o no tiene acceso al workflow."""


class RoboflowNoEncontradoError(RoboflowError):
    """404: el workspace o el workflow no existen con ese identificador."""


class RoboflowLimiteError(RoboflowError):
    """429: se superó el límite de uso del plan."""


class RoboflowNoDisponibleError(RoboflowError):
    """Sin conexión, tiempo agotado o error 5xx tras los reintentos."""


class RoboflowRespuestaInvalidaError(RoboflowError):
    """La respuesta no tiene la forma que declara el workflow."""


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClasificacionWorkflow:
    confianzas: dict[str, float]   # nombre de clase en Roboflow -> confianza [0,1]
    top: str | None                # clase ganadora según Roboflow (si la informa)
    inference_id: str | None


@dataclass(frozen=True)
class ConfigWorkflow:
    api_key: str
    api_url: str = API_URL_POR_DEFECTO
    workspace: str = WORKSPACE_POR_DEFECTO
    workflow_id: str = WORKFLOW_POR_DEFECTO
    timeout: float = 15.0
    reintentos: int = 2            # además del primer intento
    espera_inicial: float = 0.5    # segundos; se duplica en cada reintento
    lado_max: int = 640            # el modelo trabaja a 224x224

    @property
    def url(self) -> str:
        return f"{self.api_url.rstrip('/')}/{self.workspace}/workflows/{self.workflow_id}"


_REINTENTABLES = {429, 500, 502, 503, 504}


def _imagen_base64(img: Image.Image, lado_max: int) -> str:
    copia = img.convert("RGB")
    copia.thumbnail((lado_max, lado_max))
    buf = io.BytesIO()
    copia.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _post_con_reintentos(cfg: ConfigWorkflow, cuerpo: dict) -> requests.Response:
    espera = cfg.espera_inicial
    ultimo_error: RoboflowError | None = None
    for intento in range(cfg.reintentos + 1):
        try:
            r = requests.post(
                cfg.url,
                json=cuerpo,
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                timeout=cfg.timeout,
                allow_redirects=False,
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo_error = RoboflowNoDisponibleError(f"Sin conexión con Roboflow ({type(e).__name__})")
        else:
            if r.status_code == 200:
                return r
            if r.status_code in (401, 403):
                raise RoboflowAutenticacionError(f"Roboflow rechazó la API key (HTTP {r.status_code})")
            if r.status_code == 404:
                raise RoboflowNoEncontradoError("Roboflow no encuentra el workflow (HTTP 404)")
            if r.status_code not in _REINTENTABLES:
                raise RoboflowRespuestaInvalidaError(f"Roboflow respondió HTTP {r.status_code}")
            ultimo_error = (RoboflowLimiteError if r.status_code == 429 else RoboflowNoDisponibleError)(
                f"Roboflow respondió HTTP {r.status_code}"
            )
        if intento < cfg.reintentos:
            log.warning("Roboflow: intento %d falló (%s); reintentando en %.1fs",
                        intento + 1, ultimo_error, espera)
            time.sleep(espera)
            espera *= 2
    assert ultimo_error is not None
    raise ultimo_error


def _extraer_clasificacion(datos) -> ClasificacionWorkflow:
    """
    La API REST responde {"outputs": [ {<salida>: valor, ...}, ... ]}, una entrada
    por imagen. La salida "predictions" contiene la predicción del bloque de
    clasificación:
        {"predictions": [{"class": "...", "confidence": 0.9, ...}], "top": "...", ...}
    También se acepta la forma multietiqueta {"predictions": {"clase": {"confidence": x}}}.
    """
    if not isinstance(datos, dict) or not isinstance(datos.get("outputs"), list) or not datos["outputs"]:
        raise RoboflowRespuestaInvalidaError("La respuesta no trae 'outputs'")
    entrada = datos["outputs"][0]
    if not isinstance(entrada, dict) or SALIDA_PREDICCIONES not in entrada:
        claves = sorted(entrada) if isinstance(entrada, dict) else type(entrada).__name__
        raise RoboflowRespuestaInvalidaError(
            f"Falta la salida '{SALIDA_PREDICCIONES}' (salidas recibidas: {claves})"
        )
    bloque = entrada[SALIDA_PREDICCIONES]
    if not isinstance(bloque, dict):
        raise RoboflowRespuestaInvalidaError("'predictions' no es un objeto")

    interno = bloque.get("predictions")
    pares: list[tuple] = []
    if isinstance(interno, list):
        pares = [(p.get("class"), p.get("confidence")) for p in interno if isinstance(p, dict)]
    elif isinstance(interno, dict):
        pares = [(k, v.get("confidence") if isinstance(v, dict) else v) for k, v in interno.items()]
    if not pares:
        raise RoboflowRespuestaInvalidaError("La predicción no trae clases")

    confianzas: dict[str, float] = {}
    for nombre, valor in pares:
        if not isinstance(nombre, str) or isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise RoboflowRespuestaInvalidaError("Clase o confianza con formato inesperado")
        if valor != valor or not 0.0 <= valor <= 1.0:   # NaN o fuera de rango
            raise RoboflowRespuestaInvalidaError("Confianza fuera de [0, 1]")
        confianzas[nombre] = float(valor)

    top = bloque.get("top") if isinstance(bloque.get("top"), str) else None
    inference_id = bloque.get("inference_id") if isinstance(bloque.get("inference_id"), str) else None
    return ClasificacionWorkflow(confianzas, top, inference_id)


def clasificar_tatuaje(img: Image.Image, cfg: ConfigWorkflow) -> ClasificacionWorkflow:
    """
    Ejecuta el workflow sobre una imagen y devuelve las confianzas por clase.

    El workflow no declara parámetros, así que solo se envía la entrada `image`.
    Lanza una subclase de RoboflowError si algo falla; nunca devuelve datos a medias.
    """
    if not cfg.api_key:
        raise RoboflowAutenticacionError("Falta ROBOFLOW_API_KEY")
    cuerpo = {"inputs": {"image": {"type": "base64", "value": _imagen_base64(img, cfg.lado_max)}}}
    r = _post_con_reintentos(cfg, cuerpo)
    try:
        datos = r.json()
    except ValueError as e:
        raise RoboflowRespuestaInvalidaError("La respuesta de Roboflow no es JSON") from e
    return _extraer_clasificacion(datos)

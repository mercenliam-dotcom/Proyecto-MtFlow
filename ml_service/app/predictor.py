"""
Predictores intercambiables. Todos reciben una imagen PIL ya validada y
devuelven {codigo_estilo: probabilidad}. Las probabilidades suman 1, salvo
cuando Roboflow omite las clases bajo su umbral: entonces suman menos y no se
re-escalan (re-escalar inflaría la confianza).

- PredictorRoboflowWorkflow: ejecuta el Roboflow Workflow
  "tattoo-styles-vtattoo-styles-2-resnet18-t1-logic" (ver roboflow_workflow.py).
  Es el camino recomendado.
- PredictorRoboflow: consulta directamente el endpoint del modelo
  (ResNet18, proyecto "Tattoo styles").
- PredictorEfficientNetKeras: modelo local v1 de siete clases, cargado bajo demanda.
- PredictorEfficientNet: adaptador histórico de PyTorch (local_pytorch).
- PredictorSimulado: resultados falsos pero deterministas, para desarrollar
  la web sin conexión ni modelo.
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import math
import unicodedata
from pathlib import Path

import requests
from PIL import Image

from . import config
from . import roboflow_workflow as rfw

log = logging.getLogger("mtflow.ml")


class PredictorNoDisponible(Exception):
    """El modelo no respondió o respondió algo que no se puede usar."""


# ---------------------------------------------------------------------------
# Roboflow
# ---------------------------------------------------------------------------
def _clave_nombre(nombre: str) -> str:
    """'Línea  Fina' -> 'lineafina'. Tolera tildes, mayúsculas, espacios y guiones."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return "".join(c for c in sin_tildes.lower() if c.isalnum())


def _a_codigos(por_nombre: dict[str, float], mapa: dict[str, str], codigos: list[str]) -> dict[str, float]:
    """Traduce {nombre de clase: confianza} a {código: confianza}. Nunca adivina."""
    confianzas = {c: 0.0 for c in codigos}
    for nombre, valor in por_nombre.items():
        codigo = mapa.get(_clave_nombre(nombre))
        if codigo is None:
            raise PredictorNoDisponible(f"Clase desconocida en el modelo: {nombre[:40]!r}")
        confianzas[codigo] += float(valor)
    total = sum(confianzas.values())
    if total <= 0:
        raise PredictorNoDisponible("Todas las confianzas son cero")
    if 0.98 <= total <= 1.02:
        # Solo se corrige el redondeo. Si suma bastante menos que 1 es porque
        # Roboflow omitió clases bajo su umbral: se dejan tal cual.
        return {c: round(v / total, 6) for c, v in confianzas.items()}
    if total > 1.02:
        # Multietiqueta: cada clase es independiente; se escala para comparar.
        return {c: round(v / total, 6) for c, v in confianzas.items()}
    return {c: round(v, 6) for c, v in confianzas.items()}


class PredictorRoboflowWorkflow:
    """Ejecuta el Roboflow Workflow y traduce sus clases a los códigos internos."""

    def __init__(self, cfg: rfw.ConfigWorkflow, clases: dict[str, str]):
        if not cfg.api_key:
            raise ValueError("Falta ROBOFLOW_API_KEY")
        self.cfg = cfg
        self.mapa = {_clave_nombre(n): c for n, c in clases.items()}
        self.codigos = sorted(set(clases.values()))
        self.version = f"roboflow-workflow:{cfg.workspace}/{cfg.workflow_id}"

    def predecir(self, img: Image.Image) -> dict[str, float]:
        try:
            resultado = rfw.clasificar_tatuaje(img, self.cfg)
        except rfw.RoboflowError as e:
            log.error("Roboflow Workflow: %s", e)
            raise PredictorNoDisponible(str(e)) from e
        if not resultado.confianzas:
            # Ningún estilo superó el umbral del workflow: fuera de catálogo.
            log.info("Roboflow Workflow: ningún estilo superó el umbral -> E-99")
            return {**{c: 0.0 for c in self.codigos}, "E-99": 1.0}
        return _a_codigos(resultado.confianzas, self.mapa, self.codigos)


class PredictorRoboflow:
    def __init__(self, api_key: str, api_url: str, model_id: str, timeout: float,
                 lado_max: int, clases: dict[str, str]):
        if not api_key:
            raise ValueError("Falta ROBOFLOW_API_KEY")
        self.api_key = api_key
        self.url = f"{api_url.rstrip('/')}/{model_id.strip('/')}"
        self.timeout = timeout
        self.lado_max = lado_max
        self.mapa = {_clave_nombre(n): c for n, c in clases.items()}
        self.codigos = sorted(set(clases.values()))
        self.version = f"roboflow:{model_id}"

    def _imagen_base64(self, img: Image.Image) -> str:
        copia = img.convert("RGB")
        copia.thumbnail((self.lado_max, self.lado_max))
        buf = io.BytesIO()
        copia.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _extraer(self, datos) -> dict[str, float]:
        """
        Acepta los dos formatos de Roboflow para clasificación:
          una etiqueta:  {"predictions": [{"class": "Anime", "confidence": 0.9}, ...]}
          multietiqueta: {"predictions": {"Anime": {"confidence": 0.9}, ...}}
        """
        if not isinstance(datos, dict):
            raise PredictorNoDisponible("Respuesta de Roboflow no es un objeto")
        pred = datos.get("predictions")
        pares = []
        if isinstance(pred, list):
            pares = [(p.get("class"), p.get("confidence")) for p in pred if isinstance(p, dict)]
        elif isinstance(pred, dict):
            pares = [(k, v.get("confidence") if isinstance(v, dict) else v) for k, v in pred.items()]
        if not pares:
            raise PredictorNoDisponible("Respuesta de Roboflow sin predicciones")

        por_nombre: dict[str, float] = {}
        for nombre, valor in pares:
            if not isinstance(nombre, str) or isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise PredictorNoDisponible("Predicción con formato inesperado")
            if math.isnan(valor) or not 0.0 <= valor <= 1.0:
                raise PredictorNoDisponible("Confianza fuera de rango")
            por_nombre[nombre] = por_nombre.get(nombre, 0.0) + float(valor)
        return _a_codigos(por_nombre, self.mapa, self.codigos)

    def predecir(self, img: Image.Image) -> dict[str, float]:
        try:
            r = requests.post(
                self.url,
                data=self._imagen_base64(img),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as e:
            log.error("Roboflow no responde: %s", type(e).__name__)
            raise PredictorNoDisponible("Sin conexión con Roboflow") from e
        if r.status_code != 200:
            # No se registra el cuerpo: podría repetir la URL con la clave.
            log.error("Roboflow respondió HTTP %s", r.status_code)
            raise PredictorNoDisponible(f"Roboflow HTTP {r.status_code}")
        try:
            datos = r.json()
        except ValueError as e:
            raise PredictorNoDisponible("Respuesta de Roboflow no es JSON") from e
        return self._extraer(datos)


# ---------------------------------------------------------------------------
# Simulado
# ---------------------------------------------------------------------------
class PredictorSimulado:
    version = "simulado-0.2"

    def predecir(self, img: Image.Image) -> dict[str, float]:
        miniatura = img.convert("RGB").resize((32, 32))
        semilla = hashlib.sha256(miniatura.tobytes()).digest()
        clases = config.CLASES
        # Logits pseudoaleatorios a partir del hash; una clase "gana" con
        # margen para que se vean los tres estados de la recomendación.
        logits = [b / 255.0 * 3.0 for b in semilla[: len(clases)]]
        ganadora = semilla[10] % len(clases)
        logits[ganadora] += 1.5 + (semilla[11] / 255.0) * 4.0
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        total = sum(exps)
        redondeadas = [round(e / total, 4) for e in exps]
        redondeadas[ganadora] = round(redondeadas[ganadora] + 1.0 - sum(redondeadas), 4)
        return dict(zip(clases, redondeadas))


# ---------------------------------------------------------------------------
# Local (EfficientNet-B0)
# ---------------------------------------------------------------------------
class PredictorEfficientNet:
    """Inferencia con pesos propios. Requiere torch y torchvision (requirements-modelo.txt)."""

    def __init__(self, ruta_pesos: Path):
        import torch
        from torchvision import models, transforms

        self.torch = torch
        modelo = models.efficientnet_b0(weights=None)
        entradas = modelo.classifier[1].in_features
        modelo.classifier[1] = torch.nn.Linear(entradas, len(config.CLASES))
        estado = torch.load(ruta_pesos, map_location="cpu", weights_only=True)
        modelo.load_state_dict(estado)
        modelo.eval()
        self.modelo = modelo
        self.transformar = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.version = f"efficientnet_b0:{ruta_pesos.name}"

    def predecir(self, img: Image.Image) -> dict[str, float]:
        x = self.transformar(img.convert("RGB")).unsqueeze(0)
        with self.torch.inference_mode():
            probs = self.torch.softmax(self.modelo(x), dim=1)[0].tolist()
        return {c: round(float(p), 6) for c, p in zip(config.CLASES, probs)}


def cargar_predictor():
    modo = "simulado" if config.FORZAR_STUB else config.MODO_PREDICTOR
    if modo == "auto":
        from .modelo_local import hay_pesos_keras

        if config.ROBOFLOW_API_KEY:
            modo = "roboflow_workflow"
        elif hay_pesos_keras(config.MTFLOW_MODEL_DIR):
            modo = "local"
        elif Path(config.MODELO_RUTA).is_file():
            modo = "local_pytorch"
        else:
            modo = "simulado"
    if modo in ("roboflow_workflow", "workflow"):
        cfg = rfw.ConfigWorkflow(
            api_key=config.ROBOFLOW_API_KEY,
            api_url=config.ROBOFLOW_API_URL,
            workspace=config.ROBOFLOW_WORKSPACE,
            workflow_id=config.ROBOFLOW_WORKFLOW_ID,
            timeout=config.ROBOFLOW_TIMEOUT,
            reintentos=config.ROBOFLOW_REINTENTOS,
            lado_max=config.ROBOFLOW_LADO_MAX,
        )
        return PredictorRoboflowWorkflow(cfg, config.CLASES_ROBOFLOW)
    if modo in ("roboflow", "roboflow_modelo"):
        return PredictorRoboflow(
            config.ROBOFLOW_API_KEY, config.ROBOFLOW_API_URL, config.ROBOFLOW_MODEL_ID,
            config.ROBOFLOW_TIMEOUT, config.ROBOFLOW_LADO_MAX, config.CLASES_ROBOFLOW,
        )
    if modo == "local":
        from .modelo_local import PredictorEfficientNetKeras
        return PredictorEfficientNetKeras(config.MTFLOW_MODEL_DIR)
    if modo == "local_pytorch":
        return PredictorEfficientNet(Path(config.MODELO_RUTA))
    if modo == "simulado":
        return PredictorSimulado()
    raise ValueError(
        f"ML_PREDICTOR desconocido: {modo!r} "
        "(usa local, local_pytorch, roboflow_workflow, roboflow_modelo, simulado o auto)"
    )

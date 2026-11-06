"""Único predictor operativo: EfficientNetB0 TensorFlow/Keras local."""
import unicodedata
from . import config

class PredictorNoDisponible(Exception):
    """El modelo no pudo producir una respuesta válida."""

def _clave_nombre(nombre: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return "".join(c for c in normalizado.lower() if c.isalnum())

def cargar_predictor():
    if config.MODO_PREDICTOR != "local":
        raise ValueError("Este servicio solo admite ML_PREDICTOR=local (EfficientNet Keras).")
    from .modelo_local import PredictorEfficientNetKeras
    return PredictorEfficientNetKeras(config.MTFLOW_MODEL_DIR)

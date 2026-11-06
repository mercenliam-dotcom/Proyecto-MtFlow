"""Decisión de abstención; E-99 es una regla del sistema, no una clase aprendida."""
import math

from . import config
from .predictor import PredictorNoDisponible

CODIGOS = tuple(f"E-{i:02}" for i in range(1, 8))


def construir_respuesta(version, confianzas):
    if not isinstance(confianzas, dict) or set(confianzas) != set(CODIGOS):
        raise PredictorNoDisponible("Faltan probabilidades de los siete estilos.")
    valores = list(confianzas.values())
    if (any(isinstance(p, bool) or not isinstance(p, (int, float))
            or not math.isfinite(p) or not 0 <= p <= 1 for p in valores)
            or not math.isclose(sum(valores), 1.0, abs_tol=1e-4)):
        raise PredictorNoDisponible("Probabilidades inválidas.")
    ganador = max(CODIGOS, key=confianzas.get)
    maxima = confianzas[ganador]
    estilo = ganador if maxima >= config.UMBRAL_CONFIANZA else "E-99"
    return {
        "version_modelo": version,
        "confianzas": confianzas,
        "estilo_sugerido": estilo,
        "confianza_maxima": maxima,
        "umbral_confianza": config.UMBRAL_CONFIANZA,
    }

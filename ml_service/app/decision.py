"""Decisión de abstención; E-99 es una regla del sistema, no una clase aprendida."""
import math

from . import config
from .predictor import PredictorNoDisponible

CODIGOS = tuple(f"E-{i:02}" for i in range(1, 8))


def construir_respuesta(version, confianzas, ood=None):
    if not isinstance(confianzas, dict) or set(confianzas) != set(CODIGOS):
        raise PredictorNoDisponible("Faltan probabilidades de los siete estilos.")
    valores = list(confianzas.values())
    if (any(isinstance(p, bool) or not isinstance(p, (int, float))
            or not math.isfinite(p) or not 0 <= p <= 1 for p in valores)
            or not math.isclose(sum(valores), 1.0, abs_tol=1e-4)):
        raise PredictorNoDisponible("Probabilidades inválidas.")
    ganador = max(CODIGOS, key=confianzas.get)
    maxima = confianzas[ganador]
    if ":ood:" in version and ood is None:
        raise PredictorNoDisponible("Falta el análisis OOD del modelo.")
    fuera = False
    if ood is not None:
        if not isinstance(ood, dict) or set(ood) != {"version", "distancia", "umbral", "fuera_distribucion"}:
            raise PredictorNoDisponible("Metadatos OOD inválidos.")
        for campo in ("distancia", "umbral"):
            valor = ood[campo]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not 0 <= valor <= 2:
                raise PredictorNoDisponible("Puntuación OOD inválida.")
        identificador = ood["version"]
        if (not isinstance(identificador, str) or len(identificador) != 64
                or any(c not in "0123456789abcdef" for c in identificador)
                or not version.endswith(":ood:" + identificador[:16])
                or type(ood["fuera_distribucion"]) is not bool
                or ood["fuera_distribucion"] != (ood["distancia"] > ood["umbral"])):
            raise PredictorNoDisponible("Decisión OOD inconsistente.")
        fuera = ood["fuera_distribucion"]
    motivo = "fuera_distribucion" if fuera else "confianza_insuficiente" if maxima < config.UMBRAL_CONFIANZA else None
    estilo = ganador if motivo is None else "E-99"
    return {
        "version_modelo": version,
        "confianzas": confianzas,
        "estilo_sugerido": estilo,
        "confianza_maxima": maxima,
        "umbral_confianza": config.UMBRAL_CONFIANZA,
        "ood": ood,
        "motivo_abstencion": motivo,
    }

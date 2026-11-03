"""
Catálogo de estilos del estudio y lógica de recomendación.

PROVISORIO: los nombres reales de los seis estilos aún deben confirmarlos
las socias. Al confirmarlos, cambiar SOLO este diccionario (los códigos
E-01…E-06 y E-99 se mantienen, porque son los que usa el modelo).
"""
from dataclasses import dataclass

from django.conf import settings

ESTILOS = {
    "E-01": "Estilo 1 (por definir)",
    "E-02": "Estilo 2 (por definir)",
    "E-03": "Estilo 3 (por definir)",
    "E-04": "Estilo 4 (por definir)",
    "E-05": "Estilo 5 (por definir)",
    "E-06": "Estilo 6 (por definir)",
    "E-99": "Fuera de catálogo",
}
CODIGO_FUERA_DE_CATALOGO = "E-99"


@dataclass(frozen=True)
class Recomendacion:
    codigo: str          # APTO | EN_EVALUACION | NO_RECOMENDADO
    alerta_ml: str       # valor de AlertaML en el modelo de datos
    titulo: str
    explicacion: str


def recomendar(estilo: str, confianza: float) -> Recomendacion:
    """
    El sistema RECOMIENDA, no decide (ADR-0004). Ninguna de estas salidas
    rechaza una solicitud: todas llegan a la tatuadora con su marca.
    Umbrales tentativos, configurables por variable de entorno.
    """
    if estilo == CODIGO_FUERA_DE_CATALOGO:
        return Recomendacion(
            "NO_RECOMENDADO", "REVISION_ESPECIAL", "No recomendado",
            "La imagen no se parece a ningún estilo del catálogo del estudio.",
        )
    if confianza >= settings.UMBRAL_PRE_APROBADA:
        return Recomendacion(
            "APTO", "PRE_APROBADA", "Apto",
            "Alta similitud con un estilo que el estudio trabaja.",
        )
    if confianza >= settings.UMBRAL_REVISION:
        return Recomendacion(
            "EN_EVALUACION", "REVISION_ESPECIAL", "En evaluación",
            "Similitud intermedia: la tatuadora decide según tamaño y complejidad.",
        )
    return Recomendacion(
        "NO_RECOMENDADO", "REVISION_ESPECIAL", "No recomendado",
        "Similitud bajo el umbral requerido. La solicitud igual llega a la tatuadora.",
    )

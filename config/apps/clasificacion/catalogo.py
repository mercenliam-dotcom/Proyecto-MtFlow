"""
Catálogo de estilos del estudio y lógica de recomendación.

Los nombres son las 7 clases del modelo entrenado en Roboflow (proyecto
"Tattoo styles"). El servicio de inferencia traduce cada clase a su código
(ml_service/app/config.py, CLASES_ROBOFLOW). Si se agrega o renombra una
clase, hay que cambiar ambos lugares.

E-99 representa la ausencia de clases sobre el umbral del workflow.
No demuestra por sí sola que una imagen no sea un tatuaje.
"""
from dataclasses import dataclass

from django.conf import settings

ESTILOS = {
    "E-01": "Alto contraste",
    "E-02": "Anime",
    "E-03": "Cibersigilismo",
    "E-04": "Lettering",
    "E-05": "Línea fina",
    "E-06": "Ornamentos",
    "E-07": "Tribal / Neotribal",
    "E-99": "Fuera de catálogo",
}
CODIGO_FUERA_DE_CATALOGO = "E-99"
# Estilos que el modelo SIEMPRE debe informar (E-99 es opcional)
ESTILOS_OBLIGATORIOS = frozenset(c for c in ESTILOS if c != CODIGO_FUERA_DE_CATALOGO)


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
            "Ningún estilo del catálogo alcanzó la similitud mínima del modelo (40 %). "
            "La revisión final corresponde a la tatuadora.",
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
        "Similitud bajo el umbral requerido. La revisión final corresponde a la tatuadora.",
    )

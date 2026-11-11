"""
Cliente del servicio de inferencia (FastAPI, ADR-0002).

- La URL del servicio es FIJA (settings.ML_SERVICE_URL). Nunca se arma con
  datos del usuario, así no se puede usar el sistema para hacer peticiones
  a otros servidores (SSRF).
- Cada petición lleva una clave compartida (X-API-Key): el servicio de
  inferencia no queda abierto a cualquiera en Internet.
- La respuesta se valida estrictamente antes de usarla.
"""
import logging
import math
from dataclasses import dataclass

import requests
from django.conf import settings

from .catalogo import ESTILOS, ESTILOS_OBLIGATORIOS

log = logging.getLogger("mtflow.seguridad")
UMBRAL_CONFIANZA = 0.60  # Exigencia mínima confirmada; no rebajable por entorno.


class ServicioMLNoDisponible(Exception):
    """El servicio no respondió o respondió algo inválido."""


@dataclass
class ResultadoClasificacion:
    confianzas: dict[str, float]   # código -> probabilidad, suma ≤ 1
    estilo_sugerido: str
    confianza_maxima: float
    version_modelo: str
    umbral_confianza: float = UMBRAL_CONFIANZA
    ood: dict | None = None
    motivo_abstencion: str | None = None

    def ordenadas(self):
        return sorted(self.confianzas.items(), key=lambda kv: kv[1], reverse=True)


def _validar_respuesta(datos) -> ResultadoClasificacion:
    if not isinstance(datos, dict) or not isinstance(datos.get("confianzas"), dict):
        raise ServicioMLNoDisponible("Respuesta sin confianzas")
    confianzas = datos["confianzas"]
    claves = set(confianzas)
    if not claves <= set(ESTILOS) or not ESTILOS_OBLIGATORIOS <= claves:
        raise ServicioMLNoDisponible("Los estilos de la respuesta no calzan con el catálogo")
    limpias = {}
    for codigo, valor in confianzas.items():
        if not isinstance(valor, (int, float)) or isinstance(valor, bool) or math.isnan(valor):
            raise ServicioMLNoDisponible("Confianza no numérica")
        if not 0.0 <= valor <= 1.0:
            raise ServicioMLNoDisponible("Confianza fuera de [0,1]")
        limpias[codigo] = float(valor)
    total = sum(limpias.values())
    # Suman 1, o menos si Roboflow omitió las clases bajo su umbral (0,4).
    if total <= 0 or total > 1.01:
        raise ServicioMLNoDisponible("Las confianzas no suman entre 0 y 1")
    # E-99 no tiene probabilidad aprendida en el modelo local. Incluso al leer
    # una respuesta antigua se decide exclusivamente sobre las siete clases.
    ganador = max(sorted(ESTILOS_OBLIGATORIOS), key=limpias.get)
    maxima = limpias[ganador]
    version = datos.get("version_modelo", "desconocida")
    if not isinstance(version, str) or not version or len(version) > 120:
        raise ServicioMLNoDisponible("Versión del modelo inválida")
    ood = datos.get("ood")
    if ":ood:" in version and ood is None:
        raise ServicioMLNoDisponible("Falta el análisis OOD declarado por el modelo")
    fuera = False
    if ood is not None:
        if not isinstance(ood, dict) or set(ood) != {"version", "distancia", "umbral", "fuera_distribucion"}:
            raise ServicioMLNoDisponible("Metadatos OOD inválidos")
        for campo in ("distancia", "umbral"):
            valor = ood[campo]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not 0 <= valor <= 2:
                raise ServicioMLNoDisponible("Puntuación OOD inválida")
        identificador = ood["version"]
        if (not isinstance(identificador, str) or len(identificador) != 64
                or any(c not in "0123456789abcdef" for c in identificador)
                or not version.endswith(":ood:" + identificador[:16])
                or type(ood["fuera_distribucion"]) is not bool
                or ood["fuera_distribucion"] != (ood["distancia"] > ood["umbral"])):
            raise ServicioMLNoDisponible("Decisión OOD inconsistente")
        fuera = ood["fuera_distribucion"]
    motivo = "fuera_distribucion" if fuera else "confianza_insuficiente" if maxima < UMBRAL_CONFIANZA else None
    if (ood is not None or "motivo_abstencion" in datos) and datos.get("motivo_abstencion") != motivo:
        raise ServicioMLNoDisponible("El motivo de abstención no coincide con el análisis")
    estilo = ganador if motivo is None else "E-99"
    # Los metadatos nuevos deben coincidir con el vector. Las respuestas antiguas
    # de dos campos se aceptan aplicando igualmente la regla del 60 % en Django.
    if "estilo_sugerido" in datos and datos["estilo_sugerido"] != estilo:
        raise ServicioMLNoDisponible("La categoría no coincide con el análisis OOD y la exigencia del 60 %")
    if "umbral_confianza" in datos and (
        isinstance(datos["umbral_confianza"], bool) or datos["umbral_confianza"] != UMBRAL_CONFIANZA
    ):
        raise ServicioMLNoDisponible("El servicio no aplica la exigencia del 60 %")
    if "confianza_maxima" in datos:
        declarada = datos["confianza_maxima"]
        if (isinstance(declarada, bool) or not isinstance(declarada, (int, float))
                or not math.isfinite(declarada) or not math.isclose(declarada, maxima, abs_tol=1e-9)):
            raise ServicioMLNoDisponible("La confianza máxima no coincide con el vector")
    return ResultadoClasificacion(limpias, estilo, maxima, version, ood=ood, motivo_abstencion=motivo)


def clasificar(contenido: bytes, nombre: str, tipo: str) -> ResultadoClasificacion:
    url = settings.ML_SERVICE_URL.rstrip("/") + "/clasificar"
    try:
        r = requests.post(
            url,
            files={"imagen": (nombre, contenido, tipo)},
            headers={"X-API-Key": settings.ML_SERVICE_API_KEY},
            timeout=settings.ML_SERVICE_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as e:
        log.error("Servicio ML no responde: %s", type(e).__name__)
        raise ServicioMLNoDisponible("Sin conexión") from e
    if r.status_code != 200:
        log.error("Servicio ML respondió %s", r.status_code)
        raise ServicioMLNoDisponible(f"HTTP {r.status_code}")
    try:
        datos = r.json()
    except ValueError as e:
        raise ServicioMLNoDisponible("Respuesta no es JSON") from e
    return _validar_respuesta(datos)

"""
Servicio de inferencia de MTFlow (ADR-0002).

Contrato:
  GET  /salud       -> {"estado": "ok", "version_modelo": "..."}
  POST /clasificar  (multipart, campo "imagen", cabecera X-API-Key)
                    -> versión, siete confianzas del modelo local, estilo sugerido
                       (E-01…E-07 o E-99), confianza máxima y umbral fijo de 0.60

Este servicio NO está pensado para recibir tráfico del público: solo lo
llama el backend Django, con una clave compartida. Igualmente vuelve a
validar la imagen (defensa en profundidad).
"""
import io
import logging
import secrets
import threading
import warnings
from contextlib import closing

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from . import config
from .predictor import PredictorNoDisponible, cargar_predictor
from .decision import construir_respuesta

# Mensajes del servicio visibles en la terminal de uvicorn (motivo de cada 503)
log = logging.getLogger("mtflow.ml")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     [mtflow.ml] %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False

app = FastAPI(title="MTFlow · servicio de inferencia", docs_url=None, redoc_url=None, openapi_url=None)
predictor = cargar_predictor()
# El cupo abarca lectura, decodificación e inferencia; el lock del predictor
# por sí solo dejaba acumular fotos ya decodificadas mientras esperaban turno.
cupo_imagen = threading.BoundedSemaphore(1)


def verificar_clave(x_api_key: str = Header(default="")):
    if not config.API_KEY or not secrets.compare_digest(x_api_key, config.API_KEY):
        raise HTTPException(status_code=401, detail="No autorizado")


@app.get("/salud")
def salud():
    return {"estado": "ok", "version_modelo": predictor.version,
            "umbral_confianza": config.UMBRAL_CONFIANZA,
            "ood_activo": getattr(predictor, "detector_ood", None) is not None}


def procesar_imagen(datos):
    """Decodifica una vez y libera los píxeles al terminar, también si falla."""
    Image.MAX_IMAGE_PIXELS = config.MAX_PIXELES
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with closing(Image.open(io.BytesIO(datos))) as img:
                if img.format not in ("JPEG", "PNG") or getattr(img, "is_animated", False):
                    raise HTTPException(status_code=415, detail="Solo JPG o PNG estáticos")
                if img.width * img.height > config.MAX_PIXELES:
                    raise HTTPException(status_code=413, detail="La imagen tiene demasiados píxeles")
                img.load()
                try:
                    ood = None
                    if hasattr(predictor, "analizar_imagen"):
                        confianzas, ood = predictor.analizar_imagen(img, datos)
                    elif hasattr(predictor, "analizar_bytes"):
                        confianzas, ood = predictor.analizar_bytes(datos)
                    elif hasattr(predictor, "predecir_bytes"):
                        confianzas = predictor.predecir_bytes(datos)
                    else:
                        confianzas = predictor.predecir(img)
                    return construir_respuesta(predictor.version, confianzas, ood)
                except PredictorNoDisponible as e:
                    log.warning("clasificar -> 503: %s", e)
                    raise HTTPException(status_code=503, detail="Modelo no disponible") from e
    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=413, detail="La imagen tiene demasiados píxeles")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise HTTPException(status_code=422, detail="Imagen no válida")


@app.post("/clasificar", dependencies=[Depends(verificar_clave)])
async def clasificar(imagen: UploadFile = File(...)):
    if not cupo_imagen.acquire(blocking=False):
        await imagen.close()
        raise HTTPException(status_code=503, detail="El análisis está ocupado. Reintenta en unos segundos.",
                            headers={"Retry-After": "3"})
    try:
        datos = await imagen.read(config.MAX_BYTES + 1)
        if not datos or len(datos) > config.MAX_BYTES:
            raise HTTPException(status_code=413, detail="Tamaño no permitido")
        if not (datos.startswith(b"\xff\xd8\xff") or datos.startswith(b"\x89PNG\r\n\x1a\n")):
            raise HTTPException(status_code=415, detail="Solo JPG o PNG")
        # La decodificación también se ejecuta fuera del bucle de FastAPI,
        # para que /salud pueda responder durante el procesamiento.
        return await run_in_threadpool(procesar_imagen, datos)
    finally:
        try:
            await imagen.close()
        finally:
            cupo_imagen.release()

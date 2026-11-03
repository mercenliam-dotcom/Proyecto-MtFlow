"""
Servicio de inferencia de MTFlow (ADR-0002).

Contrato:
  GET  /salud       -> {"estado": "ok", "version_modelo": "..."}
  POST /clasificar  (multipart, campo "imagen", cabecera X-API-Key)
                    -> {"version_modelo": "...", "confianzas": {"E-01": 0.1, ...}}

Este servicio NO está pensado para recibir tráfico del público: solo lo
llama el backend Django, con una clave compartida. Igualmente vuelve a
validar la imagen (defensa en profundidad).
"""
import io
import secrets
import warnings

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from . import config
from .predictor import cargar_predictor

app = FastAPI(title="MTFlow · servicio de inferencia", docs_url=None, redoc_url=None, openapi_url=None)
predictor = cargar_predictor()


def verificar_clave(x_api_key: str = Header(default="")):
    if not config.API_KEY or not secrets.compare_digest(x_api_key, config.API_KEY):
        raise HTTPException(status_code=401, detail="No autorizado")


@app.get("/salud")
def salud():
    return {"estado": "ok", "version_modelo": predictor.version}


@app.post("/clasificar", dependencies=[Depends(verificar_clave)])
async def clasificar(imagen: UploadFile = File(...)):
    datos = await imagen.read(config.MAX_BYTES + 1)
    if not datos or len(datos) > config.MAX_BYTES:
        raise HTTPException(status_code=413, detail="Tamaño no permitido")
    if not (datos.startswith(b"\xff\xd8\xff") or datos.startswith(b"\x89PNG\r\n\x1a\n")):
        raise HTTPException(status_code=415, detail="Solo JPG o PNG")
    Image.MAX_IMAGE_PIXELS = config.MAX_PIXELES
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(datos))
            if img.format not in ("JPEG", "PNG") or getattr(img, "is_animated", False):
                raise HTTPException(status_code=415, detail="Solo JPG o PNG estáticos")
            img.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=422, detail="Imagen no válida")
    return {"version_modelo": predictor.version, "confianzas": predictor.predecir(img)}

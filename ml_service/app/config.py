import os
from pathlib import Path


def _cargar_env(ruta: Path) -> None:
    """Carga ml_service/.env (CLAVE=valor) sin pisar variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(Path(__file__).resolve().parent.parent / ".env")

# Clave que Django debe enviar en X-API-Key (la misma de config/.env)
API_KEY = os.environ.get("ML_SERVICE_API_KEY", "")
MAX_BYTES = int(os.environ.get("ML_MAX_BYTES", str(5 * 1024 * 1024)))
MAX_PIXELES = 40_000_000

# ---------------------------------------------------------------------------
# Qué predictor usar
# ---------------------------------------------------------------------------
#   roboflow -> modelo entrenado en Roboflow (ResNet18), consultado por su API
#   local    -> pesos propios en MODELO_RUTA (EfficientNet-B0)
#   simulado -> resultados falsos y deterministas, para desarrollar sin modelo
#   auto     -> roboflow si hay ROBOFLOW_API_KEY; si no, local si existen los
#               pesos; si no, simulado
MODO_PREDICTOR = os.environ.get("ML_PREDICTOR", "auto").lower()
FORZAR_STUB = os.environ.get("ML_FORZAR_STUB", "0") == "1"  # compatibilidad
MODELO_RUTA = os.environ.get("MODELO_RUTA", "modelos/efficientnet_b0_mtflow.pt")

# ---------------------------------------------------------------------------
# Roboflow
# ---------------------------------------------------------------------------
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")
ROBOFLOW_API_URL = os.environ.get("ROBOFLOW_API_URL", "https://serverless.roboflow.com")
ROBOFLOW_MODEL_ID = os.environ.get(
    "ROBOFLOW_MODEL_ID", "martin-stgmar-gmail-com/tattoo-styles-2-resnet18-t1"
)
ROBOFLOW_TIMEOUT = float(os.environ.get("ROBOFLOW_TIMEOUT", "15"))
# La imagen se reduce antes de enviarla: el modelo trabaja a 224x224, así que
# mandar más píxeles solo agrega demora y comparte más datos de los necesarios.
ROBOFLOW_LADO_MAX = int(os.environ.get("ROBOFLOW_LADO_MAX", "640"))

# ---------------------------------------------------------------------------
# Catálogo: código interno <- nombre de la clase en el modelo de Roboflow
# ---------------------------------------------------------------------------
# Los códigos son los que guarda y muestra Django. Si se agrega o renombra una
# clase en Roboflow, hay que actualizar este diccionario Y el catálogo de
# Django (config/apps/clasificacion/catalogo.py). Una clase desconocida hace
# que la respuesta se rechace: nunca se adivina.
CLASES_ROBOFLOW = {
    "Alto contraste": "E-01",
    "Anime": "E-02",
    "Cibersigilismo": "E-03",
    "Lettering": "E-04",
    "Linea Fina": "E-05",
    "Ornamentos": "E-06",
    "Tribal-Neotribal": "E-07",
    # Si el dataset incorpora una clase de descarte ("Otros", "No tatuaje"),
    # se mapea aquí a "E-99".
}

# Orden de salida del predictor local/simulado.
CLASES = ["E-01", "E-02", "E-03", "E-04", "E-05", "E-06", "E-07", "E-99"]

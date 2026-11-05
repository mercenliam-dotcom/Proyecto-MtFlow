import os
from pathlib import Path


def _cargar_env(ruta: Path) -> None:
    """Carga ml_service/.env (CLAVE=valor) sin pisar variables ya definidas."""
    if not ruta.exists():
        return
    # utf-8-sig tolera el BOM que agrega el Bloc de notas de Windows
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


BASE_DIR = Path(__file__).resolve().parent.parent
_cargar_env(BASE_DIR / ".env")

# Clave que Django debe enviar en X-API-Key (la misma de config/.env)
API_KEY = os.environ.get("ML_SERVICE_API_KEY", "")
MAX_BYTES = int(os.environ.get("ML_MAX_BYTES", str(5 * 1024 * 1024)))
MAX_PIXELES = 40_000_000

# ---------------------------------------------------------------------------
# Qué predictor usar
# ---------------------------------------------------------------------------
#   roboflow_workflow -> Roboflow Workflow "tattoo-styles-vtattoo-styles-2-resnet18-t1-logic"
#   roboflow_modelo   -> endpoint directo del modelo en Roboflow (alias: roboflow)
#   local    -> bundle TensorFlow/Keras v1 en MTFLOW_MODEL_DIR (siete clases)
#   local_pytorch -> adaptador histórico para MODELO_RUTA (.pt, ocho salidas)
#   simulado -> resultados falsos y deterministas, para desarrollar sin modelo
#   auto     -> roboflow_workflow si hay ROBOFLOW_API_KEY; si no, local si existen los
#               pesos; si no, simulado
MODO_PREDICTOR = os.environ.get("ML_PREDICTOR", "auto").lower()
FORZAR_STUB = os.environ.get("ML_FORZAR_STUB", "0") == "1"  # compatibilidad
MODELO_RUTA = os.environ.get("MODELO_RUTA", "modelos/efficientnet_b0_mtflow.pt")
MTFLOW_MODEL_DIR = Path(os.environ.get("MTFLOW_MODEL_DIR", "modelos/efficientnet_b0_v1"))
if not MTFLOW_MODEL_DIR.is_absolute():
    MTFLOW_MODEL_DIR = BASE_DIR / MTFLOW_MODEL_DIR

# Política confirmada: un valor menor no se acepta como categoría automática.
# No se permite rebajar esta exigencia mediante variables de entorno.
UMBRAL_CONFIANZA = 0.60

# ---------------------------------------------------------------------------
# Roboflow
# ---------------------------------------------------------------------------
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")
ROBOFLOW_API_URL = os.environ.get("ROBOFLOW_API_URL", "https://serverless.roboflow.com")
ROBOFLOW_MODEL_ID = os.environ.get(
    "ROBOFLOW_MODEL_ID", "martin-stgmar-gmail-com/tattoo-styles-2-resnet18-t1"
)
ROBOFLOW_WORKSPACE = os.environ.get("ROBOFLOW_WORKSPACE", "martin-stgmar-gmail-com")
ROBOFLOW_WORKFLOW_ID = os.environ.get(
    "ROBOFLOW_WORKFLOW_ID", "tattoo-styles-vtattoo-styles-2-resnet18-t1-logic"
)
ROBOFLOW_TIMEOUT = float(os.environ.get("ROBOFLOW_TIMEOUT", "15"))
ROBOFLOW_REINTENTOS = int(os.environ.get("ROBOFLOW_REINTENTOS", "2"))
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
    # Español (dataset v3)
    "Alto contraste": "E-01",
    "Anime": "E-02",
    "Cibersigilismo": "E-03",
    "Lettering": "E-04",
    "Linea Fina": "E-05",
    "Ornamentos": "E-06",
    "Tribal-Neotribal": "E-07",
    # Inglés (modelo tattoo-styles-2)
    "High Contrast": "E-01",
    "Blackwork": "E-01",
    "Cybersigilism": "E-03",
    "Fine Line": "E-05",
    "Fineline": "E-05",
    "Ornamental": "E-06",
    "Neotribal": "E-07",
    "Tribal": "E-07",
}

# Orden de salida del predictor local/simulado.
CLASES = ["E-01", "E-02", "E-03", "E-04", "E-05", "E-06", "E-07", "E-99"]

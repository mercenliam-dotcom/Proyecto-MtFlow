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
MAX_BYTES = int(os.environ.get("ML_MAX_BYTES", str(10 * 1024 * 1024)))
MAX_PIXELES = 40_000_000

# Único backend admitido. Sin API externa ni sustitución por simulación.
MODO_PREDICTOR = os.environ.get("ML_PREDICTOR", "local").strip().lower()
MTFLOW_MODEL_DIR = Path(os.environ.get("MTFLOW_MODEL_DIR", "modelos/efficientnet_b0_v3"))
if not MTFLOW_MODEL_DIR.is_absolute():
    MTFLOW_MODEL_DIR = BASE_DIR / MTFLOW_MODEL_DIR
UMBRAL_CONFIANZA = 0.60

# Activado por defecto en esta rama. Desactivación explícita para comparar el baseline.
OOD_ACTIVO = os.environ.get("MTFLOW_OOD_ENABLED", "1").lower() in ("1", "true", "si", "yes")
OOD_CALIBRACION = Path(os.environ.get("MTFLOW_OOD_CALIBRATION", "modelos/efficientnet_b0_v3/ood/calibracion_ood_v3.json"))
if not OOD_CALIBRACION.is_absolute():
    OOD_CALIBRACION = BASE_DIR / OOD_CALIBRACION

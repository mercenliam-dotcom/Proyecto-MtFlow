import os

API_KEY = os.environ.get("ML_SERVICE_API_KEY", "")
# Ruta a los pesos entrenados. Si no existe, el servicio usa el predictor
# simulado (stub) para que la web pueda desarrollarse sin el modelo.
MODELO_RUTA = os.environ.get("MODELO_RUTA", "modelos/efficientnet_b0_mtflow.pt")
FORZAR_STUB = os.environ.get("ML_FORZAR_STUB", "0") == "1"
MAX_BYTES = int(os.environ.get("ML_MAX_BYTES", str(5 * 1024 * 1024)))
MAX_PIXELES = 40_000_000

# Orden de las clases = orden de las neuronas de salida del modelo.
# DEBE coincidir con el orden usado en el entrenamiento (ImageFolder ordena
# alfabéticamente las carpetas: E-01 … E-06, E-99).
CLASES = ["E-01", "E-02", "E-03", "E-04", "E-05", "E-06", "E-99"]

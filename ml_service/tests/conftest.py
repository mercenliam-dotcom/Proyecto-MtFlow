"""Variables de entorno de prueba, definidas ANTES de importar la app."""
import os

os.environ["ML_SERVICE_API_KEY"] = "clave-de-prueba"
os.environ["ML_FORZAR_STUB"] = "1"
os.environ.pop("ROBOFLOW_API_KEY", None)

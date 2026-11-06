"""Doble exclusivamente de pruebas: nunca seleccionable mediante entorno."""
import os
from types import SimpleNamespace
from unittest.mock import patch
os.environ["ML_SERVICE_API_KEY"] = "clave-de-prueba"
os.environ["ML_PREDICTOR"] = "local"
doble = SimpleNamespace(version="efficientnet_b0:v2:test", predecir_bytes=lambda datos:
    {f"E-{i:02}": (.7 if i == 1 else .05) for i in range(1, 8)})
with patch("app.predictor.cargar_predictor", return_value=doble):
    from app import main

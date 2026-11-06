# Ejecución local de EfficientNetB0 v2

La clasificación usa exclusivamente el bundle Keras incluido. Se retiraron los conectores, ajustes y pruebas de llamadas a Roboflow, el adaptador PyTorch y la simulación seleccionable por configuración. Las referencias al origen del dataset y los registros históricos se conservan como trazabilidad, sin conexiones externas.

## En este computador: dos terminales de Git Bash

Desde la carpeta del escritorio `Proyecto mtFlow`:

Terminal Django:
```bash
source .venv/Scripts/activate
cd config
python manage.py runserver 127.0.0.1:8000
```

Terminal EfficientNet:
```bash
source .venv-ml/Scripts/activate
cd ml_service
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

El entorno `.venv-ml` usa Python 3.12 y las versiones TensorFlow 2.21.0 / Keras 3.13.2 declaradas por el entrenamiento. En otra máquina se crea con Python 3.12 y se instalan `ml_service/requirements.txt` y `ml_service/requirements-modelo.txt`. No se deben sobrescribir los `.env` existentes.

`ml_service/.env` usa `ML_PREDICTOR=local` y `MTFLOW_MODEL_DIR=modelos/efficientnet_b0_v2`. La clave `ML_SERVICE_API_KEY` coincide con la de Django; protege la conexión local y no pertenece a un proveedor externo.

## Comprobación

`http://127.0.0.1:8001/salud` debe informar `efficientnet_b0:v2:` seguido de la huella del modelo y umbral `0.6`. La prueba real de carga e inferencia es `python scripts/verificar_efficientnet_local.py` desde la raíz usando `.venv-ml`.

Se conservan siete probabilidades, orientación EXIF, RGB de 224×224 y el preprocesamiento del entrenamiento. No se divide por 255 fuera del modelo. E-99 es abstención bajo 60 %, no una clase entrenada. Si faltan pesos o son inválidos, el servicio falla de forma explícita. Django puede conservar la solicitud e imagen indicando ML no disponible.

Los documentos ADR anteriores describen decisiones históricas. Esta decisión los sustituye para la ejecución actual. Las predicciones antiguas no se recalculan ni se borran; su versión original sigue visible al equipo.

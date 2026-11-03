# MtFlow

Sistema web para Maldita Ternura Estudio. Identifica el estilo de una imagen de referencia de tatuaje y **recomienda** (no decide) si la solicitud calza con el estudio.

## Qué hay en el repositorio

| Carpeta | Qué es |
|---|---|
| `config/` | Proyecto Django (aquí está `manage.py`) |
| `config/web/` | Sitio **público**: portafolio, horarios, cotización |
| `config/apps/cuentas/` | Cuentas del equipo con rol Administrador / Usuario. **Sin registro público** |
| `config/apps/nucleo/` | Seguridad común: validación de imágenes, enlaces firmados, cabeceras, errores |
| `config/apps/clasificacion/` | Pantalla "Identificar estilo" que consulta al servicio de inferencia |
| `ml_service/` | Servicio de inferencia (FastAPI). Programa aparte que recibe una imagen y devuelve el % de cada estilo |
| `docs/` | Matriz de seguridad y decisiones (ADR) |

## Cómo se conectan las piezas

```
Navegador ──► Django (puerto 8000) ──► FastAPI (puerto 8001) ──► Roboflow Workflow
              valida y limpia la         traduce las 7 clases        "Tattoo styles …-t1 Logic"
              imagen, decide Apto /      del modelo a E-01…E-07      (modelo ResNet18)
              En evaluación / No
              recomendado y lo muestra
```

Hay **dos claves distintas**:

| Clave | Qué es | Dónde va |
|---|---|---|
| `ML_SERVICE_API_KEY` | Contraseña que inventan ustedes, para que FastAPI solo le responda a Django | Igual en `config/.env` y en `ml_service/.env` |
| `ROBOFLOW_API_KEY` | Clave privada de la cuenta de Roboflow (Settings → API Keys) | Solo en `ml_service/.env` |

Sin `ROBOFLOW_API_KEY` el servicio usa resultados simulados, así la web se puede probar sin conexión. Detalles y riesgos en `docs/decisiones/ADR-0009-modelo-roboflow.md`.

## Puesta en marcha (Windows, Git Bash)

Terminal 1, la web:

```bash
cd ~/OneDrive/Escritorio/"Proyecto mtFlow"
source .venv/Scripts/activate        # aparece (.venv) al inicio de la línea
pip install -r requirements.txt

cd config
cp .env.example .env
# Abrir config/.env y completar:
#   DJANGO_SECRET_KEY  -> generar con: python -c "import secrets; print(secrets.token_urlsafe(64))"
#   ML_SERVICE_API_KEY -> cualquier texto largo (el mismo que en ml_service/.env)
# Sin DATABASE_URL se usa SQLite local. Para PostgreSQL: docker compose up -d
# y descomentar DATABASE_URL.

python manage.py migrate
python manage.py createsuperuser    # crea el primer ADMINISTRADOR
python manage.py test               # deben pasar todas
python manage.py runserver          # http://127.0.0.1:8000
```

Terminal 2, el servicio de inferencia:

```bash
cd ~/OneDrive/Escritorio/"Proyecto mtFlow"
source .venv/Scripts/activate
cd ml_service
pip install -r requirements.txt
cp .env.example .env    # completar ML_SERVICE_API_KEY y ROBOFLOW_API_KEY
uvicorn app.main:app --port 8001
```

Para ver qué modelo quedó activo, abre http://127.0.0.1:8001/salud. Debe decir `roboflow-workflow:martin-stgmar-gmail-com/tattoo-styles-vtattoo-styles-2-resnet18-t1-logic`, o `simulado-0.2` si no hay clave.

### Probar la conexión real con Roboflow (smoke test)

```bash
cd ml_service
pip install pytest httpx
ROBOFLOW_SMOKE=1 python -m pytest tests/test_smoke_roboflow.py -s
# con una foto propia:
ROBOFLOW_SMOKE=1 ROBOFLOW_SMOKE_IMAGEN=ruta/foto.jpg python -m pytest tests/test_smoke_roboflow.py -s
```

Llama al workflow real (consume créditos de Roboflow) y comprueba que devuelve la salida `predictions` con clases conocidas. Las demás pruebas (`python -m pytest`) nunca salen a internet.

En PowerShell: `.\.venv\Scripts\Activate.ps1` en vez de `source ...` y `copy` en vez de `cp`.

## Rutas

| Ruta | Quién |
|---|---|
| `/`, `/horarios/`, `/cotizacion/` | Público |
| `/cuentas/ingresar/` | Equipo (enlace "Acceso del equipo" en el menú) |
| `/panel/` | Inicio del área privada |
| `/clasificacion/probar/` | Equipo: subir imagen y ver el estilo sugerido |
| `/cuentas/` | **Solo administradores**: crear, editar, desactivar cuentas |

## Integración con Roboflow

El cliente está en `ml_service/app/roboflow_workflow.py`. La función `clasificar_tatuaje(imagen, cfg)` hace esto:

- `POST https://serverless.roboflow.com/martin-stgmar-gmail-com/workflows/tattoo-styles-vtattoo-styles-2-resnet18-t1-logic`
- Envía la entrada `image` en base64. El workflow no declara parámetros, así que no se envía ninguno.
- La API key va en `Authorization: Bearer`, leída de `ROBOFLOW_API_KEY`; nunca en la URL ni en el cuerpo.
- Usa un timeout de 15 s y 2 reintentos con espera creciente cuando hay cortes de red, HTTP 429 o 5xx.
- Ante cualquier falla lanza errores con tipo: `RoboflowAutenticacionError` (401/403), `RoboflowNoEncontradoError` (404), `RoboflowLimiteError` (429), `RoboflowNoDisponibleError` y `RoboflowRespuestaInvalidaError`.
- Lee solo la salida `predictions` (clase y confianza). No hay salidas de imagen.

El bloque del modelo usa un umbral de confianza de 0,4. Si Roboflow omite las clases bajo ese umbral, las confianzas suman menos de 1 y **no se re-escalan**, para no inflar el porcentaje.

`ML_PREDICTOR` en `ml_service/.env` puede ser `roboflow_workflow` (por defecto con clave), `roboflow_modelo` (endpoint directo del modelo), `local`, `simulado` o `auto`. Si cambian las clases en Roboflow, hay que actualizar `CLASES_ROBOFLOW` en `ml_service/app/config.py` y `ESTILOS` en `config/apps/clasificacion/catalogo.py`.

Para usar pesos propios en vez de Roboflow: dejar los pesos entrenados en `ml_service/modelos/efficientnet_b0_mtflow.pt` (un `state_dict` de `torchvision.models.efficientnet_b0` con 8 salidas en orden E-01…E-07, E-99) e instalar `ml_service/requirements-modelo.txt`. El servicio los detecta al arrancar; Django no cambia. Los nombres de los estilos se cambian en `config/apps/clasificacion/catalogo.py`.

## Producción

`DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (PostgreSQL/Supabase, obligatoria), `DB_SSLMODE=require`, `DJANGO_ADMIN_URL`. Con `DEBUG=0` se activan solos HTTPS, HSTS y cookies seguras. `python manage.py check --deploy` lo verifica.

## Pruebas automáticas (CI)

El flujo está listo en `docs/ci/ci.yml`. Para activarlo ver `docs/ci/LEEME.md`.

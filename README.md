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
Navegador ──► Django (puerto 8000) ──► FastAPI (puerto 8001) ──► API de Roboflow
              valida y limpia la         traduce las 7 clases        modelo ResNet18
              imagen, decide Apto /      del modelo a E-01…E-07      "Tattoo styles"
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

Para ver qué modelo quedó activo, abre http://127.0.0.1:8001/salud. Debe decir `roboflow:martin-stgmar-gmail-com/...`, o `simulado-0.2` si no hay clave.

En PowerShell: `.\.venv\Scripts\Activate.ps1` en vez de `source ...` y `copy` en vez de `cp`.

## Rutas

| Ruta | Quién |
|---|---|
| `/`, `/horarios/`, `/cotizacion/` | Público |
| `/cuentas/ingresar/` | Equipo (enlace "Acceso del equipo" en el menú) |
| `/panel/` | Inicio del área privada |
| `/clasificacion/probar/` | Equipo: subir imagen y ver el estilo sugerido |
| `/cuentas/` | **Solo administradores**: crear, editar, desactivar cuentas |

## Cambiar de modelo

`ML_PREDICTOR` en `ml_service/.env`: `roboflow`, `local`, `simulado` o `auto`. Si cambian las clases en Roboflow, actualizar `CLASES_ROBOFLOW` en `ml_service/app/config.py` y `ESTILOS` en `config/apps/clasificacion/catalogo.py`.

Para usar pesos propios en vez de Roboflow: dejar los pesos entrenados en `ml_service/modelos/efficientnet_b0_mtflow.pt` (un `state_dict` de `torchvision.models.efficientnet_b0` con 8 salidas en orden E-01…E-07, E-99) e instalar `ml_service/requirements-modelo.txt`. El servicio los detecta al arrancar; Django no cambia. Los nombres de los estilos se cambian en `config/apps/clasificacion/catalogo.py`.

## Producción

`DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (PostgreSQL/Supabase, obligatoria), `DB_SSLMODE=require`, `DJANGO_ADMIN_URL`. Con `DEBUG=0` se activan solos HTTPS, HSTS y cookies seguras. `python manage.py check --deploy` lo verifica.

## Pruebas automáticas (CI)

El flujo está listo en `docs/ci/ci.yml`. Para activarlo ver `docs/ci/LEEME.md`.

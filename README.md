# MtFlow

Rama de pruebas con EfficientNetB0 v2. El bundle del modelo viene incluido al clonar la rama.
Incluye recepción persistente, cuentas del equipo, bandejas privadas y clasificación
inmediata mediante EfficientNetB0 local, con umbral del 60 % y respuesta JSON.
Consulta el [estado de los módulos y los cambios de esta entrega](docs/estado-modulos.md).
La agenda operativa y el despliegue público siguen pendientes.

Sistema web para Maldita Ternura Estudio. Identifica el estilo de una imagen de referencia de tatuaje y **recomienda** (no decide) si la solicitud calza con el estudio.

## Qué hay en el repositorio

| Carpeta | Qué es |
|---|---|
| `config/` | Proyecto Django (aquí está `manage.py`) |
| `config/web/` | Sitio **público**: portafolio, horarios, cotización |
| `config/apps/cuentas/` | Cuentas del equipo (Administrador / Usuario) y portal separado de clientes con registro público limitado |
| `config/apps/nucleo/` | Seguridad común: validación de imágenes, enlaces firmados, cabeceras, errores |
| `config/apps/clasificacion/` | Pantalla "Identificar estilo" que consulta al servicio de inferencia |
| `ml_service/` | Servicio de inferencia (FastAPI). Programa aparte que recibe una imagen y devuelve el % de cada estilo |
| `docs/` | Matriz de seguridad y decisiones (ADR) |

## Cómo se conectan las piezas

```
Navegador ──► Django (8000) ──► FastAPI (8001) ──► EfficientNetB0 Keras local
                 │                 │                     siete probabilidades
                 │                 └── JSON: estilo o E-99, confianza, umbral 0.60
                 └── valida el JSON y guarda propuesta, imagen y predicción en BD
```

La conexión Django→FastAPI utiliza una clave compartida. Roboflow queda como alternativa explícita:

| Clave | Qué es | Dónde va |
|---|---|---|
| `ML_SERVICE_API_KEY` | Contraseña que inventan ustedes, para que FastAPI solo le responda a Django | Igual en `config/.env` y en `ml_service/.env` |
| `ROBOFLOW_API_KEY` | Clave privada de la cuenta de Roboflow (Settings → API Keys) | Solo en `ml_service/.env` |

El modo principal es `ML_PREDICTOR=local`: requiere el bundle Keras y no utiliza Roboflow. Si falta o no coincide su SHA-256, no se sustituye silenciosamente por resultados simulados. Para pruebas ficticias seleccionar `simulado` expresamente. Consulta [integración local y contrato JSON](docs/modelo-local-fastapi.md).

## Puesta en marcha (Windows, Git Bash)

Instalar Python 3.12 y clonar la rama:

```bash
git clone --depth 1 --single-branch --branch pruebas-modelo-v2-con-pesos https://github.com/mercenliam-dotcom/Proyecto-MtFlow.git
cd Proyecto-MtFlow
python -m venv .venv
```

Terminal 1, la web:

```bash
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
# El administrador de demostración requiere además ADMIN_DESARROLLO_HABILITADO=1.
# En producción la cuenta predeterminada se elimina y el administrador se crea
# de forma segura con: python manage.py createsuperuser
python manage.py test               # deben pasar todas
python manage.py runserver          # http://127.0.0.1:8000
```

Terminal 2, el servicio de inferencia, desde la raíz del repositorio:

```bash
source .venv/Scripts/activate
cd ml_service
python -m pip install -r requirements.txt -r requirements-modelo.txt
cp .env.example .env    # usar la misma ML_SERVICE_API_KEY de config/.env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Abre http://127.0.0.1:8001/salud y comprueba que muestre `efficientnet_b0:v2:<SHA-256>` y `umbral_confianza: 0.6`. En Django, inicia sesión y sube un JPG o PNG en `/clasificacion/probar/`.

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

El bloque del modelo usa un umbral de confianza de 0,4, y Roboflow **solo informa las clases que lo superan**. Así se comprobó con la API real: una respuesta trajo únicamente `{"Linea Fina": 0.4182}`. Por eso:
- las confianzas suman menos de 1 y **no se re-escalan**, para no inflar el porcentaje; la web muestra "< 40 %" en los estilos no informados;
- si ninguna clase supera 0,4, la lista llega vacía y se interpreta como **fuera de catálogo (E-99)** → "No recomendado". No es un error.

Para tener las 7 confianzas completas, el workflow tendría que exponer el parámetro `confidence` (o fijarlo en 0) en Roboflow.

`ML_PREDICTOR=local` es la configuración principal del ejemplo. Las alternativas son `roboflow_workflow`, `roboflow_modelo`, `local_pytorch`, `simulado` y `auto`. En `auto` se conserva la prioridad de una clave Roboflow; para asegurar inferencia local usar explícitamente `local`. El umbral de decisión del sistema es 60 % también al usar conectores alternativos; el 40 % descrito arriba corresponde exclusivamente a la salida del workflow histórico.

El bundle incluido es `ml_service/modelos/efficientnet_b0_v2/MTFlow_EfficientNetB0_v2.keras`, acompañado por `training_config.json`, `class_names.json` y `model_sha256.txt`. Su salida contiene E-01…E-07; E-99 se asigna por abstención cuando la mayor confianza es menor a 0.60, sin inventar una octava probabilidad. Los pesos `.pt` del adaptador histórico requieren `ML_PREDICTOR=local_pytorch` y `requirements-pytorch.txt`; no son compatibles con este bundle.

## Producción

La cuenta `admin` / `admin` solo se prepara en desarrollo si se activa explícitamente `ADMIN_DESARROLLO_HABILITADO=1` (desactivado por defecto). Al pasar a `DJANGO_DEBUG=0` se elimina la cuenta marcada de desarrollo; no se reemplazan administradores reales. Consultar [cuenta predeterminada y transición](docs/admin-desarrollo.md).

`DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (PostgreSQL/Supabase, obligatoria), `DB_SSLMODE=require`, `DJANGO_ADMIN_URL`. Con `DEBUG=0` se activan solos HTTPS, HSTS y cookies seguras. `python manage.py check --deploy` lo verifica.

## Pruebas automáticas (CI)

El flujo está listo en `docs/ci/ci.yml`. Para activarlo ver `docs/ci/LEEME.md`.


## Actualización visual y estimador referencial (noviembre 2026)

El sitio y el equipo comparten `config/templates/layout.html` y `config/static/css/design.css`.
En `/cotizacion/` se calcula un rango **ficticio y provisional en CLP**, con análisis de estilo opcional.
La versión actual guarda propuestas, imágenes privadas y el análisis solicitado; no reserva horarios. Las tarifas se ajustan en `config/web/precios.py`.
No requiere Node.js ni dependencias nuevas. Reiniciar Django para cargar los cambios de Python.

Detalles de reglas, seguridad, pruebas y pendientes: [revisión de noviembre](docs/revision-2026-11.md).

**Despliegue tras un proxy:** `CONFIAR_EN_PROXY=1` se configura explícitamente solo si el proxy reescribe los encabezados de origen/protocolo y bloquea el acceso directo al backend. De lo contrario, dejarlo en `0`. En desarrollo local no hace falta cambiarlo.

## Agenda y solicitudes

Ver [integración, funcionamiento y pendientes](docs/integracion-agenda-2026-11-05.md).

## Normalización y validaciones

La revisión de 1FN–3FN, las migraciones, las claves y el DER actualizado están en [normalización y validaciones](docs/normalizacion-y-validaciones.md). Ejecutar `python manage.py migrate` antes de iniciar esta versión. La migración conserva datos y requiere respaldo; no cambiar a código anterior manteniendo una base ya migrada.

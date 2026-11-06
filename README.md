# MtFlow

Rama de pruebas con EfficientNetB0 v2. El bundle del modelo viene incluido al clonar la rama.
Incluye recepción persistente, cuentas del equipo, bandejas privadas y clasificación
inmediata mediante EfficientNetB0 local, con umbral del 60 % y respuesta JSON.
Consulta el [estado de los módulos y los cambios de esta entrega](docs/estado-modulos.md).
La agenda operativa está implementada; el despliegue público sigue pendiente.

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

La conexión Django→FastAPI utiliza `ML_SERVICE_API_KEY`, igual en ambos archivos `.env`.
El único modelo operativo es EfficientNetB0 v2 local. No hay llamadas a proveedores externos ni simulación automática.
Consulta [ejecución local](docs/efficientnet-local.md).

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
py -3.12 -m venv .venv-ml  # solo al crear el entorno por primera vez
source .venv-ml/Scripts/activate
cd ml_service
python -m pip install -r requirements.txt -r requirements-modelo.txt
cp .env.example .env    # usar la misma ML_SERVICE_API_KEY de config/.env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Abre http://127.0.0.1:8001/salud y comprueba que muestre `efficientnet_b0:v2:<SHA-256>` y `umbral_confianza: 0.6`. En Django, inicia sesión y sube un JPG o PNG en `/clasificacion/probar/`.

En PowerShell: `.\.venv\Scripts\Activate.ps1` en vez de `source ...` y `copy` en vez de `cp`.

## Rutas

| Ruta | Quién |
|---|---|
| `/`, `/horarios/`, `/cotizacion/` | Público |
| `/cuentas/ingresar/` | Equipo (enlace "Acceso del equipo" en el menú) |
| `/panel/` | Inicio del área privada |
| `/clasificacion/probar/` | Equipo: subir imagen y ver el estilo sugerido |
| `/cuentas/` | **Solo administradores**: crear, editar, desactivar cuentas |

## Modelo local

El bundle `ml_service/modelos/efficientnet_b0_v2/` contiene los pesos Keras, clases, configuración de entrenamiento y SHA-256. Se verifica antes de cargarlo. Produce siete probabilidades; E-99 indica que ninguna alcanza 60 %. Si falta el modelo, el servicio no arranca con resultados ficticios.

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

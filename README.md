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
Navegador ──► Django (puerto 8000) ──► FastAPI (puerto 8001)
              valida y limpia la         calcula el % de los 7 estilos
              imagen, decide Apto /      (hoy: predictor simulado;
              En evaluación / No         luego: EfficientNet-B0)
              recomendado y lo muestra
```

No se usa ningún servicio externo ni pagado. La `ML_SERVICE_API_KEY` es una contraseña que inventan ustedes y que se escribe igual en los dos programas, para que FastAPI solo le responda a Django.

## Puesta en marcha (Windows, PowerShell)

```powershell
# Desde la carpeta del repositorio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd config
copy .env.example .env
# Abrir config\.env y completar:
#   DJANGO_SECRET_KEY  -> generar con: python -c "import secrets; print(secrets.token_urlsafe(64))"
#   ML_SERVICE_API_KEY -> cualquier texto largo (el mismo del paso del servicio)
# Sin DATABASE_URL se usa SQLite local. Para PostgreSQL: docker compose up -d
# y descomentar DATABASE_URL.

python manage.py migrate
python manage.py createsuperuser    # crea el primer ADMINISTRADOR
python manage.py test               # deben pasar todas
python manage.py runserver          # http://127.0.0.1:8000
```

Servicio de inferencia, en **otra** terminal:

```powershell
cd ml_service
pip install -r requirements.txt
$env:ML_SERVICE_API_KEY="la-misma-clave-del-.env"
uvicorn app.main:app --port 8001
```

## Rutas

| Ruta | Quién |
|---|---|
| `/`, `/horarios/`, `/cotizacion/` | Público |
| `/cuentas/ingresar/` | Equipo (enlace "Acceso del equipo" en el menú) |
| `/panel/` | Inicio del área privada |
| `/clasificacion/probar/` | Equipo: subir imagen y ver el estilo sugerido |
| `/cuentas/` | **Solo administradores**: crear, editar, desactivar cuentas |

## Conectar el modelo real

Dejar los pesos entrenados en `ml_service/modelos/efficientnet_b0_mtflow.pt` (un `state_dict` de `torchvision.models.efficientnet_b0` con 7 salidas en orden E-01…E-06, E-99) e instalar `ml_service/requirements-modelo.txt`. El servicio los detecta al arrancar; Django no cambia. Los nombres de los estilos se cambian en `config/apps/clasificacion/catalogo.py`.

## Producción

`DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (PostgreSQL/Supabase, obligatoria), `DB_SSLMODE=require`, `DJANGO_ADMIN_URL`. Con `DEBUG=0` se activan solos HTTPS, HSTS y cookies seguras. `python manage.py check --deploy` lo verifica.

## Pruebas automáticas (CI)

El flujo está listo en `docs/ci/ci.yml`. Para activarlo ver `docs/ci/LEEME.md`.

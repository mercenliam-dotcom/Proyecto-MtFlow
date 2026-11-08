"""
Configuración de MTFlow.

Toda la configuración sensible o dependiente del entorno se lee de variables
de entorno (archivo .env en desarrollo). Ningún secreto vive en el código.

Principio: los valores por defecto son los SEGUROS. Para relajar algo en
desarrollo hay que pedirlo explícitamente con DJANGO_DEBUG=1.
"""
from pathlib import Path
import os
from urllib.parse import urlparse, unquote

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Lectura de variables de entorno
# ---------------------------------------------------------------------------
def _cargar_env(ruta: Path) -> None:
    """Carga un archivo .env simple (CLAVE=valor). No pisa variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BASE_DIR / ".env")


def env(clave, defecto=None, requerido=False):
    valor = os.environ.get(clave, defecto)
    if requerido and not valor:
        raise ImproperlyConfigured(
            f"Falta la variable {clave}. Copia config/.env.example como config/.env y complétalo."
        )
    return valor


def env_bool(clave, defecto=False):
    return str(os.environ.get(clave, "1" if defecto else "0")).lower() in ("1", "true", "si", "yes")


def env_lista(clave, defecto=""):
    return [x.strip() for x in os.environ.get(clave, defecto).split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY", requerido=True)
if not DEBUG and len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY debe tener al menos 50 caracteres en producción.")


# ---------------------------------------------------------------------------
# Hosts permitidos (protección contra Host header injection)
# ---------------------------------------------------------------------------
# Django responde 400 a cualquier petición cuyo encabezado Host no esté en
# esta lista. Así nadie puede "cambiar el localhost" para envenenar enlaces
# de restablecimiento o redirecciones.
ALLOWED_HOSTS = env_lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_lista("DJANGO_CSRF_TRUSTED_ORIGINS", "")
USE_X_FORWARDED_HOST = False  # nunca confiar en X-Forwarded-Host enviado por el cliente


# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "web",                 # pantallas públicas: portafolio, horarios, cotización
    "apps.nucleo",
    "apps.cuentas",
    "apps.clasificacion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.nucleo.middleware.CabecerasSeguridadMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.cuentas.permisos.ForzarCambioContrasenaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            # autoescape está activo por defecto: todo valor que venga del
            # usuario se escapa al renderizar (protección XSS). En el proyecto
            # está PROHIBIDO usar |safe, mark_safe o {% autoescape off %}
            # sobre datos ingresados por usuarios. Ver docs/seguridad.md.
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Base de datos: PostgreSQL 16 (ADR-0006); SQLite solo como atajo local
# ---------------------------------------------------------------------------
def _db_desde_url(url: str) -> dict:
    p = urlparse(url)
    if p.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL debe ser postgresql://")
    opciones = {}
    # En producción la conexión a la base viaja cifrada con TLS (sslmode=require).
    sslmode = env("DB_SSLMODE", "prefer" if DEBUG else "require")
    opciones["sslmode"] = sslmode
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(p.path.lstrip("/")),
        "USER": unquote(p.username or ""),
        "PASSWORD": unquote(p.password or ""),
        "HOST": p.hostname or "",
        "PORT": str(p.port or 5432),
        "OPTIONS": opciones,
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": True,
    }


_DATABASE_URL = env("DATABASE_URL")
if _DATABASE_URL:
    DATABASES = {"default": _db_desde_url(_DATABASE_URL)}
elif DEBUG:
    # Atajo para desarrollo local sin PostgreSQL instalado. El proyecto se
    # prueba y se despliega sobre PostgreSQL: usar esto solo para probar
    # pantallas en tu equipo.
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Nombre distinto al db.sqlite3 anterior: ese se creó con el usuario por
        # defecto de Django y no es compatible con cuentas.Usuario.
        "NAME": BASE_DIR / "mtflow_local.sqlite3",
        "ATOMIC_REQUESTS": True,
    }}
else:
    raise ImproperlyConfigured("En producción DATABASE_URL es obligatoria (PostgreSQL).")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Autenticación y contraseñas
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "cuentas.Usuario"  # fijado ANTES de la primera migración

# Las contraseñas NO se cifran: se guardan como hash Argon2id con sal
# (irreversible). Al iniciar sesión se calcula el hash de lo ingresado y se
# compara con el almacenado.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
     "OPTIONS": {"user_attributes": ("nombre_usuario", "nombre", "apellido", "email")}},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "apps.cuentas.validadores.ComplejidadContrasenaValidator"},
]

LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "nucleo:inicio"
LOGOUT_REDIRECT_URL = "cuentas:login"

# Bloqueo por intentos fallidos de inicio de sesión
LOGIN_MAX_INTENTOS = int(env("LOGIN_MAX_INTENTOS", "5"))
LOGIN_BLOQUEO_SEGUNDOS = int(env("LOGIN_BLOQUEO_SEGUNDOS", "900"))
CONFIAR_EN_PROXY = env_bool("CONFIAR_EN_PROXY", False)

CACHES = {
    # LocMem basta para el prototipo con una sola instancia. Con varias
    # instancias (Cloud Run escalando) usar DatabaseCache o Redis, para que
    # el contador de intentos fallidos sea compartido.
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}


# ---------------------------------------------------------------------------
# HTTPS, cookies y cabeceras de seguridad
# ---------------------------------------------------------------------------
# En producción todo el tráfico va por HTTPS (TLS). El proxy de la
# plataforma (Cloud Run) termina el TLS y avisa con X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if CONFIAR_EN_PROXY else None
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else int(env("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60          # una jornada de trabajo
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

# Política de seguridad de contenido (la aplica apps.nucleo.middleware).
# Sin scripts en línea, sin recursos de terceros, sin incrustar la página.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "object-src 'none'; "
    "media-src 'none'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


# ---------------------------------------------------------------------------
# Subida de archivos
# ---------------------------------------------------------------------------
IMAGEN_MAX_BYTES = int(env("IMAGEN_MAX_BYTES", str(10 * 1024 * 1024)))   # 10 MB
IMAGEN_LADO_MIN_PX = int(env("IMAGEN_LADO_MIN_PX", "224"))               # entrada de EfficientNet-B0
IMAGEN_LADO_MAX_PX = int(env("IMAGEN_LADO_MAX_PX", "8000"))
IMAGEN_MAX_PIXELES = int(env("IMAGEN_MAX_PIXELES", str(40_000_000)))     # anti "bomba de descompresión"
# Umbral provisional del filtro de nitidez (varianza del laplaciano).
# Calibrar con los percentiles que entrega revisar_dataset.py.
IMAGEN_NITIDEZ_MIN = float(env("IMAGEN_NITIDEZ_MIN", "40"))

# Límite de datos de formulario. Los archivos se limitan durante la lectura
# con LimiteImagenUploadHandler. El proxy debe limitar también el cuerpo total.
DATA_UPLOAD_MAX_MEMORY_SIZE = IMAGEN_MAX_BYTES * 3 + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = IMAGEN_MAX_BYTES
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 3
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_HANDLERS = [
    "apps.nucleo.uploads.LimiteImagenUploadHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]

# Los archivos subidos NO se publican como estáticos: solo se sirven a
# través de una vista con sesión iniciada y URL firmada con caducidad.
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media_privado")))
URL_FIRMADA_SEGUNDOS = int(env("URL_FIRMADA_SEGUNDOS", "600"))


# ---------------------------------------------------------------------------
# Servicio de inferencia (FastAPI, ADR-0002)
# ---------------------------------------------------------------------------
ML_SERVICE_URL = env("ML_SERVICE_URL", "http://127.0.0.1:8001")
ML_SERVICE_API_KEY = env("ML_SERVICE_API_KEY", requerido=True)
ML_SERVICE_TIMEOUT = float(env("ML_SERVICE_TIMEOUT", "10"))
# Umbrales tentativos de la recomendación (por validar con las socias)
UMBRAL_PRE_APROBADA = float(env("UMBRAL_PRE_APROBADA", "0.90"))
UMBRAL_REVISION = float(env("UMBRAL_REVISION", "0.85"))


# ---------------------------------------------------------------------------
# Internacionalización y estáticos
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
                    if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Ruta del admin de Django configurable: no exponer /admin/ predecible.
DJANGO_ADMIN_URL = env("DJANGO_ADMIN_URL", "gestion-interna/")


# ---------------------------------------------------------------------------
# Registro de eventos de seguridad
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"consola": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "mtflow.seguridad": {"handlers": ["consola"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["consola"], "level": "WARNING", "propagate": False},
    },
}

# Durante las pruebas automáticas se silencian los registros esperados
# (intentos fallidos, hosts rechazados) para que la salida sea legible.
import sys  # noqa: E402

if len(sys.argv) > 1 and sys.argv[1] == "test":
    for _nombre in ("mtflow.seguridad", "django.security"):
        LOGGING["loggers"][_nombre]["level"] = "CRITICAL"
    LOGGING["loggers"]["django.request"] = {"handlers": ["consola"], "level": "CRITICAL", "propagate": False}
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]

# Control de consumo del estimador público (usar caché compartida al escalar).
COTIZACION_MAX_INTENTOS = int(env("COTIZACION_MAX_INTENTOS", "10"))
COTIZACION_VENTANA_SEGUNDOS = int(env("COTIZACION_VENTANA_SEGUNDOS", "600"))
ANALISIS_MAX_INTENTOS = int(env("ANALISIS_MAX_INTENTOS", "20"))
ANALISIS_VENTANA_SEGUNDOS = int(env("ANALISIS_VENTANA_SEGUNDOS", "600"))

# Cuenta demo admin/admin únicamente mediante activación explícita local.
ADMIN_DESARROLLO_HABILITADO = env_bool("ADMIN_DESARROLLO_HABILITADO", False)

CSRF_FAILURE_VIEW = 'apps.nucleo.errores.csrf_failure'

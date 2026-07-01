"""
Base settings shared by all environments.

Environment-driven via django-environ. See `.env.example` for all variables.
Dev (`dev.py`) and prod (`prod.py`) layer on top of this module.
"""
from __future__ import annotations

import mimetypes
from datetime import timedelta
from pathlib import Path

import environ

# Some platforms (notably Windows) ship an incomplete mimetypes registry that
# lacks modern image types, so files served via Django's dev static handler get
# `application/octet-stream` and, with X-Content-Type-Options: nosniff, fail to
# render in the browser. Register them explicitly. (Nginx handles this in prod.)
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/svg+xml", ".svg")

# config/settings/base.py -> config/settings -> config -> <project root>
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read the first env file that exists (in containers, real env vars still win
# since read_env does not overwrite already-set variables). Order:
#   1. $DJANGO_ENV_FILE (explicit override)
#   2. .env            (canonical / production volume)
#   3. .env.development (local dev convention)
for _candidate in (env("DJANGO_ENV_FILE", default=""), ".env", ".env.development"):
    if _candidate and (BASE_DIR / _candidate).exists():
        environ.Env.read_env(BASE_DIR / _candidate)
        break

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Public URLs used to build absolute links (sitemaps, emails, signed media).
SITE_URL = env("SITE_URL", default="http://localhost:5173")          # frontend
API_URL = env("API_URL", default="http://localhost:8000")            # this API

AUTH_USER_MODEL = "users.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "axes",
    "drf_spectacular",
    # Local apps
    "apps.core",
    "apps.users",
    "apps.media",
    "apps.seo",
    "apps.projects",
    "apps.blog",
    "apps.team",
    "apps.testimonials",
    "apps.careers",
    "apps.leads",
    "apps.newsletter",
    "apps.audit",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RedirectMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

SITE_ID = 1

# ---------------------------------------------------------------------------
# Database (env-driven; Postgres in prod/Docker, SQLite fallback for quick local)
# ---------------------------------------------------------------------------
if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

# ---------------------------------------------------------------------------
# Password hashing — Argon2 first (per security architecture)
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# django-axes brute-force protection
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=env.int("AXES_COOLOFF_MINUTES", default=15))
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True

# ---------------------------------------------------------------------------
# DRF + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/min"),
        "user": env("THROTTLE_USER", default="240/min"),
        "form": env("THROTTLE_FORM", default="5/min"),          # public form POSTs
        "login": env("THROTTLE_LOGIN", default="5/min"),
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Morpheme Studios API",
    "DESCRIPTION": "Backend API for Morpheme Studios frontend and CRM",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MIN", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Refresh token lives in an HttpOnly cookie (set/cleared by the auth views).
JWT_REFRESH_COOKIE = "ms_refresh"
JWT_REFRESH_COOKIE_SECURE = env.bool("JWT_COOKIE_SECURE", default=not DEBUG)
JWT_REFRESH_COOKIE_SAMESITE = env("JWT_COOKIE_SAMESITE", default="Strict")
JWT_REFRESH_COOKIE_PATH = "/api/v1/auth"

# ---------------------------------------------------------------------------
# CORS (locked to known frontends)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Cache + Celery (Redis)
# Redis backs the DRF throttle counters / short-lived caching AND is the Celery
# broker + result backend. Background workers offload email sending etc.
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")


def _redis_db(index: int) -> str:
    """Return REDIS_URL with its DB index swapped — keeps cache / broker /
    result on separate Redis logical DBs so cache eviction can't drop tasks."""
    base = REDIS_URL.rsplit("/", 1)[0]
    return f"{base}/{index}"


# Cache = DB 0 (REDIS_URL as given), Celery broker = DB 1, result = DB 2.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=_redis_db(1))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=_redis_db(2))
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_WORKER_MAX_TASKS_PER_CHILD = 200
# Reliability: retry broker connection at worker startup; bound redelivery
# window so an acks_late task can't be redelivered while still running.
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600}
CELERY_RESULT_EXPIRES = 3600

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Private uploads (CVs/portfolios) live under a separate root. The public,
# signed download endpoint is Django's `/protected/<token>`; Django streams the
# bytes via X-Accel-Redirect to this INTERNAL Nginx location (must differ from
# the public path to avoid a routing collision).
PRIVATE_MEDIA_ROOT = BASE_DIR / "private-media"
PRIVATE_MEDIA_URL = "/_protected/"
MEDIA_SIGNED_URL_TTL = env.int("MEDIA_SIGNED_URL_TTL", default=300)  # seconds

# File upload limits (Careers: CV/portfolio/cover letter, PDF only, <=10MB).
# Validation is type + size + magic-byte sniffing (no external AV service).
MAX_UPLOAD_BYTES = env.int("MAX_UPLOAD_BYTES", default=10 * 1024 * 1024)
ALLOWED_UPLOAD_MIME = ["application/pdf"]

DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Morpheme Studios <no-reply@morphemestudios.com>")
LEADS_NOTIFY_EMAIL = env("LEADS_NOTIFY_EMAIL", default="connect@morphemestudios.com")

# ---------------------------------------------------------------------------
# Spam protection (Cloudflare Turnstile) — verified server-side on form POSTs
# ---------------------------------------------------------------------------
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")
TURNSTILE_ENABLED = env.bool("TURNSTILE_ENABLED", default=bool(TURNSTILE_SECRET_KEY))

# ---------------------------------------------------------------------------
# Frontend rebuild hook (publish -> rebuild prerendered SPA on the VPS)
# ---------------------------------------------------------------------------
FRONTEND_REBUILD_ENABLED = env.bool("FRONTEND_REBUILD_ENABLED", default=False)
FRONTEND_REBUILD_COMMAND = env("FRONTEND_REBUILD_COMMAND", default="")
FRONTEND_REBUILD_DEBOUNCE_SEC = env.int("FRONTEND_REBUILD_DEBOUNCE_SEC", default=60)

# ---------------------------------------------------------------------------
# i18n / tz
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging (structured-ish; PII kept out of messages)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

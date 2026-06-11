"""Production settings (VPS, behind Nginx + TLS)."""
from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SECRET_KEY, env

DEBUG = False

# ---------------------------------------------------------------------------
# Fail loudly on insecure/missing critical config (never boot prod misconfigured)
# ---------------------------------------------------------------------------
if not env("DJANGO_SECRET_KEY", default="") or SECRET_KEY == "insecure-dev-key-change-me":
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong, unique value in production "
        "(the insecure development default is not allowed)."
    )

if not env("DATABASE_URL", default=""):
    raise ImproperlyConfigured(
        "DATABASE_URL must be set in production (the SQLite fallback is for local "
        "development only)."
    )

# Hosts/origins must be explicit in production.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=CORS_ALLOWED_ORIGINS)

# Behind Nginx: trust the forwarded proto for HTTPS detection.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Transport security
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Header hardening (defense in depth alongside Nginx)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Content-Security-Policy (django-csp). Tighten allowlists per real asset origins.
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "data:")
CSP_IMG_SRC = ("'self'", "data:", "blob:") + tuple(
    env.list("CSP_EXTRA_IMG_SRC", default=[])
)
CSP_CONNECT_SRC = ("'self'",) + tuple(env.list("CSP_EXTRA_CONNECT_SRC", default=[]))
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)

# Optional Cloudflare R2 for media (S3-compatible) — enabled when bucket env is set.
if env("R2_BUCKET", default=""):
    STORAGES["default"] = {  # noqa: F405
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("R2_BUCKET"),
            "endpoint_url": env("R2_ENDPOINT_URL"),
            "access_key": env("R2_ACCESS_KEY_ID"),
            "secret_key": env("R2_SECRET_ACCESS_KEY"),
            "region_name": env("R2_REGION", default="auto"),
            "default_acl": "private",
            "querystring_auth": True,
        },
    }

# Sentry
if env("SENTRY_DSN", default=""):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        integrations=[DjangoIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_RATE", default=0.1),
        send_default_pii=False,
    )

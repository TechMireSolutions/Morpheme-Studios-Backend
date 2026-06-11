"""Development settings."""
from __future__ import annotations

from .base import *  # noqa: F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Relaxed CSP / no HSTS locally is handled by simply not enforcing prod headers here.
INSTALLED_APPS += ["django_extensions"]  # noqa: F405

# Email to console unless overridden.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")


# Local dev/tests shouldn't hard-require a running Redis. If Redis isn't
# configured or isn't reachable, use an in-memory cache and run Celery tasks
# eagerly (in-process) so the task code still executes and is testable.
def _redis_reachable(url: str) -> bool:
    import socket
    import urllib.parse
    try:
        parts = urllib.parse.urlparse(url)
        with socket.create_connection((parts.hostname or "127.0.0.1", parts.port or 6379), timeout=0.3):
            return True
    except OSError:
        return False


if not _redis_reachable(env("REDIS_URL", default="redis://127.0.0.1:6379/0")):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "morpheme-dev",
        }
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

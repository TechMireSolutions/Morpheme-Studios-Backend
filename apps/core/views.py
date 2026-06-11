"""Liveness / readiness probes (no auth, no throttle)."""
from __future__ import annotations

from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    """Liveness: the process is up and serving."""
    return Response({"status": "ok"})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def ready(request):
    """Readiness: dependencies (DB, cache) reachable."""
    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            checks["database"] = cur.fetchone()[0] == 1
    except Exception:  # pragma: no cover - reported via status
        checks["database"] = False
    try:
        cache.set("readyz", "1", 5)
        checks["cache"] = cache.get("readyz") == "1"
    except Exception:  # pragma: no cover
        checks["cache"] = False

    healthy = all(checks.values())
    return Response(
        {"status": "ready" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )

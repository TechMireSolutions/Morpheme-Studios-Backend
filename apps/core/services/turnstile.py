"""Cloudflare Turnstile server-side verification for public form POSTs.

Disabled (always-pass) when TURNSTILE_ENABLED is false, so local dev and tests
don't need a live key. Uses stdlib urllib to avoid an extra dependency.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger("apps.security")

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    if not settings.TURNSTILE_ENABLED:
        return True
    if not token:
        return False
    payload = urllib.parse.urlencode(
        {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip or "",
        }
    ).encode()
    try:
        req = urllib.request.Request(_VERIFY_URL, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - fixed CF URL
            data = json.loads(resp.read().decode())
        ok = bool(data.get("success"))
        if not ok:
            logger.warning("Turnstile verification failed")
        return ok
    except (urllib.error.URLError, ValueError):
        logger.exception("Turnstile verification error")
        return False

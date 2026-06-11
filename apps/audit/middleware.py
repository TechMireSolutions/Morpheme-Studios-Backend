"""Stashes the current request's actor/IP/UA in a thread-local so the audit
service can attribute mutations without threading `request` everywhere."""
from __future__ import annotations

import threading

_ctx = threading.local()


def get_client_ip(request) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _ctx.actor = getattr(request, "user", None)
        _ctx.ip = get_client_ip(request)
        _ctx.user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
        try:
            return self.get_response(request)
        finally:
            _ctx.actor = None
            _ctx.ip = None
            _ctx.user_agent = ""


def current_context() -> dict:
    actor = getattr(_ctx, "actor", None)
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return {
        "actor": actor,
        "ip_address": getattr(_ctx, "ip", None),
        "user_agent": getattr(_ctx, "user_agent", ""),
    }

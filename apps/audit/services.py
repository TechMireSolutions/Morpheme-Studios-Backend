"""Single entry point for writing audit entries."""
from __future__ import annotations

from .middleware import current_context
from .models import AuditLog


def record(action: str, *, target=None, target_type: str = "", target_id: str = "",
           changes: dict | None = None) -> AuditLog:
    ctx = current_context()
    if target is not None:
        target_type = target_type or target.__class__.__name__
        target_id = target_id or str(getattr(target, "pk", ""))
    return AuditLog.objects.create(
        actor=ctx["actor"],
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        changes=changes or {},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )

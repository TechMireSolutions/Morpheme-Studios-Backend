"""Role-based DRF permission classes (architecture §5)."""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role


class IsStaff(BasePermission):
    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and u.is_staff)


class IsAdminLevel(BasePermission):
    """Super Admin or Admin only."""

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "is_admin_level", False))


class CanManageContent(BasePermission):
    """Editor/Content Manager may write; SEO Manager read-only; publish gated
    by `User.can_publish()` for state changes (enforced in the serializer)."""

    write_roles = {Role.ADMIN, Role.SUPER_ADMIN, Role.EDITOR, Role.CONTENT_MANAGER}

    def has_permission(self, request, view) -> bool:
        u = request.user
        if not (u and u.is_authenticated and u.is_staff):
            return False
        if request.method in SAFE_METHODS:
            return True
        return u.is_super_admin or u.role in self.write_roles


class CanManageSeo(BasePermission):
    def has_permission(self, request, view) -> bool:
        u = request.user
        if not (u and u.is_authenticated and u.is_staff):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(u, "manages_seo", lambda: False)()


class CanManageLeads(BasePermission):
    pipeline_roles = {Role.ADMIN, Role.SUPER_ADMIN, Role.CONTENT_MANAGER}

    def has_permission(self, request, view) -> bool:
        u = request.user
        if not (u and u.is_authenticated and u.is_staff):
            return False
        if request.method in SAFE_METHODS:
            return True
        return u.is_super_admin or u.role in self.pipeline_roles


class CanManageApplications(BasePermission):
    """Job-application PII (CVs, portfolios, home addresses) — restricted to
    Admin / Super Admin only, for BOTH read and write. Editors, SEO Managers and
    Content Managers are denied entirely (unlike CanManageLeads, this does NOT
    grant SAFE-method access to all staff).

    If dedicated non-admin HR staff are introduced later, add a `Role.HR` and
    include it here — no other change needed.
    """

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and u.is_staff and getattr(u, "is_admin_level", False))

from __future__ import annotations

import pytest

from apps.users.models import Role

pytestmark = pytest.mark.django_db


def test_login_success_sets_refresh_cookie(api, super_admin):
    r = api.post("/api/v1/auth/login",
                 {"email": "super@x.com", "password": "StrongPassw0rd!23"}, format="json")
    assert r.status_code == 200
    assert "access" in r.data and r.data["user"]["role"] == "super_admin"
    from django.conf import settings
    assert settings.JWT_REFRESH_COOKIE in r.cookies


def test_login_wrong_password_401_and_audited(api, super_admin):
    from apps.audit.models import AuditLog
    r = api.post("/api/v1/auth/login",
                 {"email": "super@x.com", "password": "wrong"}, format="json")
    assert r.status_code == 401
    assert AuditLog.objects.filter(action="login_failed").exists()


def test_me_requires_auth(api):
    assert api.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(auth, super_admin):
    client = auth(super_admin)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200 and r.data["email"] == "super@x.com"


def test_refresh_rotates_token(api, super_admin):
    login = api.post("/api/v1/auth/login",
                     {"email": "super@x.com", "password": "StrongPassw0rd!23"}, format="json")
    cookie = login.cookies[__import__("django").conf.settings.JWT_REFRESH_COOKIE].value
    api.cookies[__import__("django").conf.settings.JWT_REFRESH_COOKIE] = cookie
    r = api.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and "access" in r.data


def test_admin_leads_requires_auth(api):
    assert api.get("/api/v1/admin/leads").status_code == 401


def test_admin_leads_visible_to_super_admin(auth, super_admin):
    assert auth(super_admin).get("/api/v1/admin/leads").status_code == 200


def test_seo_manager_cannot_mutate_leads(make_user, auth, db):
    from apps.leads.models import Lead
    lead = Lead.objects.create(name="x", email="x@x.com", message="m")
    seo = make_user("seo@x.com", role=Role.SEO_MANAGER)
    client = auth(seo)
    # SEO manager is not in the leads pipeline -> read denied too (CanManageLeads requires staff+role)
    r = client.patch(f"/api/v1/admin/leads/{lead.id}", {"status": "won"}, format="json")
    assert r.status_code == 403


def test_content_manager_can_update_lead_status(make_user, auth, db):
    from apps.leads.models import Lead
    lead = Lead.objects.create(name="x", email="x@x.com", message="m")
    cm = make_user("cm@x.com", role=Role.CONTENT_MANAGER)
    r = auth(cm).patch(f"/api/v1/admin/leads/{lead.id}", {"status": "contacted"}, format="json")
    assert r.status_code == 200
    lead.refresh_from_db()
    assert lead.status == "contacted"


def test_audit_logs_admin_only(make_user, auth):
    editor = make_user("ed@x.com", role=Role.EDITOR)
    assert auth(editor).get("/api/v1/admin/audit-logs").status_code == 403

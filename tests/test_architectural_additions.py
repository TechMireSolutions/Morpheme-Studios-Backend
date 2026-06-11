from __future__ import annotations

import pytest
import urllib.parse
from django.core import mail

from apps.core.models import RedirectRule
from apps.users.models import Role

pytestmark = pytest.mark.django_db


def test_redirect_middleware_rules(api):
    # Create permanent redirect rule (301)
    RedirectRule.objects.create(
        from_path="/old-about-us",
        to_path="/about",
        status_code=301,
        is_active=True
    )
    # Create temporary redirect rule (302)
    RedirectRule.objects.create(
        from_path="/old-contact",
        to_path="/contact",
        status_code=302,
        is_active=True
    )
    # Create inactive rule
    RedirectRule.objects.create(
        from_path="/inactive-path",
        to_path="/active-path",
        status_code=301,
        is_active=False
    )

    # Test permanent redirect
    r = api.get("/old-about-us")
    assert r.status_code == 301
    assert r.headers["Location"] == "/about"

    # Test permanent redirect with trailing slash matching
    r = api.get("/old-about-us/")
    assert r.status_code == 301
    assert r.headers["Location"] == "/about"

    # Test temporary redirect
    r = api.get("/old-contact")
    assert r.status_code == 302
    assert r.headers["Location"] == "/contact"

    # Test inactive path (should not redirect, will return 404)
    r = api.get("/inactive-path")
    assert r.status_code == 404


def test_password_reset_flow(api, make_user):
    user = make_user("reset-user@x.com")
    user.set_password("OldPassword!123")
    user.save()

    # Step 1: Request Password Reset
    r = api.post("/api/v1/auth/password/reset/request", {"email": "reset-user@x.com"}, format="json")
    assert r.status_code == 200
    assert r.data == {"status": "password_reset_sent"}

    # Check email was sent
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == ["reset-user@x.com"]
    assert "reset-password" in email.body

    # Extract uid and token from link using robust url parsing
    words = email.body.split()
    link = [w for w in words if "reset-password" in w][0]
    parsed_url = urllib.parse.urlparse(link)
    params = urllib.parse.parse_qs(parsed_url.query)
    uid = params["uid"][0]
    token = params["token"][0]

    # Step 2: Confirm Password Reset
    r = api.post("/api/v1/auth/password/reset/confirm", {
        "uid": uid,
        "token": token,
        "new_password": "NewCoolPassword!123"
    }, format="json")
    assert r.status_code == 200
    assert r.data == {"status": "password_reset_confirmed"}

    # Step 3: Verify user can login with new password
    r = api.post("/api/v1/auth/login", {
        "email": "reset-user@x.com",
        "password": "NewCoolPassword!123"
    }, format="json")
    assert r.status_code == 200
    assert "access" in r.data


def test_mfa_login_interception(api, make_user):
    user = make_user("mfa-user@x.com")
    user.mfa_enabled = True
    user.set_password("StrongPassw0rd!23")
    user.save()

    # Login when MFA is enabled
    r = api.post("/api/v1/auth/login", {
        "email": "mfa-user@x.com",
        "password": "StrongPassw0rd!23"
    }, format="json")
    assert r.status_code == 200
    assert r.data == {
        "mfa_required": True,
        "detail": "Multi-factor verification required.",
        "user_id": user.id
    }
    # Standard tokens and cookies must not be present
    assert "access" not in r.data
    from django.conf import settings
    assert settings.JWT_REFRESH_COOKIE not in r.cookies


def test_admin_rest_api_permissions(api, auth, super_admin, make_user):
    from apps.projects.models import Project, ProjectCategory
    cat = ProjectCategory.objects.create(key="residential", label="Residential")
    Project.objects.create(
        slug="residential-1", title="Res 1", category=cat, type="Residential",
        status="published"
    )

    # 1. Unauthenticated request to /api/v1/admin/projects
    r = api.get("/api/v1/admin/projects")
    assert r.status_code == 401

    # 2. Super admin request to /api/v1/admin/projects (allowed)
    r = auth(super_admin).get("/api/v1/admin/projects")
    assert r.status_code == 200

    # 3. Content manager (CanManageContent) - read/write allowed
    cm = make_user("cm-editor@x.com", role=Role.CONTENT_MANAGER)
    r = auth(cm).get("/api/v1/admin/projects")
    assert r.status_code == 200

    # 4. SEO Manager (CanManageContent) - read-only allowed, write denied
    seo = make_user("seo-manager@x.com", role=Role.SEO_MANAGER)
    r = auth(seo).get("/api/v1/admin/projects")
    assert r.status_code == 200
    
    # Try POST as SEO Manager (denied)
    r = auth(seo).post("/api/v1/admin/projects", {
        "slug": "residential-2", "title": "Res 2", "category": cat.id, "type": "Residential"
    }, format="json")
    assert r.status_code == 403
    
    # Try POST as Content Manager (allowed)
    r = auth(cm).post("/api/v1/admin/projects", {
        "slug": "residential-2", "title": "Res 2", "category": cat.id, "type": "Residential"
    }, format="json")
    assert r.status_code == 201

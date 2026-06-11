from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, override_settings

from apps.media.models import Media
from apps.media.services import store_private_upload
from apps.media.signing import make_token
from apps.media.views import protected_download
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db


def _pdf():
    return SimpleUploadedFile("cv.pdf", b"%PDF-1.4 real body", content_type="application/pdf")


def _request(user=None):
    req = RequestFactory().get("/protected/x")
    req.user = user if user is not None else _anon()
    return req


def _anon():
    from django.contrib.auth.models import AnonymousUser
    return AnonymousUser()


def _admin():
    return User.objects.create_superuser("hr-admin@x.com", "StrongPassw0rd!23")


def _editor():
    return User.objects.create_user("editor@x.com", "StrongPassw0rd!23", role=Role.EDITOR, is_staff=True)


# --- storage round-trip (now requires an authenticated admin) ---
def test_private_upload_round_trip_download():
    media = store_private_upload(_pdf())
    assert media.is_private
    resp = protected_download(_request(_admin()), make_token(media.id))
    assert resp.status_code == 200  # FileResponse (dev) or X-Accel (prod)


# --- Phase 2 authorization tests ---
def test_download_denied_for_anonymous():
    media = store_private_upload(_pdf())
    with pytest.raises(PermissionDenied):
        protected_download(_request(_anon()), make_token(media.id))


def test_download_denied_for_non_admin_staff():
    media = store_private_upload(_pdf())
    with pytest.raises(PermissionDenied):
        protected_download(_request(_editor()), make_token(media.id))


def test_download_allowed_for_admin():
    media = store_private_upload(_pdf())
    resp = protected_download(_request(_admin()), make_token(media.id))
    assert resp.status_code == 200


def test_expired_token_denied_even_for_admin():
    media = store_private_upload(_pdf())
    token = make_token(media.id)
    with override_settings(MEDIA_SIGNED_URL_TTL=-1):  # any token is now expired
        with pytest.raises(Http404):
            protected_download(_request(_admin()), token)


def test_invalid_token_denied_even_for_admin():
    media = store_private_upload(_pdf())
    with pytest.raises(Http404):
        protected_download(_request(_admin()), make_token(media.id) + "x")


def test_public_media_not_served_via_private_endpoint():
    pub = Media(type=Media.Type.IMAGE, is_private=False,
                file=SimpleUploadedFile("x.png", b"\x89PNG", content_type="image/png"))
    pub.save()
    with pytest.raises(Http404):
        protected_download(_request(_admin()), make_token(pub.id))


# --- Phase 2: applications API is admin-only (PII) ---
def test_applications_api_denied_for_non_admin_roles(api):
    from rest_framework.test import APIClient
    for role in (Role.EDITOR, Role.SEO_MANAGER, Role.CONTENT_MANAGER):
        user = User.objects.create_user(f"{role}@x.com", "StrongPassw0rd!23", role=role, is_staff=True)
        c = APIClient()
        c.force_authenticate(user=user)
        assert c.get("/api/v1/admin/applications").status_code == 403, role


def test_applications_api_allowed_for_admin():
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user=_admin())
    assert c.get("/api/v1/admin/applications").status_code == 200

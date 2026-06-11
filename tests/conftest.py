from __future__ import annotations

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import Role, User


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the LocMemCache between tests so DRF throttle history (and the
    dashboard cache) don't leak across tests."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make(email, role=Role.CONTENT_MANAGER, **extra):
        return User.objects.create_user(
            email=email, password="StrongPassw0rd!23", role=role, is_staff=True, **extra
        )
    return _make


@pytest.fixture
def super_admin(db):
    return User.objects.create_superuser("super@x.com", "StrongPassw0rd!23")


@pytest.fixture
def auth(api):
    """Authenticate the client as a given user via force_authenticate."""
    def _auth(user):
        api.force_authenticate(user=user)
        return api
    return _auth


@pytest.fixture
def published_project(db):
    from apps.projects.models import Project, ProjectCategory
    cat = ProjectCategory.objects.create(key="residential", label="Residential")
    return Project.objects.create(
        slug="test-villa", title="Test Villa", category=cat, type="Residential",
        excerpt="A test.", description="Body.", status="published",
        published_at=timezone.now(),
    )


@pytest.fixture
def published_post(db, super_admin):
    from apps.blog.models import BlogPost
    return BlogPost.objects.create(
        slug="hello-world", title="Hello World", excerpt="Intro", body="<p>Body</p>",
        author=super_admin, status="published", published_at=timezone.now(),
    )

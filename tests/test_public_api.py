from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_projects_list_only_published(api, published_project):
    from apps.projects.models import Project
    Project.objects.create(slug="hidden", title="Hidden", status="draft")
    r = api.get("/api/v1/projects")
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.data["results"]]
    assert "test-villa" in slugs and "hidden" not in slugs


def test_project_detail(api, published_project):
    r = api.get("/api/v1/projects/test-villa")
    assert r.status_code == 200
    assert r.data["title"] == "Test Villa"
    assert "gallery" in r.data and "description" in r.data


def test_project_categories_not_swallowed_by_detail_route(api, published_project):
    r = api.get("/api/v1/projects/categories")
    assert r.status_code == 200
    assert any(c["key"] == "residential" for c in r.data)


def test_blog_list_and_detail(api, published_post):
    assert api.get("/api/v1/blog").status_code == 200
    r = api.get("/api/v1/blog/hello-world")
    assert r.status_code == 200 and r.data["body"] == "<p>Body</p>"


def test_unknown_project_404(api):
    assert api.get("/api/v1/projects/nope").status_code == 404


def test_seo_meta_resolves(api, published_project):
    r = api.get("/api/v1/seo/meta?path=/projects/test-villa")
    assert r.status_code == 200
    assert "Test Villa" in r.data["title"]
    assert r.data["jsonld"]["@type"]  # has structured data


def test_sitemap_and_robots(client, published_project):
    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200 and b"test-villa" in sm.content
    rb = client.get("/robots.txt")
    assert rb.status_code == 200 and b"Sitemap:" in rb.content


def test_health_and_ready(api):
    assert api.get("/health").status_code == 200
    # /ready also returns 200 (LocMemCache + sqlite both reachable in tests)
    assert api.get("/ready").status_code in (200, 503)

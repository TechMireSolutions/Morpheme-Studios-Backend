"""SEO/infra endpoints served by Django (always fresh): sitemap.xml, robots.txt,
and the per-route meta lookup used by the frontend prerender step."""
from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.blog.models import BlogPost
from apps.projects.models import Project

from .services import meta_for_path


def _site(path: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def sitemap_xml(request) -> HttpResponse:
    urls = [{"loc": _site("/"), "priority": "1.0"},
            {"loc": _site("/studio"), "priority": "0.7"},
            {"loc": _site("/projects"), "priority": "0.8"},
            {"loc": _site("/blog"), "priority": "0.7"},
            {"loc": _site("/careers"), "priority": "0.6"},
            {"loc": _site("/contact"), "priority": "0.6"}]
    for p in Project.objects.published().only("slug", "updated_at"):
        urls.append({"loc": _site(f"/projects/{p.slug}"),
                     "lastmod": p.updated_at.date().isoformat(), "priority": "0.8"})
    for b in BlogPost.objects.published().only("slug", "updated_at"):
        urls.append({"loc": _site(f"/blog/{b.slug}"),
                     "lastmod": b.updated_at.date().isoformat(), "priority": "0.6"})

    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        body.append("<url><loc>{loc}</loc>".format(loc=u["loc"]))
        if u.get("lastmod"):
            body.append(f"<lastmod>{u['lastmod']}</lastmod>")
        body.append(f"<priority>{u['priority']}</priority></url>")
    body.append("</urlset>")
    return HttpResponse("".join(body), content_type="application/xml")


def robots_txt(request) -> HttpResponse:
    lines = ["User-agent: *"]
    if getattr(settings, "DEBUG", False) or settings.SITE_URL.startswith("http://localhost"):
        lines.append("Disallow: /")  # never index staging/dev
    else:
        lines += ["Disallow: /admin", "Disallow: /api/v1/admin", "Allow: /"]
    lines.append(f"Sitemap: {settings.API_URL.rstrip('/')}/sitemap.xml")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def seo_meta(request):
    """GET /api/v1/seo/meta?path=/projects/foo — resolved meta + JSON-LD."""
    path = request.query_params.get("path", "/")
    obj = None
    defaults: dict = {}
    if path.startswith("/projects/"):
        obj = Project.objects.published().filter(slug=path.rsplit("/", 1)[-1]).first()
        if obj:
            defaults = {"title": f"{obj.title} — Morpheme Studios", "description": obj.excerpt}
    elif path.startswith("/blog/"):
        obj = BlogPost.objects.published().filter(slug=path.rsplit("/", 1)[-1]).first()
        if obj:
            defaults = {"title": f"{obj.title} — Morpheme Studios", "description": obj.excerpt}
    return Response(meta_for_path(path, obj, defaults=defaults))

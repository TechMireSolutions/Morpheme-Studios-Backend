"""Root URL configuration.

Mounts: Django Admin (the CMS), health probes, the SEO/infra endpoints served
fresh by Django (sitemap.xml, robots.txt), protected media downloads, and the
full `/api/v1/` surface aggregated in `config/api_urls.py`.
"""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.media.views import protected_download
from apps.seo.views import robots_txt, sitemap_xml

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),  # /health, /ready
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path(
        "protected/<str:token>",
        protected_download,
        name="protected-download",
    ),
    path("api/v1/", include("config.api_urls")),
    
    # OpenAPI + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

# Serve public media in dev (Nginx handles this in production).
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )

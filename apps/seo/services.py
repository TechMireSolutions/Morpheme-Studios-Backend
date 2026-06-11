"""Build the SEO payload for a route: resolved metadata + JSON-LD, with sane
auto-fallbacks when an editor hasn't set explicit values (architecture §9)."""
from __future__ import annotations

from django.conf import settings

from .models import SeoMeta


def _abs(path: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def organization_schema() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Morpheme Studios",
        "url": settings.SITE_URL,
    }


def meta_for_path(path: str, obj=None, *, defaults: dict | None = None) -> dict:
    """Resolve SeoMeta for a path or attached object, falling back to defaults."""
    defaults = defaults or {}
    meta = None
    if obj is not None:
        meta = SeoMeta.objects.filter(
            content_type__model=obj._meta.model_name,
            object_id=obj.pk,
        ).first()
    if meta is None:
        meta = SeoMeta.objects.filter(path=path).first()

    title = (meta.meta_title if meta and meta.meta_title else defaults.get("title", "Morpheme Studios"))
    description = (meta.meta_description if meta and meta.meta_description
                  else defaults.get("description", ""))
    canonical = (meta.canonical_url if meta and meta.canonical_url else _abs(path))
    og_image = None
    if meta and meta.og_image and not meta.og_image.is_private:
        try:
            og_image = meta.og_image.file.url
        except ValueError:
            og_image = None
    og_image = og_image or defaults.get("og_image")

    schema = (meta.schema_jsonld if meta and meta.schema_jsonld else defaults.get("schema"))

    return {
        "path": path,
        "title": title,
        "description": description,
        "canonical": canonical,
        "robots": (meta.robots_directives if meta else "index,follow"),
        "og": {
            "title": (meta.og_title if meta and meta.og_title else title),
            "description": (meta.og_description if meta and meta.og_description else description),
            "image": og_image,
        },
        "twitter_card": (meta.twitter_card if meta else "summary_large_image"),
        "jsonld": schema or organization_schema(),
    }

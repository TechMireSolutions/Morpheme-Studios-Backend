from __future__ import annotations

from django.contrib.contenttypes.admin import GenericStackedInline

from .models import SeoMeta


class SeoMetaInline(GenericStackedInline):
    """Attach to any content ModelAdmin to edit its SEO inline."""

    model = SeoMeta
    extra = 0
    max_num = 1
    fields = (
        "meta_title", "meta_description", "canonical_url",
        "og_title", "og_description", "og_image",
        "twitter_card", "robots_directives", "schema_jsonld",
    )

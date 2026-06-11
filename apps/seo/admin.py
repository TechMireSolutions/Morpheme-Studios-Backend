from __future__ import annotations

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline

from .models import SeoMeta


@admin.register(SeoMeta)
class SeoMetaAdmin(admin.ModelAdmin):
    """Standalone SEO workspace — create/manage path-based entries (e.g. /contact,
    /studio) directly, plus see object-attached meta. Object-bound rows are also
    editable inline on their content admin via SeoMetaInline."""

    list_display = ("__str__", "path", "meta_title", "robots_directives", "updated_at")
    list_filter = ("twitter_card", "robots_directives")
    search_fields = ("path", "meta_title", "meta_description", "canonical_url")
    fields = (
        "path", "content_type", "object_id",
        "meta_title", "meta_description", "canonical_url",
        "og_title", "og_description", "og_image",
        "twitter_card", "robots_directives", "schema_jsonld",
    )
    autocomplete_fields = ("og_image",)


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

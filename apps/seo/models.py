"""Polymorphic SEO metadata (architecture §2.2 / §9).

Attaches to any content object via a generic FK, or to an ad-hoc route via
`path` (for pages that aren't backed by a model). Owns title/description,
canonical, Open Graph, Twitter Card and a JSON-LD schema blob.
"""
from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class SeoMeta(models.Model):
    class TwitterCard(models.TextChoices):
        SUMMARY = "summary", "Summary"
        SUMMARY_LARGE = "summary_large_image", "Summary large image"

    # Either attach to an object (generic FK) ...
    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # ... or to a bare path (e.g. "/contact").
    path = models.CharField(max_length=512, null=True, blank=True, unique=True, db_index=True)

    meta_title = models.CharField(max_length=180, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    canonical_url = models.URLField(blank=True)
    og_title = models.CharField(max_length=180, blank=True)
    og_description = models.CharField(max_length=320, blank=True)
    og_image = models.ForeignKey(
        "media.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    twitter_card = models.CharField(
        max_length=20, choices=TwitterCard.choices, default=TwitterCard.SUMMARY_LARGE
    )
    robots_directives = models.CharField(max_length=120, blank=True, default="index,follow")
    schema_jsonld = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEO metadata"
        verbose_name_plural = "SEO metadata"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="uniq_seo_per_object",
                condition=models.Q(object_id__isnull=False),
            )
        ]

    def __str__(self) -> str:
        return self.path or self.meta_title or f"SEO #{self.pk}"

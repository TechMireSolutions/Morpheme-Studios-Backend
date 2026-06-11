"""Shared abstract bases + site-wide config models.

The abstract bases (`TimeStampedModel`, `PublishableModel`) carry the common
columns described in the architecture doc §2.2 so every content table stays
consistent. The concrete models here are the low-churn site config collections
(offices, settings, redirects, editable static pages).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """`created_at` / `updated_at` / `created_by` on every content table."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class PublishStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class PublishedQuerySet(models.QuerySet):
    def published(self) -> "PublishedQuerySet":
        return self.filter(status=PublishStatus.PUBLISHED)


class PublishableModel(TimeStampedModel):
    """Adds the draft/published/archived workflow. Only `published` rows are
    ever returned by the public API."""

    status = models.CharField(
        max_length=12,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Site config collections
# ---------------------------------------------------------------------------
class Office(models.Model):
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=120)
    address_lines = models.JSONField(default=list, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "city"]

    def __str__(self) -> str:
        return f"{self.city}, {self.country}"


class SiteSetting(models.Model):
    """Key/value site config (mission, approach, stats, social URLs)."""

    key = models.SlugField(max_length=80, unique=True)
    value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.key


class RedirectRule(models.Model):
    """301/302 management so old WordPress URLs don't 404 (SEO §9)."""

    STATUS_CHOICES = [(301, "301 Permanent"), (302, "302 Temporary")]

    from_path = models.CharField(max_length=512, unique=True, db_index=True)
    to_path = models.CharField(max_length=512)
    status_code = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=301)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.from_path} -> {self.to_path} ({self.status_code})"


class Page(PublishableModel):
    """Editable static pages (home, studio, terms) as block JSON."""

    key = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    blocks = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.key

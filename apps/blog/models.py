"""Blog (thought-leadership). Adds the real article body the old site had
but the new SPA dropped (audit §3)."""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import PublishableModel
from apps.core.sanitize import sanitize_html


class BlogCategory(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)

    class Meta:
        verbose_name_plural = "Blog categories"
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label


class Tag(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label


class BlogPost(PublishableModel):
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=200)
    excerpt = models.CharField(max_length=400, blank=True)
    body = models.TextField(blank=True, help_text="Sanitised HTML / rich text")
    cover = models.ForeignKey(
        "media.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    category = models.ForeignKey(
        BlogCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="blog_posts",
    )
    reading_minutes = models.PositiveSmallIntegerField(default=3)

    seo = GenericRelation("seo.SeoMeta")

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["category", "status"]),
        ]

    def save(self, *args, **kwargs):
        # Sanitize rich-text HTML at write time (stored-XSS defense). Applies to
        # every write path: Django Admin, data import, and any future API.
        self.body = sanitize_html(self.body)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title

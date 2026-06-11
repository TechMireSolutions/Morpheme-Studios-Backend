"""Projects = the portfolio, the core marketing asset (architecture §2.2)."""
from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import PublishableModel


class ProjectCategory(models.Model):
    key = models.SlugField(max_length=60, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "label"]
        verbose_name_plural = "Project categories"

    def __str__(self) -> str:
        return self.label


class Project(PublishableModel):
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    category = models.ForeignKey(
        ProjectCategory, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="projects",
    )
    type = models.CharField(max_length=120, blank=True)
    status_label = models.CharField(max_length=120, blank=True, help_text="e.g. Completed, In progress")
    excerpt = models.CharField(max_length=400, blank=True)
    description = models.TextField(blank=True)
    services = models.JSONField(default=list, blank=True, help_text="Service tags for this project")

    cover = models.ForeignKey(
        "media.Media", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    is_featured = models.BooleanField(default=False)
    featured_order = models.PositiveIntegerField(default=0)

    seo = GenericRelation("seo.SeoMeta")

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["category", "status"]),
            models.Index(
                fields=["featured_order"],
                name="proj_featured_idx",
                condition=models.Q(is_featured=True),
            ),
        ]

    def __str__(self) -> str:
        return self.title


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="gallery")
    media = models.ForeignKey("media.Media", on_delete=models.CASCADE, related_name="+")
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.project.slug} image #{self.sort_order}"

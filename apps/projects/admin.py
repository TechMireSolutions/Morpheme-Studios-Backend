from __future__ import annotations

from django.contrib import admin

from apps.seo.admin import SeoMetaInline

from .models import Project, ProjectCategory, ProjectImage


@admin.register(ProjectCategory)
class ProjectCategoryAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "sort_order")
    list_editable = ("sort_order",)
    prepopulated_fields = {"key": ("label",)}


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    autocomplete_fields = ("media",)
    ordering = ("sort_order",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "year", "status", "is_featured", "featured_order", "published_at")
    list_filter = ("status", "category", "is_featured", "year")
    list_editable = ("is_featured", "featured_order")
    search_fields = ("title", "location", "excerpt", "description")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("cover",)
    date_hierarchy = "published_at"
    inlines = [ProjectImageInline, SeoMetaInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "type", "status_label")}),
        ("Details", {"fields": ("location", "year", "excerpt", "description", "services")}),
        ("Media & feature", {"fields": ("cover", "is_featured", "featured_order")}),
        ("Publishing", {"fields": ("status", "published_at")}),
    )

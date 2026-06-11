from __future__ import annotations

from django.contrib import admin

from apps.seo.admin import SeoMetaInline

from .models import BlogCategory, BlogPost, Tag


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("label", "slug")
    prepopulated_fields = {"slug": ("label",)}
    search_fields = ("label",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("label", "slug")
    prepopulated_fields = {"slug": ("label",)}
    search_fields = ("label",)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "status", "published_at", "reading_minutes")
    list_filter = ("status", "category", "tags")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("cover", "category", "author")
    filter_horizontal = ("tags",)
    date_hierarchy = "published_at"
    inlines = [SeoMetaInline]

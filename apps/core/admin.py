from __future__ import annotations

from django.contrib import admin

from .models import Office, Page, RedirectRule, SiteSetting


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ("city", "country", "phone", "sort_order")
    list_editable = ("sort_order",)
    search_fields = ("city", "country")


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
    search_fields = ("key",)


@admin.register(RedirectRule)
class RedirectRuleAdmin(admin.ModelAdmin):
    list_display = ("from_path", "to_path", "status_code", "is_active")
    list_filter = ("status_code", "is_active")
    search_fields = ("from_path", "to_path")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("key", "title")
    prepopulated_fields = {"key": ("title",)}

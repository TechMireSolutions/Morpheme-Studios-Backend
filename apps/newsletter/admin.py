from __future__ import annotations

from django.contrib import admin

from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "status", "source", "confirmed_at", "created_at")
    list_filter = ("status", "source", "created_at")
    search_fields = ("email",)
    readonly_fields = ("confirm_token", "confirmed_at", "unsubscribed_at", "ip_address", "created_at")

    def has_add_permission(self, request) -> bool:
        return False

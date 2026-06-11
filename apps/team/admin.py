from __future__ import annotations

from django.contrib import admin

from .models import TeamMember


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "status", "sort_order")
    list_editable = ("sort_order",)
    list_filter = ("status",)
    search_fields = ("name", "role")
    autocomplete_fields = ("photo",)

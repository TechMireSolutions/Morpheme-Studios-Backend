from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import JobApplication, JobOpening


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ("title", "place", "employment_type", "is_open", "status", "closes_at")
    list_filter = ("status", "is_open", "employment_type")
    search_fields = ("title", "place")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    """Applications are records, not editable content. Only the pipeline
    status and assignee may be changed."""

    list_display = ("full_name", "email", "applying_for", "opening", "status", "assigned_to", "created_at")
    list_filter = ("status", "opening", "created_at")
    search_fields = ("first_name", "last_name", "email", "applying_for")
    autocomplete_fields = ("assigned_to",)
    date_hierarchy = "created_at"
    readonly_fields = (
        "opening", "first_name", "last_name", "gender", "date_of_birth", "nationality",
        "country_of_residence", "home_address", "email", "phone", "field_of_expertise",
        "applying_for", "education", "experience_range", "cv_link", "portfolio_link",
        "cover_letter_link", "terms_accepted", "terms_accepted_at", "source",
        "ip_address", "user_agent", "created_at",
    )
    fields = ("status", "assigned_to", *readonly_fields)

    @admin.display(description="Name")
    def full_name(self, obj: JobApplication) -> str:
        return f"{obj.first_name} {obj.last_name}"

    def _file_link(self, media, label):
        if not media:
            return "—"
        return format_html('<span title="Download via admin API signed URL">{} (private)</span>', label)

    @admin.display(description="CV")
    def cv_link(self, obj):
        return self._file_link(obj.cv, "CV")

    @admin.display(description="Portfolio")
    def portfolio_link(self, obj):
        return self._file_link(obj.portfolio, "Portfolio")

    @admin.display(description="Cover letter")
    def cover_letter_link(self, obj):
        return self._file_link(obj.cover_letter, "Cover letter")

    def has_add_permission(self, request) -> bool:
        return False

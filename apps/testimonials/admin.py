from __future__ import annotations

from django.contrib import admin

from .models import Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("author_name", "company", "rating", "status", "sort_order")
    list_editable = ("sort_order",)
    list_filter = ("status", "rating")
    search_fields = ("author_name", "company", "quote")
    autocomplete_fields = ("avatar",)

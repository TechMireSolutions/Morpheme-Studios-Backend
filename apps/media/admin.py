from django.contrib import admin
from apps.media.models import Media

@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("original_name", "type", "is_private", "created_at")
    list_filter = ("type", "is_private", "created_at")
    search_fields = ("original_name", "alt_text")

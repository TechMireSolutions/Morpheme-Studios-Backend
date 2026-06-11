from __future__ import annotations

from rest_framework import serializers

from .models import Office, Page


class OfficeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Office
        fields = ("id", "city", "country", "address_lines", "phone", "email",
                  "latitude", "longitude", "sort_order")


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ("key", "title", "blocks", "updated_at")

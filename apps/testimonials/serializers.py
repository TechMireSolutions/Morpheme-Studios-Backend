from __future__ import annotations

from rest_framework import serializers

from apps.media.serializers import MediaSerializer

from .models import Testimonial


class TestimonialSerializer(serializers.ModelSerializer):
    avatar = MediaSerializer()

    class Meta:
        model = Testimonial
        fields = ("id", "author_name", "author_role", "company", "quote", "rating", "avatar")

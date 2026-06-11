from __future__ import annotations

from rest_framework import serializers

from apps.media.serializers import MediaSerializer

from .models import TeamMember


class TeamMemberSerializer(serializers.ModelSerializer):
    photo = MediaSerializer()

    class Meta:
        model = TeamMember
        fields = ("id", "name", "role", "bio", "photo", "sort_order")

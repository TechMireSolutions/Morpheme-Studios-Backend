from __future__ import annotations

from rest_framework import serializers

from apps.media.serializers import MediaSerializer

from .models import Project, ProjectCategory, ProjectImage


class ProjectCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCategory
        fields = ("key", "label", "sort_order")


class ProjectImageSerializer(serializers.ModelSerializer):
    media = MediaSerializer()

    class Meta:
        model = ProjectImage
        fields = ("media", "caption", "sort_order")


class ProjectListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="key", read_only=True)
    cover = MediaSerializer()

    class Meta:
        model = Project
        fields = (
            "slug", "title", "location", "year", "category", "type",
            "status_label", "excerpt", "services", "cover", "is_featured",
        )


class ProjectDetailSerializer(ProjectListSerializer):
    gallery = ProjectImageSerializer(many=True, read_only=True)

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + ("description", "gallery", "published_at")

from __future__ import annotations

from rest_framework import serializers

from apps.media.serializers import MediaSerializer

from .models import BlogCategory, BlogPost, Tag


class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ("slug", "label")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("slug", "label")


class BlogPostListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    tags = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)
    cover = MediaSerializer()
    author = serializers.CharField(source="author.get_full_name", default="", read_only=True)

    class Meta:
        model = BlogPost
        fields = (
            "slug", "title", "excerpt", "cover", "category", "tags",
            "author", "reading_minutes", "published_at",
        )


class BlogPostDetailSerializer(BlogPostListSerializer):
    class Meta(BlogPostListSerializer.Meta):
        fields = BlogPostListSerializer.Meta.fields + ("body",)

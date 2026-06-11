"""Admin CRUD API for Blog posts (RBAC: CanManageContent).

Body HTML is sanitized in BlogPost.save() (nh3), so write access here is XSS-safe.
"""
from __future__ import annotations

from rest_framework import serializers, viewsets

from apps.audit import services as audit
from apps.users.permissions import CanManageContent

from .models import BlogPost


class AdminBlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = (
            "id", "slug", "title", "excerpt", "body", "cover", "category",
            "tags", "author", "reading_minutes", "status", "published_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class AdminBlogPostViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageContent]
    serializer_class = AdminBlogPostSerializer
    filterset_fields = ["status", "category__slug", "tags__slug"]
    search_fields = ["title", "excerpt", "body"]
    ordering_fields = ["published_at", "created_at"]

    def get_queryset(self):
        return BlogPost.objects.select_related("category", "cover", "author").prefetch_related("tags")

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        audit.record(audit.AuditLog.Action.CREATE, target=obj)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit.record(audit.AuditLog.Action.UPDATE, target=obj)

    def perform_destroy(self, instance):
        audit.record(audit.AuditLog.Action.DELETE, target=instance)
        instance.delete()

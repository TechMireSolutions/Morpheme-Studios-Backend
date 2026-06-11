"""Admin CRUD API for Projects (RBAC: CanManageContent). Complements the public
read API and Django Admin for a future custom React dashboard (architecture §7.5)."""
from __future__ import annotations

from rest_framework import serializers, viewsets

from apps.audit import services as audit
from apps.users.permissions import CanManageContent

from .models import Project


class AdminProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            "id", "slug", "title", "location", "year", "category", "type",
            "status_label", "excerpt", "description", "services", "cover",
            "is_featured", "featured_order", "status", "published_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class AdminProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageContent]
    serializer_class = AdminProjectSerializer
    filterset_fields = ["status", "category__key", "is_featured"]
    search_fields = ["title", "excerpt", "description", "location"]
    ordering_fields = ["published_at", "featured_order", "year", "created_at"]

    def get_queryset(self):
        return Project.objects.select_related("category", "cover").all()

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        audit.record(audit.AuditLog.Action.CREATE, target=obj)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit.record(audit.AuditLog.Action.UPDATE, target=obj)

    def perform_destroy(self, instance):
        audit.record(audit.AuditLog.Action.DELETE, target=instance)
        instance.delete()

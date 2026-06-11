"""Admin CRUD API for Team members (RBAC: CanManageContent)."""
from __future__ import annotations

from rest_framework import serializers, viewsets

from apps.audit import services as audit
from apps.users.permissions import CanManageContent

from .models import TeamMember


class AdminTeamMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ("id", "name", "role", "bio", "photo", "sort_order",
                  "status", "published_at", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class AdminTeamMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageContent]
    serializer_class = AdminTeamMemberSerializer
    filterset_fields = ["status"]
    search_fields = ["name", "role"]
    ordering_fields = ["sort_order", "created_at"]

    def get_queryset(self):
        return TeamMember.objects.select_related("photo").all()

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        audit.record(audit.AuditLog.Action.CREATE, target=obj)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit.record(audit.AuditLog.Action.UPDATE, target=obj)

    def perform_destroy(self, instance):
        audit.record(audit.AuditLog.Action.DELETE, target=instance)
        instance.delete()

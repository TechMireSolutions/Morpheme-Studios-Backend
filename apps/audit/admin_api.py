from __future__ import annotations

from rest_framework import mixins, serializers, viewsets

from apps.users.permissions import IsAdminLevel

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.email", default=None, read_only=True)

    class Meta:
        model = AuditLog
        fields = ("id", "actor", "action", "target_type", "target_id",
                  "changes", "ip_address", "created_at")


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminLevel]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor")
    filterset_fields = ["action", "target_type", "actor"]
    search_fields = ["target_type", "target_id", "actor__email"]
    ordering_fields = ["created_at"]

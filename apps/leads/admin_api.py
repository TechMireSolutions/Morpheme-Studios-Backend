"""Admin REST API for the leads pipeline (RBAC-gated). Complements the Django
Admin CMS for a future custom React dashboard (architecture §4/§7.5)."""
from __future__ import annotations

from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit import services as audit
from apps.users.permissions import CanManageLeads

from .models import Lead, LeadNote


class LeadNoteSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = LeadNote
        fields = ("id", "body", "author", "created_at")
        read_only_fields = ("id", "author", "created_at")


class LeadSerializer(serializers.ModelSerializer):
    notes = LeadNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = ("id", "name", "email", "phone", "message", "status", "source",
                  "assigned_to", "spam_score", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "name", "email", "phone", "message", "source",
                            "spam_score", "notes", "created_at", "updated_at")


class AdminLeadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [CanManageLeads]
    serializer_class = LeadSerializer
    filterset_fields = ["status", "assigned_to"]
    search_fields = ["name", "email", "message"]
    ordering_fields = ["created_at", "status"]

    def get_queryset(self):
        return Lead.objects.prefetch_related("notes__author").select_related("assigned_to")

    def perform_update(self, serializer):
        lead = serializer.save()
        audit.record(audit.AuditLog.Action.UPDATE, target=lead,
                     changes={k: serializer.validated_data[k] for k in serializer.validated_data})

    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        lead = self.get_object()
        body = (request.data or {}).get("body", "").strip()
        if not body:
            return Response({"error": {"code": "validation_error", "message": "Note body required."}},
                            status=400)
        note = LeadNote.objects.create(lead=lead, author=request.user, body=body)
        audit.record(audit.AuditLog.Action.CREATE, target=note)
        return Response(LeadNoteSerializer(note).data, status=201)

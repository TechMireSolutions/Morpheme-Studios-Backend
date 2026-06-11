"""Admin REST API for reviewing applications (RBAC-gated). File access only via
short-lived signed URLs — raw private paths are never exposed."""
from __future__ import annotations

from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit import services as audit
from apps.media.signing import make_token
from apps.users.permissions import CanManageApplications

from .models import JobApplication


class AdminApplicationSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()

    class Meta:
        model = JobApplication
        fields = (
            "id", "opening", "first_name", "last_name", "gender", "date_of_birth",
            "nationality", "country_of_residence", "home_address", "email", "phone",
            "field_of_expertise", "applying_for", "education", "experience_range",
            "status", "assigned_to", "files", "created_at",
        )
        read_only_fields = tuple(f for f in fields if f not in {"status", "assigned_to"})

    def get_files(self, obj: JobApplication) -> dict:
        out = {}
        for kind in ("cv", "portfolio", "cover_letter"):
            media = getattr(obj, kind)
            out[kind] = bool(media)
        return out


class AdminApplicationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                              mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [CanManageApplications]
    serializer_class = AdminApplicationSerializer
    filterset_fields = ["status", "opening"]
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = ["created_at", "status"]

    def get_queryset(self):
        return JobApplication.objects.select_related("opening", "assigned_to", "cv", "portfolio", "cover_letter")

    def perform_update(self, serializer):
        app = serializer.save()
        audit.record(audit.AuditLog.Action.UPDATE, target=app)

    @action(detail=True, methods=["get"], url_path=r"files/(?P<kind>cv|portfolio|cover_letter)/signed-url")
    def signed_url(self, request, pk=None, kind=None):
        app = self.get_object()
        media = getattr(app, kind, None)
        if not media:
            return Response({"error": {"code": "not_found", "message": "No such file."}}, status=404)
        from django.conf import settings
        token = make_token(media.id)
        audit.record(audit.AuditLog.Action.UPDATE, target=app,
                     changes={"downloaded": kind})
        return Response({"url": f"/protected/{token}", "expires_in": settings.MEDIA_SIGNED_URL_TTL})

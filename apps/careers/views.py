from __future__ import annotations

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.audit import services as audit
from .models import JobOpening
from .serializers import (
    JobApplicationCreateSerializer,
    JobOpeningDetailSerializer,
    JobOpeningListSerializer,
)
from .tasks import notify_new_application


class JobOpeningViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    lookup_field = "slug"
    pagination_class = None

    def get_queryset(self):
        return JobOpening.objects.published().filter(is_open=True)

    def get_serializer_class(self):
        return JobOpeningDetailSerializer if self.action == "retrieve" else JobOpeningListSerializer


class JobApplicationCreateView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Public multipart application submission (throttled + Turnstile)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = JobApplicationCreateSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "form"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        audit.record(audit.AuditLog.Action.CREATE, target=application,
                     changes={"source": "careers_form"})
        transaction.on_commit(lambda: notify_new_application.delay(application.id))
        return Response(serializer.data, status=status.HTTP_201_CREATED)

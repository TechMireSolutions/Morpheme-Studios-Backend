from __future__ import annotations

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.audit import services as audit
from .serializers import LeadCreateSerializer
from .tasks import notify_new_lead


class LeadCreateView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Public contact form submission (throttled + Turnstile + honeypot)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = LeadCreateSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "form"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()
        audit.record(audit.AuditLog.Action.CREATE, target=lead, changes={"source": "contact_form"})
        transaction.on_commit(lambda: notify_new_lead.delay(lead.id))
        return Response(serializer.data, status=status.HTTP_201_CREATED)

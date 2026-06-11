from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from .models import TeamMember
from .serializers import TeamMemberSerializer


class TeamMemberViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = TeamMemberSerializer
    pagination_class = None

    def get_queryset(self):
        return TeamMember.objects.published().select_related("photo")

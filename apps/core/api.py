"""Public read API for site config: offices, settings (key/value), static pages."""
from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Office, Page, PublishStatus, SiteSetting
from .serializers import OfficeSerializer, PageSerializer


class OfficeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    queryset = Office.objects.all()
    serializer_class = OfficeSerializer
    pagination_class = None


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def settings_view(request):
    """All site settings as a flat {key: value} map."""
    data = {s.key: s.value for s in SiteSetting.objects.all()}
    return Response(data)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def page_detail(request, key: str):
    page = get_object_or_404(Page, key=key, status=PublishStatus.PUBLISHED)
    return Response(PageSerializer(page).data)

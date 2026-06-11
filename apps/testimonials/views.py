from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from .models import Testimonial
from .serializers import TestimonialSerializer


class TestimonialViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = TestimonialSerializer
    pagination_class = None

    def get_queryset(self):
        return Testimonial.objects.published().select_related("avatar")

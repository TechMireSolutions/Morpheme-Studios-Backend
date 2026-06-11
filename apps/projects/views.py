from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import AllowAny

from .models import Project, ProjectCategory
from .serializers import (
    ProjectCategorySerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
)


class ProjectViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Public read-only project API. Only published rows are returned."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {"category__key": ["exact"], "is_featured": ["exact"], "year": ["exact"]}
    search_fields = ["title", "excerpt", "description", "location"]
    ordering_fields = ["published_at", "year", "featured_order"]

    def get_queryset(self):
        return (
            Project.objects.published()
            .select_related("category", "cover")
            .prefetch_related("gallery__media")
        )

    def get_serializer_class(self):
        return ProjectDetailSerializer if self.action == "retrieve" else ProjectListSerializer


class ProjectCategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    queryset = ProjectCategory.objects.all()
    serializer_class = ProjectCategorySerializer
    pagination_class = None

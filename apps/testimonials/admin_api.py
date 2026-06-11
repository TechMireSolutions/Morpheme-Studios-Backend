"""Admin CRUD API for Testimonials (RBAC: CanManageContent)."""
from __future__ import annotations

from rest_framework import serializers, viewsets

from apps.audit import services as audit
from apps.users.permissions import CanManageContent

from .models import Testimonial


class AdminTestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ("id", "author_name", "author_role", "company", "quote", "rating",
                  "avatar", "sort_order", "status", "published_at", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class AdminTestimonialViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageContent]
    serializer_class = AdminTestimonialSerializer
    filterset_fields = ["status", "rating"]
    search_fields = ["author_name", "company", "quote"]
    ordering_fields = ["sort_order", "created_at"]

    def get_queryset(self):
        return Testimonial.objects.select_related("avatar").all()

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        audit.record(audit.AuditLog.Action.CREATE, target=obj)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit.record(audit.AuditLog.Action.UPDATE, target=obj)

    def perform_destroy(self, instance):
        audit.record(audit.AuditLog.Action.DELETE, target=instance)
        instance.delete()

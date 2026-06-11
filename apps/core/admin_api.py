"""Admin dashboard KPIs (architecture §4). Cached briefly in Redis."""
from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.users.permissions import IsStaff


@api_view(["GET"])
@permission_classes([IsStaff])
def dashboard_stats(request):
    cached = cache.get("dashboard_stats")
    if cached:
        return Response(cached)

    from apps.blog.models import BlogPost
    from apps.careers.models import JobApplication
    from apps.core.models import PublishStatus
    from apps.leads.models import Lead
    from apps.newsletter.models import Subscriber
    from apps.projects.models import Project

    now = timezone.now()
    last7 = now - timedelta(days=7)
    last30 = now - timedelta(days=30)

    data = {
        "leads": {
            "new_7d": Lead.objects.filter(created_at__gte=last7).count(),
            "new_30d": Lead.objects.filter(created_at__gte=last30).count(),
            "open": Lead.objects.exclude(status__in=["won", "lost"]).count(),
        },
        "applications": {
            "new_7d": JobApplication.objects.filter(created_at__gte=last7).count(),
            "new_30d": JobApplication.objects.filter(created_at__gte=last30).count(),
        },
        "content": {
            "projects_published": Project.objects.filter(status=PublishStatus.PUBLISHED).count(),
            "projects_draft": Project.objects.filter(status=PublishStatus.DRAFT).count(),
            "posts_published": BlogPost.objects.filter(status=PublishStatus.PUBLISHED).count(),
            "posts_draft": BlogPost.objects.filter(status=PublishStatus.DRAFT).count(),
        },
        "newsletter": {
            "confirmed": Subscriber.objects.filter(status="confirmed").count(),
            "pending": Subscriber.objects.filter(status="pending").count(),
        },
    }
    cache.set("dashboard_stats", data, 60)
    return Response(data)

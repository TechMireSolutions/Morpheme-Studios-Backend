"""Seed representative content so the public API and admin are demonstrable.

Idempotent (uses get_or_create / update_or_create). Categories mirror the
frontend `data/projects.js`. A one-to-one import of every legacy record from the
Vite data modules is a separate follow-up script.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.blog.models import BlogCategory, BlogPost
from apps.core.models import Office, Page, PublishStatus, SiteSetting
from apps.projects.models import Project, ProjectCategory
from apps.team.models import TeamMember
from apps.testimonials.models import Testimonial

User = get_user_model()

CATEGORIES = [
    ("architecture", "Architecture"),
    ("interior", "Interior Design"),
    ("residential", "Residential"),
    ("retail", "Retail & Commercial"),
    ("arts", "Arts & Design"),
    ("competition", "Competition"),
]

OFFICES = [
    {"city": "London", "country": "United Kingdom", "sort_order": 0},
    {"city": "Ras Al Khaimah", "country": "United Arab Emirates", "sort_order": 1},
    {"city": "Karachi", "country": "Pakistan", "sort_order": 2},
]


class Command(BaseCommand):
    help = "Seed representative demo content."

    def handle(self, *args, **options):
        now = timezone.now()

        admin, created = User.objects.get_or_create(
            email="admin@morphemestudios.com",
            defaults={"full_name": "Studio Admin", "role": "super_admin",
                      "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("ChangeMe!2026")
            admin.save()
            self.stdout.write(self.style.WARNING("Created admin@morphemestudios.com / ChangeMe!2026"))

        cats = {}
        for i, (key, label) in enumerate(CATEGORIES):
            cats[key], _ = ProjectCategory.objects.update_or_create(
                key=key, defaults={"label": label, "sort_order": i})

        Project.objects.update_or_create(
            slug="pynnacles-close-residences",
            defaults={
                "title": "Pynnacles Close Residences",
                "location": "London, United Kingdom",
                "year": 2024,
                "category": cats["residential"],
                "type": "Residential",
                "status_label": "Completed",
                "excerpt": "A terrace of light-filled homes that negotiate density with generosity.",
                "description": "Pynnacles Close reimagines suburban density as something quietly luxurious.",
                "services": ["Architecture", "Interior Design", "Landscape"],
                "is_featured": True,
                "featured_order": 1,
                "status": PublishStatus.PUBLISHED,
                "published_at": now,
                "created_by": admin,
            },
        )

        cat, _ = BlogCategory.objects.get_or_create(slug="insights", defaults={"label": "Insights"})
        BlogPost.objects.update_or_create(
            slug="designing-for-density",
            defaults={
                "title": "Designing for Density",
                "excerpt": "How restraint and daylight turn tight sites into generous homes.",
                "body": "<p>Full article body managed in the CMS.</p>",
                "category": cat,
                "author": admin,
                "reading_minutes": 5,
                "status": PublishStatus.PUBLISHED,
                "published_at": now,
                "created_by": admin,
            },
        )

        for i, name in enumerate(["Studio Principal", "Design Director", "Project Architect"]):
            TeamMember.objects.update_or_create(
                name=f"Team Member {i + 1}",
                defaults={"role": name, "sort_order": i,
                          "status": PublishStatus.PUBLISHED, "published_at": now},
            )

        Testimonial.objects.update_or_create(
            author_name="A. Client",
            defaults={"company": "Private Residence", "quote": "An exceptional studio to work with.",
                      "rating": 5, "status": PublishStatus.PUBLISHED, "published_at": now},
        )

        for o in OFFICES:
            Office.objects.update_or_create(city=o["city"], defaults=o)

        SiteSetting.objects.update_or_create(
            key="mission",
            defaults={"value": {"text": "Architecture & design that negotiates density with generosity."}},
        )

        Page.objects.update_or_create(
            key="terms",
            defaults={"title": "Terms", "blocks": {"sections": []},
                      "status": PublishStatus.PUBLISHED, "published_at": now},
        )

        self.stdout.write(self.style.SUCCESS("Seed complete."))

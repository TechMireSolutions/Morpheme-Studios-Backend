"""Careers: openings (CMS-managed) + applications (system-generated, PII +
private file uploads). Applications are read-only in admin; files reachable
only via short-lived signed URLs (security §6)."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import PublishableModel


class JobOpening(PublishableModel):
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=200)
    place = models.CharField(max_length=200, blank=True)
    employment_type = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    requirements = models.JSONField(default=list, blank=True)
    is_open = models.BooleanField(default=True)
    closes_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class JobApplication(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        SCREENING = "screening", "Screening"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Rejected"

    opening = models.ForeignKey(
        JobOpening, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="applications",
        help_text="Null = speculative application",
    )

    # Applicant PII
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    gender = models.CharField(max_length=40, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=120, blank=True)
    country_of_residence = models.CharField(max_length=120, blank=True)
    home_address = models.TextField(blank=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    field_of_expertise = models.CharField(max_length=200, blank=True)
    applying_for = models.CharField(max_length=200, blank=True)
    education = models.TextField(blank=True)
    experience_range = models.CharField(max_length=80, blank=True)

    # Private uploads (PDF only). is_private=True on each Media.
    cv = models.ForeignKey("media.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    portfolio = models.ForeignKey("media.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cover_letter = models.ForeignKey("media.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_applications",
    )
    source = models.CharField(max_length=80, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["opening"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(terms_accepted=True), name="application_terms_required"),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}>"

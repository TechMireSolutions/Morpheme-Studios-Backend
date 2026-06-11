"""Newsletter subscribers with double opt-in (architecture §7.2)."""
from __future__ import annotations

import secrets

from django.db import models


def _token() -> str:
    return secrets.token_urlsafe(32)


class Subscriber(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"

    email = models.EmailField(unique=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING, db_index=True)
    confirm_token = models.CharField(max_length=64, default=_token, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=80, blank=True, default="site")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

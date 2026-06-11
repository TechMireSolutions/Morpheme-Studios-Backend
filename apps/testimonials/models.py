from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import PublishableModel


class Testimonial(PublishableModel):
    author_name = models.CharField(max_length=200)
    author_role = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    quote = models.TextField()
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    avatar = models.ForeignKey(
        "media.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__isnull=True) | models.Q(rating__gte=1, rating__lte=5),
                name="testimonial_rating_range",
            )
        ]

    def __str__(self) -> str:
        return f"{self.author_name}"

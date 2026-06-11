from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.core.services.turnstile import verify_turnstile
from apps.media.services import store_private_upload

from .models import JobApplication, JobOpening


class JobOpeningListSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobOpening
        fields = ("slug", "title", "place", "employment_type", "is_open", "closes_at")


class JobOpeningDetailSerializer(JobOpeningListSerializer):
    class Meta(JobOpeningListSerializer.Meta):
        fields = JobOpeningListSerializer.Meta.fields + ("description", "requirements")


class JobApplicationCreateSerializer(serializers.ModelSerializer):
    cv = serializers.FileField(write_only=True)
    portfolio = serializers.FileField(write_only=True, required=False, allow_null=True)
    cover_letter = serializers.FileField(write_only=True, required=False, allow_null=True)
    turnstile_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = JobApplication
        fields = (
            "opening", "first_name", "last_name", "gender", "date_of_birth",
            "nationality", "country_of_residence", "home_address", "email", "phone",
            "field_of_expertise", "applying_for", "education", "experience_range",
            "terms_accepted", "cv", "portfolio", "cover_letter", "turnstile_token",
        )

    def validate_terms_accepted(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("You must accept the terms to apply.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        ip = request.META.get("REMOTE_ADDR") if request else None
        if not verify_turnstile(attrs.get("turnstile_token"), ip):
            raise serializers.ValidationError({"turnstile_token": "Spam check failed."})
        return attrs

    def create(self, validated):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        files = {k: validated.pop(k, None) for k in ("cv", "portfolio", "cover_letter")}
        validated.pop("turnstile_token", None)

        media_refs = {}
        try:
            for key, f in files.items():
                if f is not None:
                    media_refs[key] = store_private_upload(f, uploaded_by=actor)
        except DjangoValidationError as exc:
            # Surface file errors as field errors.
            raise serializers.ValidationError({"cv": exc.messages}) from exc

        application = JobApplication.objects.create(
            **validated,
            cv=media_refs.get("cv"),
            portfolio=media_refs.get("portfolio"),
            cover_letter=media_refs.get("cover_letter"),
            terms_accepted_at=timezone.now(),
            source="careers_form",
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:512] if request else ""),
        )
        return application

    def to_representation(self, instance):
        return {"id": instance.id, "status": "received"}

from __future__ import annotations

from rest_framework import serializers

from apps.core.services.turnstile import verify_turnstile

from .models import Lead


class LeadCreateSerializer(serializers.ModelSerializer):
    turnstile_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Honeypot: bots fill hidden fields; humans never do.
    company_website = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Lead
        fields = ("name", "email", "phone", "message", "turnstile_token", "company_website")

    def validate(self, attrs):
        if attrs.get("company_website"):
            raise serializers.ValidationError("Spam detected.")
        request = self.context.get("request")
        ip = request.META.get("REMOTE_ADDR") if request else None
        if not verify_turnstile(attrs.get("turnstile_token"), ip):
            raise serializers.ValidationError({"turnstile_token": "Spam check failed."})
        return attrs

    def create(self, validated):
        validated.pop("turnstile_token", None)
        validated.pop("company_website", None)
        request = self.context.get("request")
        return Lead.objects.create(
            **validated,
            source="contact_form",
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:512] if request else ""),
        )

    def to_representation(self, instance):
        return {"id": instance.id, "status": "received"}

from __future__ import annotations

from rest_framework import serializers

from apps.core.services.turnstile import verify_turnstile



class SubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    turnstile_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get("request")
        ip = request.META.get("REMOTE_ADDR") if request else None
        if not verify_turnstile(attrs.get("turnstile_token"), ip):
            raise serializers.ValidationError({"turnstile_token": "Spam check failed."})
        return attrs


class UnsubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("token"):
            raise serializers.ValidationError("Provide an email or token.")
        return attrs

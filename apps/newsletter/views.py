from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Subscriber
from .serializers import SubscribeSerializer, UnsubscribeSerializer
from .tasks import send_confirmation_email


class FormThrottle(ScopedRateThrottle):
    scope = "form"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([FormThrottle])
def subscribe(request):
    serializer = SubscribeSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].lower()

    sub, created = Subscriber.objects.get_or_create(
        email=email,
        defaults={"ip_address": request.META.get("REMOTE_ADDR"), "source": "site"},
    )
    if sub.status == Subscriber.Status.CONFIRMED:
        return Response({"status": "already_subscribed"})
    if sub.status == Subscriber.Status.UNSUBSCRIBED:
        sub.status = Subscriber.Status.PENDING
        sub.save(update_fields=["status"])
    transaction.on_commit(lambda: send_confirmation_email.delay(sub.id))
    # Always return the same message to avoid email enumeration.
    return Response({"status": "confirmation_sent"}, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def confirm(request):
    token = request.query_params.get("token", "")
    sub = Subscriber.objects.filter(confirm_token=token).first()
    if not sub:
        return Response({"error": {"code": "not_found", "message": "Invalid token."}},
                        status=status.HTTP_404_NOT_FOUND)
    if sub.status != Subscriber.Status.CONFIRMED:
        sub.status = Subscriber.Status.CONFIRMED
        sub.confirmed_at = timezone.now()
        sub.save(update_fields=["status", "confirmed_at"])
    return Response({"status": "confirmed"})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([FormThrottle])
def unsubscribe(request):
    serializer = UnsubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    qs = Subscriber.objects.all()
    sub = (qs.filter(confirm_token=data["token"]).first() if data.get("token")
           else qs.filter(email=data["email"].lower()).first())
    if sub:
        sub.status = Subscriber.Status.UNSUBSCRIBED
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=["status", "unsubscribed_at"])
    return Response({"status": "unsubscribed"})

"""Background tasks for newsletter (run by the Celery worker; eager in dev/tests)."""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("apps")


@shared_task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def send_confirmation_email(self, subscriber_id: int) -> None:
    from .models import Subscriber

    try:
        sub = Subscriber.objects.get(pk=subscriber_id)
    except Subscriber.DoesNotExist:
        return
    # Idempotency: only the pending state needs a confirmation email. If a retry
    # or duplicate delivery fires after the user already confirmed/unsubscribed,
    # do nothing.
    if sub.status != Subscriber.Status.PENDING:
        return
    confirm_url = f"{settings.SITE_URL}/newsletter/confirm?token={sub.confirm_token}"
    try:
        send_mail(
            "Confirm your subscription",
            f"Please confirm your subscription to Morpheme Studios:\n\n{confirm_url}\n",
            settings.DEFAULT_FROM_EMAIL,
            [sub.email],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Newsletter confirmation email failed (will retry): %s", exc)
        raise self.retry(exc=exc)

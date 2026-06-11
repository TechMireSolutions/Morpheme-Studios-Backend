"""Background tasks for leads (run by the Celery worker; eager in dev/tests)."""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("apps")


@shared_task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def notify_new_lead(self, lead_id: int) -> None:
    from .models import Lead

    try:
        lead = Lead.objects.get(pk=lead_id)
    except Lead.DoesNotExist:
        return
    subject = f"New enquiry from {lead.name}"
    body = (
        f"Name: {lead.name}\nEmail: {lead.email}\nPhone: {lead.phone or '-'}\n\n"
        f"Message:\n{lead.message}\n\n"
        f"Manage: {settings.API_URL}/admin/leads/lead/{lead.id}/change/"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.LEADS_NOTIFY_EMAIL])
    except Exception as exc:  # noqa: BLE001 - retry transient SMTP failures
        logger.warning("Lead notification email failed (will retry): %s", exc)
        raise self.retry(exc=exc)

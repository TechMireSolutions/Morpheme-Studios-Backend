"""Background tasks for careers (run by the Celery worker; eager in dev/tests)."""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("apps")


@shared_task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def notify_new_application(self, application_id: int) -> None:
    from .models import JobApplication

    try:
        app = JobApplication.objects.get(pk=application_id)
    except JobApplication.DoesNotExist:
        return
    subject = f"New job application: {app.first_name} {app.last_name}"
    body = (
        f"A new application was received.\n\n"
        f"Name: {app.first_name} {app.last_name}\n"
        f"Email: {app.email}\n"
        f"Applying for: {app.applying_for or (app.opening.title if app.opening else 'Speculative')}\n"
        f"Review in admin: {settings.API_URL}/admin/careers/jobapplication/{app.id}/change/"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.LEADS_NOTIFY_EMAIL])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Application notification email failed (will retry): %s", exc)
        raise self.retry(exc=exc)

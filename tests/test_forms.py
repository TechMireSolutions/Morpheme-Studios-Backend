from __future__ import annotations


import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


# ---- Contact / leads ----
def test_lead_valid_submission_persists_and_audits(api):
    from apps.audit.models import AuditLog
    from apps.leads.models import Lead
    r = api.post("/api/v1/leads", {"name": "Jane", "email": "j@x.com", "message": "Hi"}, format="json")
    assert r.status_code == 201
    assert Lead.objects.filter(email="j@x.com").exists()
    assert AuditLog.objects.filter(action="create", target_type="Lead").exists()


def test_lead_missing_fields_400(api):
    r = api.post("/api/v1/leads", {"name": "Jane"}, format="json")
    assert r.status_code == 400
    assert "email" in r.data["error"]["fields"]


def test_lead_invalid_email_400(api):
    r = api.post("/api/v1/leads", {"name": "J", "email": "not-an-email", "message": "x"}, format="json")
    assert r.status_code == 400


def test_lead_honeypot_blocks_spam(api):
    from apps.leads.models import Lead
    r = api.post("/api/v1/leads",
                 {"name": "Bot", "email": "b@x.com", "message": "spam", "company_website": "http://x"},
                 format="json")
    assert r.status_code == 400
    assert not Lead.objects.filter(email="b@x.com").exists()


# ---- Careers / applications ----
def _pdf(name="cv.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 body", content_type="application/pdf")


def test_application_valid(api):
    from apps.careers.models import JobApplication
    r = api.post("/api/v1/careers/applications", {
        "first_name": "Ada", "last_name": "L", "email": "ada@x.com",
        "terms_accepted": "true", "cv": _pdf(),
    }, format="multipart")
    assert r.status_code == 201
    app = JobApplication.objects.get(email="ada@x.com")
    assert app.cv.is_private is True


def test_application_fake_pdf_rejected(api):
    bad = SimpleUploadedFile("evil.pdf", b"<?php ?>", content_type="application/pdf")
    r = api.post("/api/v1/careers/applications", {
        "first_name": "X", "last_name": "Y", "email": "x@y.com",
        "terms_accepted": "true", "cv": bad,
    }, format="multipart")
    assert r.status_code == 400


def test_application_requires_terms(api):
    r = api.post("/api/v1/careers/applications", {
        "first_name": "X", "last_name": "Y", "email": "x@y.com",
        "terms_accepted": "false", "cv": _pdf(),
    }, format="multipart")
    assert r.status_code == 400


def test_application_oversized_rejected(api, settings):
    settings.MAX_UPLOAD_BYTES = 10  # tiny cap for the test
    r = api.post("/api/v1/careers/applications", {
        "first_name": "X", "last_name": "Y", "email": "big@y.com",
        "terms_accepted": "true", "cv": _pdf(),
    }, format="multipart")
    assert r.status_code == 400


# ---- Newsletter ----
def test_newsletter_double_optin_flow(api):
    from apps.newsletter.models import Subscriber
    r = api.post("/api/v1/newsletter/subscribe", {"email": "n@x.com"}, format="json")
    assert r.status_code == 202
    sub = Subscriber.objects.get(email="n@x.com")
    assert sub.status == "pending"
    c = api.get(f"/api/v1/newsletter/confirm?token={sub.confirm_token}")
    assert c.status_code == 200
    sub.refresh_from_db()
    assert sub.status == "confirmed"


def test_newsletter_duplicate_no_crash(api):
    api.post("/api/v1/newsletter/subscribe", {"email": "dup@x.com"}, format="json")
    r = api.post("/api/v1/newsletter/subscribe", {"email": "dup@x.com"}, format="json")
    assert r.status_code in (202, 200)


def test_newsletter_unsubscribe(api):
    from apps.newsletter.models import Subscriber
    api.post("/api/v1/newsletter/subscribe", {"email": "u@x.com"}, format="json")
    r = api.post("/api/v1/newsletter/unsubscribe", {"email": "u@x.com"}, format="json")
    assert r.status_code == 200
    assert Subscriber.objects.get(email="u@x.com").status == "unsubscribed"

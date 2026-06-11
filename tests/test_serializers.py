from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_media_serializer_hides_private_url():
    from apps.media.models import Media
    from apps.media.serializers import MediaSerializer
    from django.core.files.uploadedfile import SimpleUploadedFile

    priv = Media(type=Media.Type.DOCUMENT, is_private=True,
                 file=SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf"))
    priv.save()
    data = MediaSerializer(priv).data
    assert data["url"] is None  # private files never exposed via read API


def test_project_detail_serializer_shape(published_project):
    from apps.projects.serializers import ProjectDetailSerializer
    data = ProjectDetailSerializer(published_project).data
    assert set(["slug", "title", "gallery", "description", "category"]).issubset(data.keys())
    assert data["category"] == "residential"  # SlugRelatedField -> key


def test_lead_create_serializer_strips_helper_fields():
    from apps.leads.serializers import LeadCreateSerializer
    s = LeadCreateSerializer(data={"name": "A", "email": "a@x.com", "message": "m",
                                   "company_website": "", "turnstile_token": ""})
    assert s.is_valid(), s.errors
    # honeypot + token are write-only helper fields (not real model columns)
    assert s.fields["company_website"].write_only
    assert s.fields["turnstile_token"].write_only
    lead = s.save()
    assert lead.email == "a@x.com" and lead.source == "contact_form"

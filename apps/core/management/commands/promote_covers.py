"""One-off repair for page-scraped legacy covers.

Some legacy project pages exposed no authentic images via the WP REST API or
static HTML — the scraper only captured page chrome (the brand logo and a
"related projects" slider showing OTHER projects' photos). For those entries we
clear the cover (frontend shows the neutral placeholder) rather than mislabel
them with another project's image — real photos can be uploaded later in admin.

Scoped + safe: only the known image-less legacy slugs and literal logo assets
are touched. Curated projects (which intentionally reuse stock photos) are left
alone. Idempotent.

Usage:  python manage.py promote_covers
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.media.models import Media
from apps.projects.models import Project, ProjectImage

# Legacy projects whose live pages had no authentic, extractable imagery.
NO_AUTHENTIC_IMAGE = {
    "bank-alfalah-ltd-branches", "kt-head-office", "pemra-regional-office",
    "pemra-regional-headquarter", "sbawm-mosque", "shishkat-hotel",
    "qinyangligong-industrial-park", "223a-kensington-highstreet",
    "ka-residence", "high-mark-one", "nhs-general-practice-pinner",
}
LOGO_MARKERS = ("cropped-", "morpheme2.0", "favicon", "site-icon")


def _is_logo(media) -> bool:
    if media is None:
        return False
    name = (media.original_name or media.file.name or "").lower()
    return any(m in name for m in LOGO_MARKERS)


class Command(BaseCommand):
    help = "Clear scraped chrome covers for image-less legacy projects; strip logo assets."

    def handle(self, *args, **opts):
        cleared = promoted = pruned = 0

        # 1. Image-less legacy projects -> clear cover + drop their (junk) gallery.
        for p in Project.objects.filter(slug__in=NO_AUTHENTIC_IMAGE):
            if p.cover_id:
                p.cover = None
                p.save(update_fields=["cover"])
                cleared += 1
            n, _ = p.gallery.all().delete()
            pruned += n
            self.stdout.write(f"  cleared {p.slug} (no authentic image; placeholder)")

        # 2. Any remaining logo cover -> promote first non-logo gallery image, else clear.
        for p in Project.objects.filter(cover__isnull=False).select_related("cover"):
            if not _is_logo(p.cover):
                continue
            real = next((gi.media for gi in p.gallery.select_related("media").order_by("sort_order", "id")
                         if not _is_logo(gi.media)), None)
            p.cover = real
            p.save(update_fields=["cover"])
            promoted += 1 if real else 0
            cleared += 0 if real else 1

        # 3. Strip logo images from every gallery + delete orphaned logo media.
        for gi in ProjectImage.objects.select_related("media"):
            if _is_logo(gi.media):
                gi.delete(); pruned += 1
        orphans = 0
        for m in Media.objects.all():
            if _is_logo(m) and not ProjectImage.objects.filter(media=m).exists() \
                    and not Project.objects.filter(cover=m).exists():
                m.delete(); orphans += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done: cleared={cleared}, promoted={promoted}, gallery rows pruned={pruned}, orphan logos deleted={orphans}"))

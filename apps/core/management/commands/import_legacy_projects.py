"""Surgically migrate genuine historical projects from the legacy WordPress site
(morphemestudios.com) into PostgreSQL — spam-free, idempotent, self-hosted media.

Pulls the projects custom-post-type via the WP REST API (server-side), downloads
featured + inline images into backend media, and:
  * CREATES 14 missing projects (13 verified-new + Pynnacles Grove, kept distinct),
  * MERGES 3 name-variants into existing records (adds legacy images, no overwrite).

Idempotent: upsert by slug; Media deduped by filename; gallery images deduped.
Blog is intentionally NOT touched (legacy blog is 100% spam).

Usage:  python manage.py import_legacy_projects
"""
from __future__ import annotations

import html
import json
import re
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags

from apps.media.models import Media
from apps.projects.models import Project, ProjectCategory, ProjectImage

WP_API = "https://morphemestudios.com/wp-json/wp/v2/projects?per_page=100&_embed=1"

# legacy slug -> category key (resolves "(uncategorised)" by discipline)
CREATE = {
    "bank-alfalah-ltd-branches": "retail",
    "kt-head-office": "interior",
    "pemra-regional-office": "architecture",
    "pemra-regional-headquarter": "architecture",
    "sbawm-mosque": "architecture",
    "shishkat-hotel": "architecture",
    "qinyangligong-industrial-park": "architecture",
    "dha-convention-centre": "architecture",
    "223a-kensington-highstreet": "interior",
    "ka-residence": "residential",
    "high-mark-one": "architecture",
    "nhs-general-practice-pinner": "architecture",
    "darulsehat-hospital-liaquat-medical-college": "architecture",
    "pynnacles-grove-residences": "residential",   # kept SEPARATE from Pynnacles Close
}
# legacy slug -> existing DB slug to enrich (no duplicate)
MERGE = {
    "national-foods-innovation-centre": "national-foods-excellence-centre",
    "mka-sports-academy": "moin-khan-academy",
    "aesthetics-by-maria": "aesthetics-clinic-kensington",
}


class Command(BaseCommand):
    help = "Import genuine historical projects from the legacy WordPress site."

    def handle(self, *args, **opts):
        self.counts = {"created": 0, "merged": 0, "media": 0, "gallery": 0, "skipped_img": 0}
        self._cache: dict[str, Media] = {}

        items = self._fetch_projects()
        by_slug = {it.get("slug"): it for it in items}
        self.stdout.write(f"Fetched {len(items)} projects from WP REST API.")

        for slug, cat_key in CREATE.items():
            it = by_slug.get(slug)
            if not it:
                self.stderr.write(f"  ! legacy project not found in API: {slug}")
                continue
            self._create(it, cat_key)

        for legacy_slug, db_slug in MERGE.items():
            it = by_slug.get(legacy_slug)
            if it:
                self._merge(it, db_slug)

        self.stdout.write(self.style.SUCCESS(
            "Legacy import complete: " + ", ".join(f"{k}={v}" for k, v in self.counts.items())))

    # ---- WP API ----
    def _fetch_projects(self) -> list:
        req = urllib.request.Request(WP_API, headers={"User-Agent": "Mozilla/5.0 migration"})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed legacy host
            return json.loads(r.read().decode("utf-8"))

    @staticmethod
    def _title(it) -> str:
        return html.unescape(strip_tags(it.get("title", {}).get("rendered", ""))).strip()

    @staticmethod
    def _text(it) -> str:
        return html.unescape(strip_tags(it.get("content", {}).get("rendered", ""))).strip()

    def _featured_url(self, it) -> str | None:
        try:
            return it["_embedded"]["wp:featuredmedia"][0]["source_url"]
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _dedup_uploads(urls) -> list[str]:
        """Dedup WP images by original filename (strip -WxH size suffixes), keep order."""
        seen, out = set(), []
        for u in urls:
            if "/wp-content/uploads/" not in u:
                continue
            low = u.lower()
            # Skip site chrome: WP custom-logo is published as "cropped-*.png".
            if any(x in low for x in ("logo", "favicon", "icon", "placeholder", "cropped-")):
                continue
            base = re.sub(r"-\d+x\d+(?=\.\w+($|\?))", "", u)  # collapse thumbnails to original
            if base not in seen:
                seen.add(base)
                out.append(base)
        return out[:8]

    def _content_image_urls(self, it) -> list[str]:
        raw = it.get("content", {}).get("rendered", "") or ""
        return self._dedup_uploads(re.findall(r'<img[^>]+src="([^"]+)"', raw))

    def _page_image_urls(self, link: str) -> list[str]:
        """Fallback: scrape the rendered project page for page-builder images."""
        if not link:
            return []
        try:
            req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0 migration"})
            with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310 - fixed legacy host
                html_doc = r.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f"  ! page scrape failed ({link[:70]}…): {exc}")
            return []
        urls = re.findall(r'(?:src|data-src|href)="([^"]+\.(?:jpg|jpeg|png|webp))"', html_doc, re.I)
        return self._dedup_uploads(urls)

    # ---- media ----
    def _media(self, url: str, alt: str) -> Media | None:
        if not url:
            return None
        if url in self._cache:
            return self._cache[url]
        key = url.split("/")[-1].split("?")[0][:120] or "legacy.jpg"
        existing = Media.objects.filter(original_name=key, is_private=False).first()
        if existing and existing.file:
            self._cache[url] = existing
            return existing
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 migration"})
            with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310
                raw = r.read()
        except Exception as exc:  # noqa: BLE001 - resilient
            self.stderr.write(f"  ! image fetch failed ({url[:70]}…): {exc}")
            self.counts["skipped_img"] += 1
            return None
        m = Media(type=Media.Type.IMAGE, is_private=False, alt_text=(alt or key)[:255],
                  original_name=key, mime="image/jpeg")
        m.file.save(key, ContentFile(raw), save=True)
        self.counts["media"] += 1
        self._cache[url] = m
        return m

    def _set_gallery(self, project: Project, urls: list[str], alt: str):
        existing_media_ids = set(project.gallery.values_list("media_id", flat=True))
        order = project.gallery.count()
        for u in urls:
            m = self._media(u, alt)
            if m and m.id not in existing_media_ids:
                ProjectImage.objects.create(project=project, media=m, sort_order=order)
                existing_media_ids.add(m.id)
                order += 1
                self.counts["gallery"] += 1

    # ---- create / merge ----
    def _create(self, it, cat_key):
        slug = it["slug"]
        title = self._title(it)
        body = self._text(it)
        imgs = self._content_image_urls(it)
        if not imgs and not self._featured_url(it):
            imgs = self._page_image_urls(it.get("link", ""))   # page-builder fallback
        # Cover = featured image, else first available image.
        cover_url = self._featured_url(it) or (imgs[0] if imgs else None)
        cover = self._media(cover_url, title)
        cat = ProjectCategory.objects.filter(key=cat_key).first()
        obj, _ = Project.objects.update_or_create(
            slug=slug,
            defaults=dict(
                title=title, category=cat, type=(cat.label if cat else ""),
                excerpt=body[:380], description=body, cover=cover,
                status="published", published_at=timezone.now(),
            ),
        )
        gallery = list(imgs)
        fu = self._featured_url(it)
        if fu:
            gallery = [fu] + [g for g in gallery if g != fu]
        self._set_gallery(obj, gallery, title)
        self.counts["created"] += 1

    def _merge(self, it, db_slug):
        obj = Project.objects.filter(slug=db_slug).first()
        if not obj:
            self.stderr.write(f"  ! merge target missing: {db_slug}")
            return
        title = self._title(it)
        # Enrich only: fill empty description; add legacy images to gallery. Never overwrite.
        if not (obj.description or "").strip():
            obj.description = self._text(it)
            obj.excerpt = obj.excerpt or self._text(it)[:380]
            obj.save(update_fields=["description", "excerpt"])
        if not obj.cover:
            obj.cover = self._media(self._featured_url(it), title)
            obj.save(update_fields=["cover"])
        urls = self._content_image_urls(it)
        fu = self._featured_url(it)
        if fu:
            urls = [fu] + [u for u in urls if u != fu]
        self._set_gallery(obj, urls, title)
        self.counts["merged"] += 1

"""Idempotent importer: loads the legacy frontend bundled content into Postgres
so Django Admin + DB become the single source of truth.

Reads a JSON export (produced by the frontend `scripts/export_data.mjs`) and:
  * copies/downloads every referenced image into backend media + Media rows,
  * upserts categories, projects (+gallery), blog posts, team, offices,
    job openings, and stores services/stats/approach/mission in SiteSetting.

Idempotent: re-running upserts by natural key (slug / key / city / name / title)
and never duplicates. Image fetch is resilient — a failed download leaves the
cover null and logs, rather than aborting the import.

Usage:  python manage.py import_content [--file import_data.json]
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from apps.blog.models import BlogCategory, BlogPost
from apps.careers.models import JobOpening
from apps.core.models import Office, PublishStatus, SiteSetting
from apps.media.models import Media
from apps.projects.models import Project, ProjectCategory, ProjectImage
from apps.team.models import TeamMember

FRONTEND_PUBLIC = settings.BASE_DIR.parent / "Morpheme-Studios-Frontend" / "public"


class Command(BaseCommand):
    help = "Idempotently import bundled frontend content into the database."

    def add_arguments(self, parser):
        parser.add_argument("--file", default="import_data.json")

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.is_absolute():
            path = settings.BASE_DIR / path
        if not path.exists():
            raise CommandError(f"Export file not found: {path}. Run frontend scripts/export_data.mjs first.")
        data = json.loads(path.read_text(encoding="utf-8"))

        self._media_cache: dict[str, Media] = {}
        self.counts = {k: 0 for k in (
            "media", "categories", "projects", "gallery", "blog_categories",
            "blog", "team", "offices", "openings", "settings")}

        self._import_categories(data["categories"])
        self._import_projects(data["projects"], set(data.get("featured", [])))
        self._import_blog(data["blog"])
        self._import_team(data["team"])
        self._import_offices(data["offices"])
        self._import_openings(data["jobOpenings"])
        self._import_settings(data)

        self.stdout.write(self.style.SUCCESS("Import complete: " + ", ".join(
            f"{k}={v}" for k, v in self.counts.items())))

    # ---------------- media ----------------
    def _media_key(self, url: str) -> str:
        """Deterministic, idempotent filename key for a given image URL."""
        if url.startswith("/"):
            return Path(url).name
        if "unsplash.com/photo-" in url:
            pid = url.split("photo-")[1].split("?")[0]
            return f"unsplash-{pid}.jpg"
        return slugify(Path(url.split("?")[0]).stem)[:60] + Path(url.split("?")[0]).suffix

    def _get_media(self, url: str, alt: str = "") -> Media | None:
        if not url:
            return None
        if url in self._media_cache:
            return self._media_cache[url]
        key = self._media_key(url)
        existing = Media.objects.filter(original_name=key, is_private=False).first()
        if existing and existing.file:
            self._media_cache[url] = existing
            return existing

        raw = self._fetch_bytes(url)
        if raw is None:
            return None
        media = Media(type=Media.Type.IMAGE, is_private=False,
                      alt_text=(alt or key)[:255], original_name=key,
                      mime="image/webp" if key.endswith(".webp") else "image/jpeg")
        media.file.save(key, ContentFile(raw), save=True)
        self.counts["media"] += 1
        self._media_cache[url] = media
        return media

    def _fetch_bytes(self, url: str) -> bytes | None:
        try:
            if url.startswith("/"):
                local = FRONTEND_PUBLIC / url.lstrip("/")
                if not local.exists():
                    self.stderr.write(f"  ! local asset missing: {local}")
                    return None
                return local.read_bytes()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 import"})
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 - curated image URLs
                return r.read()
        except Exception as exc:  # noqa: BLE001 - resilient: skip image, keep importing
            self.stderr.write(f"  ! image fetch failed ({url[:60]}…): {exc}")
            return None

    # ---------------- content ----------------
    def _import_categories(self, cats):
        for i, c in enumerate(cats):
            if c["key"] == "all":          # UI pseudo-filter, not a real category
                continue
            ProjectCategory.objects.update_or_create(
                key=c["key"], defaults={"label": c["label"], "sort_order": i})
            self.counts["categories"] += 1

    def _import_projects(self, projects, featured):
        for i, p in enumerate(projects):
            cat = ProjectCategory.objects.filter(key=p.get("category")).first()
            year = int(p["year"]) if str(p.get("year", "")).isdigit() else None
            is_feat = p["slug"] in featured
            obj, _ = Project.objects.update_or_create(
                slug=p["slug"],
                defaults=dict(
                    title=p["title"], location=p.get("location", ""), year=year,
                    category=cat, type=p.get("type", ""), status_label=p.get("status", ""),
                    excerpt=p.get("excerpt", ""), description=p.get("description", ""),
                    services=p.get("services", []), cover=self._get_media(p.get("cover", ""), p["title"]),
                    is_featured=is_feat, featured_order=(list(featured).index(p["slug"]) + 1 if is_feat else 0),
                    status=PublishStatus.PUBLISHED, published_at=timezone.now(),
                ),
            )
            # Gallery: rebuild deterministically (idempotent).
            obj.gallery.all().delete()
            for gi, gurl in enumerate(p.get("gallery", [])):
                m = self._get_media(gurl, p["title"])
                if m:
                    ProjectImage.objects.create(project=obj, media=m, sort_order=gi)
                    self.counts["gallery"] += 1
            self.counts["projects"] += 1

    def _import_blog(self, posts):
        for p in posts:
            label = p.get("category", "Insights")
            cat, created = BlogCategory.objects.get_or_create(
                slug=slugify(label), defaults={"label": label})
            if created:
                self.counts["blog_categories"] += 1
            pub = self._parse_date(p.get("date"))
            BlogPost.objects.update_or_create(
                slug=p["slug"],
                defaults=dict(
                    title=p["title"], excerpt=p.get("excerpt", ""),
                    body=f"<p>{p.get('excerpt', '')}</p>", category=cat,
                    cover=self._get_media(p.get("image", ""), p["title"]),
                    reading_minutes=4, status=PublishStatus.PUBLISHED,
                    published_at=pub or timezone.now(),
                ),
            )
            self.counts["blog"] += 1

    def _import_team(self, team):
        for i, m in enumerate(team):
            TeamMember.objects.update_or_create(
                name=m["name"],
                defaults=dict(
                    role=m.get("role", ""), bio=m.get("note", ""),
                    photo=self._get_media(m.get("image", ""), m["name"]),
                    sort_order=i, status=PublishStatus.PUBLISHED, published_at=timezone.now(),
                ),
            )
            self.counts["team"] += 1

    def _import_offices(self, offices):
        for i, o in enumerate(offices):
            Office.objects.update_or_create(
                city=o["city"],
                defaults=dict(country=o.get("country", ""), address_lines=o.get("lines", []),
                              phone=o.get("phone", ""), sort_order=i),
            )
            self.counts["offices"] += 1

    def _import_openings(self, openings):
        for o in openings:
            JobOpening.objects.update_or_create(
                slug=slugify(o["title"]),
                defaults=dict(title=o["title"], place=o.get("place", ""),
                              employment_type=o.get("type", ""), is_open=True,
                              status=PublishStatus.PUBLISHED, published_at=timezone.now()),
            )
            self.counts["openings"] += 1

    def _import_settings(self, data):
        # services/stats/approach -> SiteSetting JSON; resolve service images to media URLs.
        services = []
        for s in data.get("services", []):
            m = self._get_media(s.get("image", ""), s.get("title", ""))
            services.append({"no": s.get("no"), "title": s.get("title"),
                             "blurb": s.get("blurb"), "image": (m.file.url if m else None)})
        for key, value in (("services", services), ("stats", data.get("stats", [])),
                           ("approach", data.get("approach", []))):
            SiteSetting.objects.update_or_create(key=key, defaults={"value": value})
            self.counts["settings"] += 1

    @staticmethod
    def _parse_date(s):
        if not s:
            return None
        for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
            try:
                return timezone.make_aware(datetime.strptime(s, fmt))
            except (ValueError, TypeError):
                continue
        return None

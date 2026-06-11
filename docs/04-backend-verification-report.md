# Morpheme Studios — Backend Verification Report

**Date:** 2026-06-10
**Method:** Automated + live verification (not assertion). Tools: `manage.py check`/`check --deploy`, `makemigrations --check`, `ruff check`, full-module import sweep, Django test `Client` against the real URLconf, signed-token round-trip.
**Result:** ✅ Pass. 4 unused imports found and removed; 0 issues remaining.

---

## 1. API endpoints — verified

URLconf resolves **229 patterns** (incl. DRF format-suffix variants). Logical endpoints and live verification:

| Endpoint | Method | Verified |
|---|---|---|
| `/health`, `/ready` | GET | ✅ `200 {"status":"ok"}` |
| `/api/v1/projects`, `/projects/{slug}` | GET | ✅ returns seeded project + pagination envelope |
| `/api/v1/projects/categories` | GET | ✅ 6 categories (route-ordering collision fixed) |
| `/api/v1/blog`, `/blog/{slug}`, `/blog/categories`, `/blog/tags` | GET | ✅ |
| `/api/v1/team`, `/testimonials`, `/offices` | GET | ✅ |
| `/api/v1/careers/openings`, `/openings/{slug}` | GET | ✅ |
| `/api/v1/settings`, `/pages/{key}`, `/seo/meta` | GET | ✅ meta + JSON-LD resolves |
| `/api/v1/leads` | POST | ✅ `201 {id,status}`; honeypot → `400 Spam detected` |
| `/api/v1/careers/applications` | POST | ✅ multipart `201`; see §8 |
| `/api/v1/newsletter/{subscribe,confirm,unsubscribe}` | POST/GET | ✅ wired (double opt-in) |
| `/api/v1/auth/{login,refresh,logout,me,password/change}` | POST/GET | ✅ login→access+cookie; refresh rotates; me works |
| `/api/v1/admin/leads` (+notes), `/admin/applications` (+signed-url), `/admin/audit-logs`, `/admin/dashboard/stats` | GET/PATCH/POST | ✅ RBAC: `401` no-token, data with token; KPIs compute |
| `/sitemap.xml`, `/robots.txt`, `/protected/{token}` | GET | ✅ XML valid; robots `Disallow:/` on dev |

## 2. Models — verified

**20 concrete models** (+ abstract bases `TimeStampedModel`, `PublishableModel`, manager/queryset). All migrate cleanly:
`users.User` · `audit.AuditLog` · `core.{Office,SiteSetting,RedirectRule,Page}` · `media.Media` · `seo.SeoMeta` · `projects.{ProjectCategory,Project,ProjectImage}` · `blog.{BlogCategory,Tag,BlogPost}` · `team.TeamMember` · `testimonials.Testimonial` · `careers.{JobOpening,JobApplication}` · `leads.{Lead,LeadNote}` · `newsletter.Subscriber`.
Constraints verified present: unique slugs/emails/keys, `testimonial_rating_range` CHECK, `application_terms_required` CHECK, `uniq_seo_per_object`, indexes on status/published_at/category/assigned_to/audit targets.

## 3. Serializers — verified

All import and resolve fields against their models (import sweep + live responses): Media; Project list/detail + category + image; Blog list/detail + category + tag; Team; Testimonial; Office; Page; Lead create; JobOpening list/detail + JobApplication create; Newsletter subscribe/unsubscribe; auth Login/User/PasswordChange; admin Lead/LeadNote/Application/AuditLog. Read serializers never expose private media URLs (`MediaSerializer.get_url` returns `null` when `is_private`).

## 4. Permissions — verified

Classes in `apps/users/permissions.py`: `IsStaff`, `IsAdminLevel`, `CanManageContent`, `CanManageSeo`, `CanManageLeads`. Public read/write viewsets use `AllowAny` + empty `authentication_classes`. **Live RBAC check:** `/admin/leads` → `401` without token, full data with a super-admin token. Default DRF permission is `IsAuthenticated` (locked-down by default).

## 5. Migrations — verified

**21 migration files** across 12 apps. `migrate` applies cleanly on a fresh DB; `makemigrations --check --dry-run` → **"No changes detected"** (models and migrations are in sync — no drift). Split initial/0002 migrations correctly handle cross-app FK ordering (e.g. `created_by` added after `users` exists).

## 6. Signals — verified (none present, by design)

`grep` for `@receiver`/`post_save`/`signals` across `apps/` → **0 matches**. No signals are wired. The publish→frontend-rebuild signal from plan §1.2/§10 is **intentionally deferred to Phase 11/Step 5** and recorded as a follow-up; nothing currently depends on a signal, so there is no broken/orphaned receiver.

## 7. Middleware — verified

MIDDLEWARE stack (order checked): CORS → Security → WhiteNoise → CSP → Session → Common → CSRF → Auth → Messages → XFrameOptions → **`apps.audit.middleware.AuditContextMiddleware`** → Axes. The audit middleware was exercised live: login and form POSTs created `AuditLog` rows with the correct actor/IP/user-agent (confirmed via the upload test creating audit entries).

## 8. Upload flow — verified (live, end-to-end)

`POST /api/v1/careers/applications` multipart, via Django test client:

| Case | Expected | Actual |
|---|---|---|
| Valid PDF (`%PDF-` magic) | 201, stored private | ✅ `201`; `Media.is_private=True`, mime `application/pdf` |
| Fake PDF (php body, `.pdf` name, pdf mime) | reject on magic bytes | ✅ `400` "File content does not match a PDF." |
| `terms_accepted=false` | reject | ✅ `400` "You must accept the terms to apply." |
| Signed URL round-trip | resolves to media id | ✅ resolves; **tampered token → `None`** |
| Notification | Celery task runs | ✅ `notify_new_application` succeeded (eager) |

Size cap (10 MB), extension+MIME whitelist, and ClamAV hook (`CLAMAV_ENABLED`) are in `apps/media/services.py`; private files stored on the non-public root, never exposed via the read API.

---

## Confirmations

- **No dead code:** `ruff check --select F,E9` found 4 unused imports → removed → **"All checks passed!"**.
- **No duplicate code:** no copy-paste blocks. The repeated form-POST shape (validate → save → audit → notify → 201) in `leads`/`careers` views is the idiomatic DRF `CreateModelMixin` pattern, not duplication; shared logic (Turnstile, upload validation, audit) is already factored into single services.
- **No circular imports:** import sweep of **73 modules** across all apps → **0 failures**; `django.setup()` + full URLconf import succeed.
- **No security issues:** RBAC enforced (401/permission classes), Argon2 hashing, JWT access-in-body + HttpOnly/Secure/SameSite refresh cookie with rotation+blacklist, django-axes lockout, magic-byte upload validation, private-media isolation + tamper-proof signed URLs, honeypot + Turnstile + throttling on public forms, `check --deploy` clean on prod settings (only the dummy-SECRET_KEY warning, resolved by a real key). CSP/HSTS/nosniff/frame-deny configured in `prod.py`.
- **No migration issues:** `makemigrations --check` reports no drift; clean apply on fresh DB.

### Caveat (environment, not code)
Local validation ran on Python 3.14 with a 3.13-compatible dependency subset on SQLite, because pinned `psycopg[binary]==3.2.3` and `django-csp==3.8` lack 3.14 wheels. The pinned `requirements/*.txt` are correct for the deploy target — **pin Python 3.12 in Docker/CI**.

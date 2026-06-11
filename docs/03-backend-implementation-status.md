# Morpheme Studios — Phase 10: Backend Implementation Status

**Date:** 2026-06-10
**Status:** Core backend implemented and validated end-to-end on SQLite.
**Companion docs:** [01-audit-and-gap-analysis.md](./01-audit-and-gap-analysis.md) · [02-architecture-and-implementation-plan.md](./02-architecture-and-implementation-plan.md)

This implements the locked plan: Django 5.1 + DRF + (Postgres in prod / SQLite for local), Django Admin as the CMS, JWT auth with HttpOnly refresh cookie, RBAC, Celery + Redis, headless API for the Vite SPA.

## What was built

| Layer | Modules |
|---|---|
| **Foundation** | `apps.core` (abstract `TimeStampedModel`/`PublishableModel`, pagination, uniform error envelope, health/ready probes, Office/SiteSetting/RedirectRule/Page), `apps.users` (email-login custom User + 5 roles + manager + admin), `apps.audit` (AuditLog + thread-local context middleware + `record()` service) |
| **Content / CMS** | `apps.media` (library + private storage + secure upload validation + signed URLs), `apps.seo` (polymorphic SeoMeta + inline), `apps.projects`, `apps.blog`, `apps.team`, `apps.testimonials`, `apps.careers`, `apps.leads`, `apps.newsletter` — all with `ModelAdmin` (25 admin registrations) |
| **Public read API** | `/api/v1/projects`, `/projects/categories`, `/blog`, `/blog/categories`, `/blog/tags`, `/team`, `/testimonials`, `/careers/openings`, `/offices`, `/settings`, `/pages/{key}`, `/seo/meta` |
| **Public write (forms)** | `POST /leads` (honeypot + Turnstile + throttle + email), `POST /careers/applications` (multipart, PDF-only magic-byte validation, ClamAV hook, private storage), newsletter subscribe/confirm/unsubscribe (double opt-in) |
| **Auth** | `POST /auth/login` (access in body, refresh in HttpOnly/Secure/SameSite cookie), `/auth/refresh` (rotate + blacklist), `/auth/logout`, `/auth/me`, `/auth/password/change`; django-axes lockout |
| **Admin API (RBAC)** | `/admin/leads` (+ notes), `/admin/applications` (+ signed file URLs), `/admin/audit-logs`, `/admin/dashboard/stats` |
| **SEO/infra** | `/sitemap.xml`, `/robots.txt` (Disallow on dev/staging), `/protected/{token}` private download via X-Accel-Redirect |

## Validated (smoke-tested live)

- `manage.py check` clean (dev + prod `--deploy`, only the dummy-SECRET_KEY warning).
- `makemigrations --check` → no pending changes; full `migrate` applies cleanly.
- Public reads return seeded data; list pagination + filtering work.
- `POST /leads` persists + returns `{id, status}`; **honeypot rejects spam**.
- JWT login returns access + sets refresh cookie; `/auth/me` and `/auth/refresh` (rotation) work.
- Admin API enforces RBAC (401 without token, data with token); dashboard KPIs compute.

## Local run

```bash
cd Morpheme-Studios-Backend
python -m venv .venv && .venv/Scripts/pip install -r requirements/dev.txt
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_demo        # admin@morphemestudios.com / ChangeMe!2026
.venv/Scripts/python manage.py runserver
```

Dev uses SQLite + LocMemCache + eager Celery automatically when `REDIS_URL`/`DATABASE_URL` are unset, so **no Postgres/Redis needed to run locally**. Set those env vars to use the production-grade stack.

## Environment notes / known follow-ups

- **Python 3.14 on this machine:** `psycopg[binary]==3.2.3` and `django-csp==3.8` have no wheels for 3.14. Local validation used a 3.13-compatible subset on SQLite; the pinned `requirements/*.txt` are correct for the deploy target (Python 3.12/3.13 per Dockerfile). Pin Python 3.12 in CI/Docker.
- **Seed:** `seed_demo` loads representative content + exact project categories. A 1:1 importer for every legacy record in the frontend `src/data/*.js` modules is the remaining data-migration task (Phase 10 step 0 in doc 02 §10).
- **Not yet wired (next phases):** content CRUD over REST (Django Admin covers CMS today per the locked decision); MFA/TOTP endpoints; frontend-rebuild Celery task; `.env.example`; Dockerfiles + compose; test suite (pytest). These are Phases 11–13.

## Next: Phase 11 — frontend integration

Per doc 02 §10: add API client + data hooks, replace hardcoded `data/*.js` imports, add `vite-react-ssg` prerender + react-helmet meta from `/seo/meta`, wire Contact→`/leads` and Careers→`/careers/applications`, add `/blog/:slug` + newsletter UI, fix the Careers-form label a11y issue from audit §5.

# Morpheme Studios — PostgreSQL Validation & End-to-End Report

**Date:** 2026-06-10
**DB:** PostgreSQL **18.4** on `localhost:5433`, database `morpheme_studios`.
**Method:** real execution — migrations, full pytest against Postgres, and live HTTP against the running backend (and Vite dev server). No results are assumed.

---

## 1. Config / wiring fixes (found by execution)

| Issue | Fix |
|---|---|
| `.env.development` had a **doubled prefix**: `DATABASE_URL=DATABASE_URL=postgres://…` (invalid) | Corrected to a single `DATABASE_URL=`. |
| `base.py` only read `.env`; the URL was in `.env.development`, so Django silently fell back to SQLite | `base.py` now reads the first of `$DJANGO_ENV_FILE` → `.env` → `.env.development`. |
| `.env.development` sets `REDIS_URL` but Redis isn't running → cache/throttle 500s, Celery `.delay()` failures | `dev.py` now **probes Redis reachability**; if down, falls back to LocMemCache + eager Celery. |
| Pinned `psycopg[binary]==3.2.3` has no Python-3.14 wheel (this host) | Installed a 3.14-compatible `psycopg` **in the local venv only**; pinned requirements + Docker (Python 3.12) unchanged. |

**Verified target (not SQLite):**
```
ENGINE: django.db.backends.postgresql   NAME: morpheme_studios   HOST: localhost   PORT: 5433
CACHE : LocMemCache (Redis down → graceful fallback)   CELERY_EAGER: True
```

## 2. Migrations & schema (Postgres)
- `migrate` → **all apps applied cleanly** on a fresh Postgres DB.
- `makemigrations --check --dry-run` → **No changes detected** (no model/migration drift).
- Postgres-specific objects confirmed via `pg_indexes` / `pg_constraint`:
  - **Partial index** `proj_featured_idx ... WHERE is_featured` ✅
  - composite index `(status, published_at)` ✅
  - CHECK constraints `testimonial_rating_range`, `application_terms_required` ✅

## 3. Automated suite against PostgreSQL — **42 passed**
`pytest` runs against a real `test_morpheme_studios` database (created/destroyed by pytest-django).
Coverage: models, serializers, RBAC/permissions, public API, forms (incl. honeypot), **uploads + signed-URL round-trip**, auth + refresh rotation. (Up from 39 — added 3 upload/authz regression tests for the bug below.)

## 4. 🐞 Real bug found **and fixed** (the kind that "compiles but fails")
**Protected file download returned HTTP 500** for a valid signed token.
- **Root cause:** private uploads are correctly stored on `PRIVATE_MEDIA_ROOT` (verified on disk: `private-media/private/document/cv_*.pdf`), but the download view read the file through the `FileField`'s **default** storage (`MEDIA_ROOT`), so it couldn't find the file.
- **Fix:** `apps/media/views.py` now resolves private files through `private_storage` (existence check + open + X-Accel-Redirect path), matching where they're written.
- **Regression test added:** `tests/test_uploads.py` (round-trip download + tampered-token 404 + public-id rejected).
- **Re-verified live:** `GET /protected/<signed>` → **200, `%PDF-1.4`**; tampered token → **404**.
> Note: this corrects an over-stated "upload flow verified" in `docs/04` — the earlier check exercised *upload + signed-URL issuance* but not the *actual download*. Now both are verified end-to-end.

Also added production `templates/404.html` + `500.html` (clean error pages).

## 5. Live end-to-end (running backend on Postgres)

| Flow | Result |
|---|---|
| Contact `POST /leads` | ✅ 201; **honeypot** → 400; invalid email → 400 |
| Careers `POST /careers/applications` (multipart) | ✅ 201; **fake-PDF (bad magic)** → 400; file stored **private** |
| Newsletter subscribe | ✅ 202 (double-opt-in pending) |
| Auth login / `/me` / refresh (cookie rotation) | ✅ all work |
| RBAC `admin/leads` | ✅ 200 with token, **401 without** |
| Signed-URL → protected download | ✅ 200 + valid PDF; tampered → 404 |
| SEO `/seo/meta`, `/sitemap.xml`, `/robots.txt` | ✅ correct meta+JSON-LD, valid XML, robots |
| Projects (list/detail/categories), Blog (list/detail), Team, Offices, Settings | ✅ all 200, DB-backed |
| **DB persistence + audit** | leads/applications/subscribers/private-media rows present; **audit actions**: login, create×2, update |
| CORS from `http://localhost:5173` | ✅ `access-control-allow-origin` returned |
| Frontend (Vite dev server :5173) | ✅ serves SPA (HTTP 200) |

## 6. Quality gates
- `pytest` → **42 passed**.
- `ruff check apps config tests --select F,E9` → **All checks passed**.
- `makemigrations --check` → **no drift**.
- Frontend `vite build` → clean (prior phase).

## 7. Remaining blockers (unchanged — infra not present)
- **Redis** not running → dev uses LocMem + eager Celery. For prod-parity Celery/broker testing, start Redis (it's in `docker-compose.yml`).
- **Docker daemon** absent → can't run the full containerized stack / Celery worker as a service here.
- **Headless Chrome** absent → **Lighthouse (Phase G)** and **Playwright E2E (Phase C E2E)** can't execute here.
- **vite-react-ssg prerender (Phase E)** not yet implemented — biggest remaining SEO lever.
- **Content migration (Phase I)** — frontend still uses API-with-bundled-fallback; needs an `import_legacy` command.

## 8. Exact next steps before production launch
1. **Start Redis** (or `docker compose up -d redis`) and re-run the suite with `CELERY_TASK_ALWAYS_EAGER=false` to validate the real broker path.
2. **Bring up the full stack** (`docker compose up -d --build`) on a Docker host; run `migrate` + `seed_demo`; smoke-test through Nginx.
3. **Playwright E2E** for the 6 user journeys against the running stack.
4. **Lighthouse** on the 8 routes; then implement image pipeline + font self-hosting to hit targets.
5. **vite-react-ssg** prerender for crawler-grade SEO (reuses `/seo/meta`).
6. **`import_legacy`** management command → migrate `src/data/*.js` into the CMS → remove frontend fallbacks.
7. Rotate the seeded admin password; set real `DJANGO_SECRET_KEY`, SMTP, Turnstile keys in prod `.env`.

## Minor / noted (non-blocking)
- `RemovedInDjango60Warning` on two `CheckConstraint(check=…)` — switch to `condition=` before Django 6.0 (left as-is now to avoid migration churn).

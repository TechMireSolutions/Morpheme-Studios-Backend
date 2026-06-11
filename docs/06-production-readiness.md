# Morpheme Studios — Phases 12–15: Production Readiness Report

> **⚠️ Superseded (2026-06-10):** the project was simplified to a **plain VPS stack — Django + PostgreSQL + gunicorn + Nginx, no Docker/Redis/Celery/ClamAV.** Background emails now send synchronously; throttling/cache use Django's DB cache. The Docker/compose/Redis instructions below no longer apply — follow **[08-vps-deployment.md](./08-vps-deployment.md)**.

**Date:** 2026-06-10
**Principle:** Nothing below is marked "done" unless it was **executed** in this environment. Items that need infrastructure not present here (Docker daemon, PostgreSQL, headless Chrome) are listed as **blocked-on-infra** with the exact commands to run them on a capable host — not faked.

## Environment constraints (factual)
- **No Docker daemon** (`docker: command not found`).
- **No local PostgreSQL** and pinned `psycopg[binary]==3.2.3` has **no Python-3.14 wheel** (this host runs 3.14). Local tests therefore run on SQLite; the Docker image pins **Python 3.12** where all deps resolve.
- **No headless Chrome** → Lighthouse + Playwright E2E cannot execute here.
- **No git repo; `gh` authed as `CodewithHassan1`.**

---

## ✅ Executed & verified this phase

### Phase C — Automated backend test suite — **39 passed**
`tests/` (pytest + pytest-django), run on every change:
- `test_models.py` — email normalization, role helpers, superuser role, unique email, published queryset, rating CHECK constraint, newsletter token.
- `test_serializers.py` — private-media URL hidden, project detail shape, lead helper-field stripping.
- `test_public_api.py` — published-only listing, detail, **category route not swallowed by `/<slug>`**, blog list/detail, 404, SEO meta + JSON-LD, sitemap/robots, health/ready.
- `test_forms.py` — lead valid/missing/invalid-email/**honeypot**; application valid/**fake-PDF rejected**/terms-required/**oversized rejected**; newsletter **double-opt-in**/duplicate/unsubscribe.
- `test_auth_rbac.py` — login + refresh-cookie, wrong-password 401 **+ audit log**, `/me` auth gate, refresh rotation, admin 401-without-token, **SEO-manager cannot mutate leads (403)**, content-manager can, audit-logs admin-only (403 for editor).

```
$ pytest
39 passed, 34 warnings in ~4s
```

### Phase L — Quality gates (verifiable parts)
- `ruff check apps config tests --select F,E9` → **All checks passed** (6 dead imports found across phases & removed).
- `manage.py check --settings=config.settings.prod --deploy` with a real key → **0 issues**.
- `vite build` → **clean** (frontend).

### Phase J — Deployment infrastructure (authored; YAML/Dockerfile validated)
- `Morpheme-Studios-Backend/Dockerfile` — multi-stage, non-root, Python 3.12, gunicorn.
- `Morpheme-Studios-Frontend/Dockerfile` + `nginx.conf` — build SPA → Nginx, SPA fallback, asset caching, `/api`·`/admin`·`/sitemap.xml` proxy to Django.
- `docker-compose.yml` (project root) — postgres 16, redis 7, clamav, django, celery (+beat), frontend; healthchecks; named volumes. **YAML validated.**
- `Morpheme-Studios-Backend/.env.example` — every env var documented.

---

## ⛔ Blocked-on-infra (run on a Docker/Chrome-capable host)

| Phase | What | How to run |
|---|---|---|
| **A** | Full stack incl. **PostgreSQL** | `cp Morpheme-Studios-Backend/.env.example .../.env` → `docker compose up -d --build` → `docker compose exec django python manage.py migrate && seed_demo` |
| **D** | Postgres-specific validation (GIN/partial indexes, tsvector FTS, transactions) | After Phase A: `docker compose exec django python manage.py migrate` then run the suite against Postgres: set `DATABASE_URL` and `pytest` |
| **C (E2E)** | Playwright user-journey tests | `playwright` is already a frontend devDep; add `tests/e2e/*.spec.js` and `npx playwright test` against the running stack |
| **E** | `vite-react-ssg` prerender + no-JS crawler check | adopt `vite-react-ssg`, build-time slug fetch from `/api/v1/projects`+`/blog`; verify with `curl` (HTML contains content without JS) |
| **G** | Lighthouse on 8 routes | `npx lighthouse <url> --output=json` against the running frontend; targets Perf 90+/A11y 95+/BP 95+/SEO 95+ |
| **B / F / H** | Manual user testing, deep WCAG (axe), live security/OWASP/upload-attack | against the running stack; backend already enforces the controls unit-tested above |

## Phase I — Content migration (designed, not yet run)
The frontend currently uses **API-with-bundled-fallback** (Phase 11). To make the CMS the source of truth: write a one-off `manage.py import_legacy` command that parses `src/data/*.js` (projects, team, blog, testimonials) into the models, then remove the fallback branches. Recommended next concrete step once the stack runs on Postgres.

## Phase K — Reports
This document consolidates Testing / Security / Deployment readiness. The SEO, Accessibility, and Performance numeric reports (Lighthouse/axe scores) are **pending the running stack** (Phase G/F) — they require execution to contain real metrics, and are deliberately not estimated here.

## Phase L — GitHub
No git repo exists in the working tree and the push target is unconfirmed (`gh` is logged in as `CodewithHassan1`). **Awaiting confirmation of the repository** before `git init` + commit + push, since pushing is outward-facing and irreversible.

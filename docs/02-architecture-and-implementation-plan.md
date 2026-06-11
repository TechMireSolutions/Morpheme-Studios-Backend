# Morpheme Studios — System Architecture & Implementation Plan

**Date:** 2026-06-09
**Status:** Planning (no implementation code yet — approval gate before Phase 10)
**Companion doc:** [01-audit-and-gap-analysis.md](./01-audit-and-gap-analysis.md)

## Locked decisions (from stakeholder)

| Decision | Choice |
|---|---|
| Frontend rendering | **Keep Vite SPA + prerendering/SSG** (not Next.js) |
| CMS approach | **Headless** — managed content served as API |
| Backend stack | **Django + Django REST Framework + PostgreSQL** (explicitly Django, not Node) |
| CMS implementation | **Django Admin** as the batteries-included management UI (Wagtail = optional upgrade for rich page editing) |
| Async/infra | Redis (cache + rate-limit + Celery broker), Celery workers, Cloudflare R2 media |
| Process | Plan-before-build |

> Note on the brief's "NestJS hosting / Node" wording: superseded by the explicit Django choice. Every Node-specific item below is mapped to its Django equivalent (e.g. JWT → `djapp simplejwt`, Argon2 → Django Argon2 hasher, repository/service layers → Django service modules + DRF serializers/viewsets).

---

# 1. System Architecture Document

## 1.1 Overall architecture

A **decoupled (headless) architecture** with three logical tiers:

```
                              ┌─────────────────────────────────────────────┐
                              │                  CLIENTS                      │
                              │   Browsers · Social scrapers · Search bots    │
                              └───────────────┬───────────────────────────────┘
                                              │ HTTPS
                              ┌───────────────▼───────────────┐
                              │      Cloudflare (CDN/WAF)      │  edge cache, TLS,
                              │   + redirects, security headers │  rate-limit, bot mgmt
                              └───────┬───────────────┬─────────┘
                                      │               │
                  static HTML/JS/img  │               │  /api/*  , /sitemap.xml, /robots.txt
                                      │               │
                    ┌─────────────────▼──┐      ┌──────▼────────────────────────────┐
                    │ FRONTEND (Nginx/VPS)│      │        BACKEND (Django + DRF)      │
                    │  Vite SPA, prerend. │      │  ┌──────────────────────────────┐ │
                    │  static HTML per    │◄────►│  │ Public API (read + form POST) │ │
                    │  route + react-     │ JSON │  ├──────────────────────────────┤ │
                    │  helmet meta baked  │      │  │ Auth API (JWT)                │ │
                    │  in at build time   │      │  ├──────────────────────────────┤ │
                    └─────────────────────┘      │  │ Admin API (RBAC)              │ │
                                                 │  ├──────────────────────────────┤ │
                    ┌─────────────────────┐      │  │ Django Admin (CMS UI)         │ │
                    │  ADMIN / EDITORS     │─────►│  └──────────────────────────────┘ │
                    │  (staff browsers)    │      │   Service layer · Serializers ·    │
                    └─────────────────────┘      │   Validators · Permissions · Audit │
                                                 └───┬───────────┬──────────┬─────────┘
                                                     │           │          │
                                       ┌─────────────▼──┐  ┌─────▼─────┐  ┌─▼──────────────┐
                                       │  PostgreSQL    │  │  Redis    │  │ Cloudflare R2  │
                                       │  (primary DB)  │  │ cache/    │  │ media (S3 API) │
                                       │                │  │ rate/broker│  │ via CDN        │
                                       └────────────────┘  └─────┬─────┘  └────────────────┘
                                                                 │
                                                          ┌──────▼───────┐   ┌──────────────┐
                                                          │ Celery worker│──►│ Email (SES/  │
                                                          │ + beat       │   │ Postmark)    │
                                                          └──────────────┘   └──────────────┘
```

## 1.2 Frontend ↔ Backend ↔ CMS ↔ Database flow

**Content read (e.g. a project page):**
1. **Build time:** Vite prerender step calls `GET /api/v1/projects` to enumerate slugs → generates a static HTML file per route, with `react-helmet-async` meta + JSON-LD baked in.
2. **Request time:** Nginx (optionally fronted by Cloudflare) serves the static HTML instantly (great LCP, crawler-friendly). The SPA hydrates and may re-fetch `GET /api/v1/projects/:slug` for the freshest data.
3. **On publish:** an editor saves in Django Admin → a signal enqueues a debounced **Celery rebuild task** → `vite build`+prerender → atomic swap into Nginx's static dir (ISR-equivalent freshness).

**Form write (e.g. contact):**
1. SPA `POST /api/v1/leads` with the form payload + Turnstile token.
2. DRF validates → service layer creates `Lead` → Celery sends notification email → audit log entry.
3. Response returns success; SPA shows the "Thank you" state.

**CMS = the management plane:** Django Admin is where staff CRUD all collections. The database is the single source of truth; the API is the read/write contract; the prerendered frontend is a projection of the DB at build time + live fetch for freshness.

## 1.3 Deployment topology

| Concern | Service |
|---|---|
| Frontend static hosting | **Nginx on the VPS** — serves the `vite build` + prerender output from a volume |
| Backend app | **Django + DRF** under **Gunicorn/Uvicorn**, containerized, on the **same VPS** via Docker Compose |
| Database | **PostgreSQL** container on the VPS (dedicated volume) |
| Cache / rate-limit / broker | **Redis** container on the VPS |
| Async jobs | **Celery** worker + **Celery beat** (sitemaps, emails, AV scan, newsletter, frontend rebuild) |
| Media storage | **VPS volume** (public via Nginx, private via Django `X-Accel-Redirect`); **Cloudflare R2** optional drop-in |
| Email | Transactional **SMTP** provider (SES / Postmark / Resend / provider SMTP) |
| Edge / WAF / DNS / TLS | **Nginx + Certbot** on the VPS; **Cloudflare** optional in front for DNS/CDN/WAF |
| Secrets | `.env` on the VPS (chmod 600, never committed) — see §6 |

---

# 2. Database Design

## 2.1 ERD (logical)

```
User ───< AuditLog
User ───< LeadNote
User ──< (assigned_to) Lead
User ──< (assigned_to) JobApplication
User ──< (author) BlogPost
User ──< (author) Project

ProjectCategory 1───< Project >───n ProjectImage >───1 Media
Project >───n ProjectService (service tags)
Project 1───1 SeoMeta (generic relation)

BlogCategory 1───< BlogPost >───n BlogPostTag >───1 Tag
BlogPost 1───1 Media (cover)
BlogPost 1───1 SeoMeta

TeamMember 1───1 Media (photo)
Testimonial 1───1 Media (avatar, optional)

JobOpening 1───< JobApplication
JobApplication ───< (3) MediaFile (cv, portfolio, cover_letter)  [private bucket]

Lead 1───< LeadNote
NewsletterSubscriber (standalone)
Office (standalone)
SiteSetting (singleton/key-value)
Page 1───1 SeoMeta            (editable static pages: home, studio, terms)
RedirectRule (standalone)
Media (library, referenced everywhere)
```

## 2.2 Tables (core fields)

> Common columns on all content tables: `id (BIGSERIAL PK)`, `created_at`, `updated_at`, `created_by_id (FK User)`. Publishable tables add `status (draft|published|archived)`, `published_at`.

**users_user** (custom user, email login)
`id, email (UNIQUE), full_name, password (Argon2), role (enum), is_active, is_staff, last_login, mfa_enabled, created_at`

**projects_projectcategory**
`id, key (UNIQUE), label, sort_order`

**projects_project**
`id, slug (UNIQUE), title, location, year, category_id (FK), type, status_label, excerpt, description, cover_media_id (FK Media), is_featured (bool), featured_order, services (JSONB or M2M), status, published_at, created_by_id, created_at, updated_at`

**projects_projectimage**
`id, project_id (FK), media_id (FK Media), sort_order` (gallery, ordered)

**services_service**
`id, no, title, blurb, image_media_id (FK), sort_order, status`

**blog_blogcategory** `id, slug (UNIQUE), label`
**blog_tag** `id, slug (UNIQUE), label`
**blog_blogpost**
`id, slug (UNIQUE), title, excerpt, body (rich text / HTML or block JSON), cover_media_id (FK), category_id (FK), author_id (FK User), reading_minutes, status, published_at, created_at, updated_at`
**blog_blogpost_tags** (M2M through) `blogpost_id, tag_id`

**team_teammember**
`id, name, role, bio, photo_media_id (FK), sort_order, status, created_at`

**careers_jobopening**
`id, slug (UNIQUE), title, place, employment_type, description, requirements (JSONB), is_open (bool), closes_at, status, created_at`

**careers_jobapplication**
`id, opening_id (FK, nullable=speculative), first_name, last_name, gender, date_of_birth, nationality, country_of_residence, home_address, email, phone, field_of_expertise, applying_for, education, experience_range, cv_media_id (FK, private), portfolio_media_id (FK, private), cover_letter_media_id (FK, private), terms_accepted (bool), terms_accepted_at, status (received|screening|interview|offer|hired|rejected), assigned_to_id (FK User), source, ip_address, user_agent, created_at`

**leads_lead** (contact form)
`id, name, email, phone, message, status (new|contacted|qualified|proposal|won|lost), source, assigned_to_id (FK User), ip_address, user_agent, spam_score, created_at, updated_at`
**leads_leadnote** `id, lead_id (FK), author_id (FK User), body, created_at`

**testimonials_testimonial**
`id, author_name, author_role, company, quote, rating (1-5, nullable), avatar_media_id (FK, nullable), sort_order, status, created_at`

**newsletter_subscriber**
`id, email (UNIQUE), status (pending|confirmed|unsubscribed), confirm_token, confirmed_at, unsubscribed_at, source, ip_address, created_at`

**media_media** (library)
`id, file (R2 key), type (image|video|document), mime, original_name, alt_text, width, height, size_bytes, is_private (bool), uploaded_by_id (FK), created_at`

**seo_seometa** (generic, attachable)
`id, content_type_id, object_id, path (nullable, for non-model pages), meta_title, meta_description, canonical_url, og_title, og_description, og_image_media_id (FK), twitter_card, robots_directives, schema_jsonld (JSONB)`

**pages_page** (editable static pages)
`id, key (UNIQUE: home|studio|terms|...), title, blocks (JSONB), status, updated_at`

**core_office** `id, city, country, address_lines (JSONB), phone, latitude, longitude, sort_order`
**core_sitesetting** `id, key (UNIQUE), value (JSONB)`  — mission, approach, stats, social URLs
**core_redirectrule** `id, from_path (UNIQUE), to_path, status_code (301|302), is_active`
**audit_auditlog** `id, actor_id (FK User, nullable), action, target_type, target_id, changes (JSONB), ip_address, user_agent, created_at`

(JWT refresh/blacklist handled by `rest_framework_simplejwt.token_blacklist` tables.)

## 2.3 Relationships summary
- One **ProjectCategory** → many **Projects**; **Project** → many gallery **ProjectImages** → one **Media** each.
- **BlogPost** → one **BlogCategory**, many **Tags** (M2M), one author (**User**), one cover **Media**.
- **JobOpening** → many **JobApplications**; each application → up to 3 private **Media** files.
- **Lead** → many **LeadNotes**; **Lead**/**JobApplication** → assigned **User**.
- **SeoMeta** attaches polymorphically (generic FK) to Project / BlogPost / Page, or by `path` for ad-hoc routes.

## 2.4 Indexes
- UNIQUE + btree on every `slug`, `users.email`, `newsletter.email`, `redirect.from_path`, `setting.key`, `page.key`.
- `projects_project (status, published_at DESC)`, `(category_id, status)`, partial index `WHERE is_featured` ordered by `featured_order`.
- `blog_blogpost (status, published_at DESC)`, `(category_id, status)`.
- `leads_lead (status, created_at DESC)`, `(assigned_to_id)`.
- `careers_jobapplication (status, created_at DESC)`, `(opening_id)`, `(email)`.
- `audit_auditlog (target_type, target_id)`, `(actor_id, created_at DESC)`.
- GIN index on JSONB columns that get queried (`seo.schema_jsonld` only if filtered; `services` if filtered).
- Full-text: `tsvector` GIN on `blog_blogpost(title, excerpt, body)` and `projects_project(title, excerpt, description)` for search.

## 2.5 Constraints
- FKs with explicit `ON DELETE`: content media `SET NULL` (don't lose a project if a stray image is deleted); `ProjectImage`/`LeadNote` `CASCADE` with parent; assigned_to `SET NULL`.
- `CHECK` constraints on enums (status fields), `rating BETWEEN 1 AND 5`, `year` plausibility.
- `NOT NULL` on business-critical fields (lead.email, application.email, terms_accepted true for applications).
- DB-level `UNIQUE` on slugs (not just app-level) to prevent race duplicates.

---

# 3. CMS Architecture

The CMS is **Django Admin**, customized per collection. Each collection = a Django model + `ModelAdmin` (list filters, search, inline galleries, draft/publish workflow, image previews, bulk actions). Content is exposed read-only to the public via DRF serializers.

| Collection | Model | Key admin features |
|---|---|---|
| **Projects** | `Project` (+ `ProjectImage` inline) | slug auto-from-title, category filter, status workflow, drag-order gallery, featured toggle, SEO inline |
| **Blog Posts** | `BlogPost` | rich-text/block body editor, category + tags, author, scheduled `published_at`, SEO inline |
| **Team Members** | `TeamMember` | photo upload, drag-sort, publish toggle |
| **Careers** | `JobOpening` (+ read-only `JobApplication`) | open/close roles; applications are **read-only** records with secure file download links + pipeline status |
| **Testimonials** | `Testimonial` | quote, rating, avatar, sort, publish |
| **Leads** | `Lead` (+ `LeadNote` inline) | pipeline status, assignment, notes, source, **no create** (system-generated), export |
| **Media** | `Media` | upload to R2, alt-text (a11y/SEO enforced), type filter, usage reference |

Publish workflow: `draft → published → archived`. Only `published` rows are returned by the public API. Saving a publish change enqueues the debounced Celery frontend-rebuild task.

> **Upgrade path:** if editors need richer page-building (drag-drop blocks, live preview), swap the `Page`/content editing layer for **Wagtail** (Django-native headless CMS) without changing the DB/API contract. Recorded as an option, not the default.

---

# 4. Admin Dashboard Architecture

Two viable surfaces; **default = Django Admin** (secure, fast to build, RBAC built in). A custom React admin can be layered later via the Admin API (§7) without backend changes.

| Page | Backing | Contents |
|---|---|---|
| **Dashboard** | custom admin index | KPI cards: new leads (7/30d), new applications, published vs draft counts, newsletter growth, recent audit activity |
| **Leads** | `Lead` admin / `/admin/leads` API | Kanban-style pipeline (new→won/lost), filters, assignment, notes, CSV export |
| **Projects** | `Project` admin | CRUD, gallery management, featured ordering, SEO |
| **Blog** | `BlogPost` admin | CRUD, categories, tags, scheduling |
| **Careers** | `JobOpening` + `JobApplication` | manage openings; review applications, download files, move through pipeline |
| **Media** | `Media` admin | upload, browse, alt-text, delete-with-usage-guard |
| **Settings** | `SiteSetting`, `Office`, `RedirectRule`, `Page` | mission/approach/stats, offices, redirects, static pages |
| **Users** | `User` admin | manage staff, roles, activation, MFA, password reset (Super Admin/Admin only) |

Cross-cutting: every mutating admin action writes an **AuditLog** entry. Dashboard widgets are cached in Redis (short TTL).

---

# 5. Roles & Permissions Matrix

Implemented with a `role` field on `User` + Django Groups/Permissions; DRF object/queryset-level permission classes enforce per-resource rules.

Legend: ✅ full · 📝 create/edit (no publish) · 👁 read-only · — none

| Capability | Super Admin | Admin | Editor | Content Manager | SEO Manager |
|---|:--:|:--:|:--:|:--:|:--:|
| Manage Users & Roles | ✅ | ✅ (not Super Admins) | — | — | — |
| Site Settings / Offices | ✅ | ✅ | — | — | — |
| Projects/Blog/Team/Testimonials – edit | ✅ | ✅ | 📝+publish | 📝 (draft only) | 👁 |
| Publish/unpublish content | ✅ | ✅ | ✅ | — | — |
| Media library | ✅ | ✅ | ✅ | ✅ | 👁 |
| SEO metadata / schema / canonicals | ✅ | ✅ | 👁 | 👁 | ✅ |
| Sitemap / robots / redirects | ✅ | ✅ | — | — | ✅ |
| Leads – view/manage pipeline | ✅ | ✅ | 👁 | ✅ | — |
| Careers – openings & applications | ✅ | ✅ | 📝 openings | ✅ | — |
| Newsletter subscribers | ✅ | ✅ | — | ✅ | 👁 |
| Audit logs | ✅ | ✅ | — | — | — |

- **Super Admin:** unrestricted, incl. managing other Super Admins, destructive settings, integrations.
- **Admin:** day-to-day full control; cannot manage Super Admins.
- **Editor:** owns content end-to-end including publish; no users/settings.
- **Content Manager:** drafts content + runs the leads/careers pipeline; cannot publish or touch SEO/users.
- **SEO Manager:** owns all SEO (meta, schema, sitemap, robots, redirects); read-only on content.

---

# 6. Security Architecture

Maps the brief's OWASP/header/auth requirements to Django.

**Authentication**
- **Argon2** password hashing (`PASSWORD_HASHERS = [Argon2PasswordHasher, ...]`).
- **JWT** via `djangorestframework-simplejwt`: short-lived **access token** (15 min) returned in body; **refresh token** (7 days) stored in an **HttpOnly, Secure, SameSite=Strict cookie**.
- **Refresh-token rotation** + **blacklist** (rotate on every refresh, blacklist the used token). Logout blacklists.
- Optional **MFA** (TOTP) for Admin/Super Admin.
- Lockout/throttle on failed logins (django-axes or DRF throttle).

**RBAC**
- Role-based DRF permission classes + queryset scoping; Django admin uses Groups mapped to the §5 matrix.

**API security**
- **Rate limiting / throttling** via DRF throttles backed by Redis: anon (e.g. 60/min), public form POSTs (e.g. 5/min/IP + daily cap), auth login (e.g. 5/15min/IP).
- **Input validation/sanitization** at the serializer layer; reject unknown fields; strict types; length caps. Rich-text sanitized server-side (bleach/nh3) to kill stored XSS.
- **CSRF**: session/admin flows use Django CSRF; JWT API is CSRF-exempt by design but protected by `SameSite` cookie + `Authorization` header (no ambient cookie auth for the API).

**File upload security (Careers)**
- Whitelist MIME + extension (PDF only), magic-byte sniffing (not just extension), size cap (10 MB), filename sanitization, store in a **private R2 bucket** (no public URL), serve via short-lived **signed URLs** to authorized staff only.
- **Antivirus scan** (ClamAV) in a Celery task before the file is marked downloadable; quarantine on hit.

**OWASP protections**
- **SQLi**: Django ORM parameterization (no raw SQL without params).
- **XSS**: API returns JSON; React escapes by default; server-side sanitize stored HTML; CSP defense-in-depth.
- **NoSQLi**: N/A (Postgres only).
- **SSRF**: no user-supplied URLs are fetched server-side; if added (e.g. media-by-URL), allowlist + block private ranges.
- **Command injection**: no shell calls with user input; AV scan via library/socket, not shell string.
- **Session fixation**: rotate session on login; JWT rotation as above.
- **Clickjacking**: `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`.
- **IDOR**: object-level permission checks on every admin/lead/application endpoint.

**Security headers** (Django middleware + Cloudflare)
- `Content-Security-Policy` (strict; allowlist self + media/CDN origin + fonts; `frame-ancestors 'none'`).
- `Strict-Transport-Security` (HSTS, includeSubDomains, preload).
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimal.
- CORS locked to the known frontend origins only.

**Monitoring & logging**
- **Audit logs** (`AuditLog`) for every staff mutation (actor, action, diff, IP).
- **Security logs**: auth failures, throttle trips, permission denials.
- **Error tracking**: Sentry (backend + frontend).
- Structured JSON logging; PII redaction in logs; log shipping to host.
- **Spam protection** on public forms: **Cloudflare Turnstile** + honeypot field + rate limit + optional disposable-email block.

---

# 7. API Specification

Base: `https://api.morphemestudios.com/api/v1`. JSON. Versioned. Cursor/page pagination on lists. All admin endpoints require JWT + role.

## 7.1 Public — content (read)
| Method | Path | Notes |
|---|---|---|
| GET | `/projects` | list; `?category=&featured=&page=` |
| GET | `/projects/{slug}` | detail incl. gallery, services, SEO |
| GET | `/projects/categories` | category list |
| GET | `/services` | services list |
| GET | `/blog` | list; `?category=&tag=&page=&q=` |
| GET | `/blog/{slug}` | post incl. body, SEO |
| GET | `/blog/categories`, `/blog/tags` | taxonomy |
| GET | `/team` | published members |
| GET | `/testimonials` | published |
| GET | `/careers/openings` | open roles |
| GET | `/careers/openings/{slug}` | role detail |
| GET | `/offices`, `/settings`, `/pages/{key}` | site config + static page content |
| GET | `/seo/meta?path=/...` | meta+schema for a route (prerender) |

## 7.2 Public — write (forms; throttled + Turnstile)
| Method | Path | Body |
|---|---|---|
| POST | `/leads` | name, email, phone?, message, turnstile_token |
| POST | `/careers/applications` | multipart: all applicant fields + cv/portfolio/cover_letter files + terms + turnstile |
| POST | `/newsletter/subscribe` | email, turnstile_token → sends double-opt-in email |
| GET | `/newsletter/confirm?token=` | confirm subscription |
| POST | `/newsletter/unsubscribe` | token/email |

## 7.3 SEO / infra (served by Django, always fresh)
| Method | Path |
|---|---|
| GET | `/sitemap.xml` (index + per-type sitemaps) |
| GET | `/robots.txt` |
| GET | `/feed.xml` (blog RSS, optional) |

## 7.4 Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | → access in body, refresh in HttpOnly cookie |
| POST | `/auth/refresh` | rotates refresh, returns new access |
| POST | `/auth/logout` | blacklists refresh |
| GET | `/auth/me` | current user + role |
| POST | `/auth/password/change` · `/auth/password/reset` · `/auth/password/reset/confirm` | |
| POST | `/auth/mfa/setup` · `/auth/mfa/verify` | TOTP (admin roles) |

## 7.5 Admin (JWT + RBAC)
- CRUD: `/admin/projects`, `/admin/projects/{id}/images`, `/admin/blog`, `/admin/blog/categories`, `/admin/blog/tags`, `/admin/team`, `/admin/testimonials`, `/admin/services`, `/admin/careers/openings`, `/admin/pages`, `/admin/redirects`, `/admin/seo`, `/admin/settings`, `/admin/offices`.
- Media: `POST /admin/media` (upload), `GET /admin/media`, `DELETE /admin/media/{id}`, `GET /admin/media/{id}/signed-url`.
- Leads: `GET /admin/leads`, `GET /admin/leads/{id}`, `PATCH /admin/leads/{id}` (status/assignee), `POST /admin/leads/{id}/notes`, `GET /admin/leads/export`.
- Applications: `GET /admin/applications`, `GET /admin/applications/{id}`, `PATCH /admin/applications/{id}` (status/assignee), `GET /admin/applications/{id}/files/{kind}/signed-url`.
- Newsletter: `GET /admin/newsletter`, `GET /admin/newsletter/export`.
- Users: `GET/POST/PATCH/DELETE /admin/users`, `POST /admin/users/{id}/deactivate` (Super Admin/Admin).
- Ops: `GET /admin/audit-logs`, `GET /admin/dashboard/stats`.

Standard responses: `200/201/204` success; `400` validation (field-keyed errors); `401` unauth; `403` role denied; `404`; `409` slug conflict; `422` semantic; `429` throttled. Uniform error envelope `{ "error": { "code", "message", "fields"? } }`.

---

# 8. Deployment Architecture — Single VPS (Docker Compose)

Both frontend and backend run on **one Linux VPS** (assume Ubuntu LTS). No Vercel/managed PaaS. Nginx terminates TLS and fronts everything; Django runs under gunicorn/uvicorn; Postgres, Redis, Celery, and ClamAV run as containers on the same host. Cloudflare optional in front for DNS/CDN/WAF.

```
                         Internet
                            │  443 (TLS)
                  ┌─────────▼──────────┐   DNS A-records:
                  │   Cloudflare       │   morphemestudios.com      → VPS IP
                  │  (optional CDN/WAF)│   www / api.* (same host)  → VPS IP
                  └─────────┬──────────┘
                            │
   ┌────────────────────────▼─────────────────────────────────────────┐
   │  VPS (Ubuntu) — Docker Compose · ufw(22/80/443) · fail2ban · SSH key│
   │                                                                     │
   │  ┌───────────────── nginx (TLS via Certbot/Let's Encrypt) ───────┐  │
   │  │  /              → static prerendered SPA  (served from volume) │  │
   │  │  /api , /admin  → proxy_pass → gunicorn (Django)               │  │
   │  │  /media/public  → served directly from media volume           │  │
   │  │  /media/private → X-Accel-Redirect, authorized via Django      │  │
   │  └───────────────────────────────────────────────────────────────┘  │
   │     │                         │                                       │
   │  ┌──▼───────────┐      ┌──────▼───────┐   ┌──────────┐  ┌──────────┐  │
   │  │ django       │      │ celery worker│   │ postgres │  │  redis   │  │
   │  │ (gunicorn+   │◄────►│ + celery beat│◄─►│ (volume) │  │(cache/   │  │
   │  │  uvicorn)    │      │              │   │          │  │ broker/  │  │
   │  └──────┬───────┘      └──────┬───────┘   └──────────┘  │ throttle)│  │
   │         │                     │                          └──────────┘  │
   │         │              ┌──────▼───────┐   ┌──────────────────────────┐ │
   │         │              │ clamav (AV)  │   │ media volume (public +    │ │
   │         │              └──────────────┘   │ private dirs) [R2 optional]│ │
   │         │   on publish: Celery rebuild task → vite build+prerender    │ │
   │         │                → atomic swap into nginx static dir          │ │
   └─────────┼─────────────────────────────────────────────────────────────┘
             ▼
        SMTP/email provider (transactional)   ·   Sentry (errors)   ·   off-box backups
```

- **Environments:** `local` (`docker-compose.yml`) and `production` (`docker-compose.prod.yml`) share the same service definitions for parity; optional `staging` = a second compose project / VPS.
- **Reverse proxy / TLS:** Nginx + Certbot auto-renew (or Cloudflare origin cert). HSTS + security headers set here and/or in Django.
- **Static frontend:** `vite build` + prerender output is written to a Docker volume that Nginx serves; the **publish rebuild** Celery task regenerates and atomically swaps it (replaces the Vercel deploy hook).
- **Media:** stored on a host/Docker volume — public files served by Nginx, private files (CVs/portfolios) gated by Django and streamed via `X-Accel-Redirect`. Cloudflare R2 (`django-storages`) remains a drop-in option without code changes.
- **Containerization:** multi-stage, non-root Dockerfile for Django; pinned base images.
- **CI/CD:** GitHub Actions — ruff + mypy + pytest + migration check → build images to **GHCR** → deploy over **SSH** to the VPS (`docker compose pull && up -d`, then `migrate` + `collectstatic` + frontend rebuild).
- **Hardening:** `ufw` (22/80/443 only), `fail2ban`, SSH key-only (no password), least-privilege DB user, secrets in a non-committed `.env` on the host (chmod 600), automatic security updates.
- **Backups & DR:** cron `pg_dump` (+ WAL/incremental optional) and media `rsync` to off-box storage on a schedule; documented restore runbook; volume snapshots if the provider supports them (Phase 13).
- **Health/readiness:** `/health` (liveness) and `/ready` (DB+Redis check) endpoints; external uptime monitor; Sentry for FE+BE errors.

---

# 9. SEO Architecture

Recovers the SEO lost to CSR, within the chosen Vite-SPA-prerender model.

**Rendering for SEO**
- Adopt **`vite-react-ssg`** (or a prerender plugin): at build, each route renders to a static HTML file with real content + `<head>` baked in. Crawlers and social scrapers get full HTML; users get fast LCP, then hydration.
- Dynamic routes (`/projects/:slug`, `/blog/:slug`): build step fetches the slug list from `/api/v1/projects` & `/blog` to enumerate pages to prerender.
- Freshness: publish → debounced **frontend-rebuild task** (VPS-local Celery job: `vite build`+prerender → atomic swap into Nginx static dir) re-prerenders (ISR-equivalent).

**Metadata strategy**
- `react-helmet-async` per route: unique `<title>`, meta description, canonical, **Open Graph**, **Twitter Card**, baked at prerender. Source of truth = `SeoMeta` rows (editable by SEO Manager), with sensible auto-fallbacks (project title/excerpt/cover image).

**Structured data (JSON-LD)** injected per route:
- `Organization` + `LocalBusiness` (×3 offices, with `address`, `geo`, `telephone`) site-wide.
- `Service` for service pages, `Article`/`BlogPosting` for blog, `BreadcrumbList` on deep pages, `FAQPage` where FAQs exist, `ImageObject` for project galleries.

**Sitemap strategy**
- Django generates `/sitemap.xml` (sitemap index → per-type sitemaps: pages, projects, blog) from the DB with `lastmod`. Always current. Submitted to Search Console/Bing.

**Robots strategy**
- Dynamic `/robots.txt` (Django): allow public, disallow `/admin`, `/api/v1/admin`, point to sitemap. Staging serves `Disallow: /`.

**URL & redirects**
- Clean slugs (already in data). Add **blog detail route** `/blog/:slug` (currently missing). Manage 301s via `RedirectRule` → applied by Nginx (generated config) / Django middleware so old WordPress URLs (and dropped pages like Media) don't 404.

**Content SEO**
- Fix Lorem Ipsum/placeholder blurbs and the broken Architecture/Competition copy (audit §8). Real blog bodies. Internal linking: projects ↔ related projects ↔ relevant blog. Image `alt` text enforced in the Media model.

---

# 10. Migration Plan (frontend ↔ backend)

Connect the existing SPA to the new backend with minimal churn. No backend code until this plan is approved; then implement backend (Phase 10) before wiring frontend (Phase 11).

**Step 0 — Backend foundation** (Phase 10): Django project, models, migrations, DRF API, Django Admin, auth, seed DB from current `src/data/*.js` (one-time import script so live content matches today).

**Step 1 — Read path:** introduce an API client + data hooks in the frontend; replace hardcoded imports (`data/projects.js`, `blog.js`, `studio.js`) with fetches. Keep the JSON shape identical to today's objects to minimize component changes. Add loading/error states.

**Step 2 — Prerender + SEO:** add `vite-react-ssg`; build-time slug fetch; add `react-helmet-async` meta + JSON-LD per route sourced from the API; wire `/sitemap.xml` + `/robots.txt`.

**Step 3 — Forms:** wire **Contact** → `POST /leads` and **Careers** → `POST /careers/applications` (multipart, real file upload, progress, validation errors, Turnstile). Associate Careers form labels (a11y fix). Add **Newsletter** subscribe UI.

**Step 4 — Missing pieces:** add `/blog/:slug` detail route + page; restore **Media** gallery (or formally drop with a 301); add **Testimonials** section.

**Step 5 — Publish loop:** wire the Django publish signal → debounced Celery rebuild task (build+prerender → atomic swap into Nginx static dir) so edits go live automatically.

**Step 6 — QA & cutover** (Phases 12–14): security/API/a11y/SEO/Lighthouse tests; 301s for old WordPress URLs; point DNS; verify.

---

## Approval gate

This document covers the 10 requested areas. **No implementation code has been written.** On approval (and any edits you want to these decisions), the next step is **Phase 10 — backend implementation** following this spec, then frontend integration (Phase 11).

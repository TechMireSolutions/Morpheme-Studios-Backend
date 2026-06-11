# Morpheme Studios — Phase 11: Frontend Integration

**Date:** 2026-06-10
**Status:** Implemented & verified (build clean; live end-to-end against the API).
**Frontend:** `Morpheme-Studios-Frontend/` (React 18 + Vite SPA).

Delivered in the requested priority order. The integration is **resilient by design**: every read path falls back to the bundled `src/data/*.js` content if the API is empty or unreachable, so the live site never regresses while the CMS is being populated.

## New shared infrastructure
- `src/lib/api.js` — fetch client, `ApiError` (carries `status` + field errors), typed endpoint helpers. Base URL from `VITE_API_URL` (default `http://localhost:8000`).
- `src/lib/useApi.js` — data hook with `{data, loading, error}` + `fallback`.
- `src/lib/normalize.js` — maps DRF payloads onto the existing component shapes (so no card/detail rewrites were needed).
- `src/components/Seo.jsx` — per-route `<head>` manager fed by `/api/v1/seo/meta`.

## 1–3. Forms → backend
- **Contact** (`Contact.jsx`) → `POST /leads`: loading/disabled state, field-level errors (`aria-invalid` + `role="alert"`), success state. ✅ verified live (incl. CORS from `localhost:5173`).
- **Careers** (`Careers.jsx`) → `POST /careers/applications`: full multipart (cv/portfolio/cover_letter), controlled inputs, **all labels now associated (`htmlFor`/`id`)** — fixes audit §5 a11y failure — terms enforced, error/success states.
- **Newsletter** (`components/Newsletter.jsx`, in Footer) → `POST /newsletter/subscribe`: double-opt-in messaging, `sr-only` label.

## 4–6. Reads → API
- **Projects** (`Projects.jsx`) + **ProjectDetail** — list/detail via API, normalized, bundled fallback; async loading handled (no premature redirect).
- **Team** (`Studio.jsx`) — `/team`, fallback to bundled team.
- **Blog** (`Blog.jsx`) + **new `/blog/:slug` route** (`BlogDetail.jsx`, registered in `App.jsx`) — restores the article body + detail page the audit flagged as missing. Body rendered from server-sanitised HTML.

## 7. SEO metadata → API
- `<Seo>` on Home, Studio, Projects, ProjectDetail, Blog, BlogDetail, Contact, Careers. Sets title/description/canonical/OG/Twitter + injects JSON-LD, with static defaults applied instantly and `/seo/meta` as the editor-controlled override. ✅ verified meta resolves per route.

## 8. Sitemap → frontend
- `public/robots.txt` (allows crawl, points to the sitemap on the apex domain).
- `vercel.json`: rewrites `/sitemap.xml` → backend dynamic sitemap; SPA deep-link fallback (so `/blog/:slug` etc. resolve on refresh); immutable caching for `/assets/*`.

## 9. Accessibility (WCAG 2.2 AA progress)
- Skip-link to `#main`; `<main id="main" tabIndex={-1}>` + **focus moved to main on route change** (`ScrollToTop.jsx`) — SPA nav now announces to AT.
- Visible `:focus-visible` outline; `.sr-only` utility.
- Careers form labels associated; form errors wired to `aria-invalid`/`role="alert"`.
- Dead `href="#"` social links in the mobile menu replaced with real URLs.
- `prefers-reduced-motion` already global (verified).

## 10. Performance
- Asset immutable caching (`vercel.json`); `decoding="async"` on `ResilientImage`; existing route-level code-splitting + lazy images retained.

## Verified
- `vite build` clean after every step (final bundle unchanged in size class).
- Live: CORS preflight + `POST /leads` from `localhost:5173`; `/team`, `/blog`, `/blog/{slug}`, `/seo/meta?path=/projects/...` all return correct data.

## Remaining follow-ups (honest scope)
- **True crawler-grade SEO needs prerender/SSG** (`vite-react-ssg`, plan §9/§10): `<Seo>` currently runs client-side. The data source (`/seo/meta`) is ready to reuse at prerender time — this is the single biggest remaining SEO item.
- **Image optimization pipeline** (AVIF/WebP, responsive `srcset`) for the large `public/*.jpg` files — needs asset reprocessing, not just code.
- **Self-host fonts** + `font-display: swap` (audit §6).
- **Turnstile widget** on the public forms (backend verification already wired; add the client widget + `VITE_TURNSTILE_SITE_KEY`).
- Content migration: import the full legacy `src/data/*.js` records into the CMS so the API (not the fallback) becomes the source of truth.

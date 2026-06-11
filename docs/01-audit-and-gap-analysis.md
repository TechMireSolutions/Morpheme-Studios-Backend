# Morpheme Studios — Phase 1 & 2: Audit + Gap Analysis

**Date:** 2026-06-09
**Author:** Architecture review
**Scope:** Reverse-engineer business logic of the old WordPress site and the new Vercel frontend **before** any backend is written. No backend code has been produced yet (per requirement).

---

## 0. Evidence base

| Source | What was inspected |
|---|---|
| New frontend codebase | `Morpheme-Studios-Frontend/` — full `src` tree, `package.json`, `vite.config.js`, `index.html`, `public/` |
| New live site | `https://morpheme-studios.vercel.app/` (raw HTML) |
| Old live site | `https://www.morphemestudios.com` (rendered content) |
| Backend folder | `Morpheme-Studios-Backend/` — empty except `README.md` |

**Stack (verified):** React 18 + Vite 8 + React Router 6 + GSAP. Pure client-side-rendered SPA. No SSR/SSG. No backend. No test/lint/typecheck tooling beyond Playwright + Lighthouse dev deps.

---

## 1. Site structure (new frontend)

Routes (from `src/App.jsx`):

| Route | Page | Data source | Notes |
|---|---|---|---|
| `/` | Home | hardcoded `data/*` | Home eager-loaded; rest lazy |
| `/studio` | Studio | `data/studio.js` | mission, approach, team, stats |
| `/projects` | Projects | `data/projects.js` | category filter (client-side) |
| `/projects/:slug` | ProjectDetail | `getProject(slug)` | 19 projects |
| `/blog` | Blog | `data/blog.js` | **list only** |
| `/careers` | Careers | hardcoded roles in page | application form |
| `/contact` | Contact | `data/studio.js` (offices) | contact form |
| `/terms` | Terms | static | |
| `*` | NotFound | — | |

**Navigation:** Navbar links = Projects, Studio, Blog, Careers, Contact (+ logo→Home). Footer mirrors this plus social links and Terms / Data Protection Act.

**Information architecture is sound and simpler than the old site** — but several content types are *displayed* with no way to *manage* them.

---

## 2. Business logic (what the company actually does)

Morpheme Studios is an **architecture & design practice** (offices: London UK, Ras Al Khaimah UAE, Karachi PK). Revenue comes from project commissions, so the website's two business-critical jobs are:

1. **Lead capture** — turn visitors into project enquiries (Contact form) and recruits (Careers form).
2. **Credibility / portfolio** — showcase projects, studio, team, thought-leadership (blog) to win those leads.

Everything else is supporting content.

### Content classification

| Content | Today | Should be |
|---|---|---|
| Projects (19) | hardcoded `projects.js` | **CMS-managed** (CRUD, the core marketing asset) |
| Blog posts (6) | hardcoded `blog.js`, excerpt-only | **CMS-managed** (needs real body content) |
| Team (9) | hardcoded `studio.js` | **CMS-managed** |
| Services / categories | hardcoded | CMS-managed (light) |
| Careers / open roles (8) | hardcoded in `Careers.jsx` | **CMS-managed** (roles change often) |
| Testimonials | **absent** | CMS-managed (exists on many competitors; missing here) |
| Offices, mission, approach | hardcoded | CMS or config — low churn, fine to keep static initially |
| Terms, legal | static | static is fine |

---

## 3. Functional analysis (feature → backend requirement)

| Feature | Current state | Backend requirement |
|---|---|---|
| **Contact form** (`Contact.jsx`) | Collects name/email/phone/message. `submit` just sets `sent=true`. **Sends nothing.** | POST endpoint, validation, persistence, spam/rate-limit, email notification, lead record |
| **Careers application** (`Careers.jsx`) | Collects heavy PII (name, gender, DOB, nationality, residence, address, email, phone) + **3 file uploads** (CV, portfolio ≤10MB, cover letter). `onSubmit={e.preventDefault()}` — **does literally nothing.** | Multipart upload endpoint, file validation/AV scan, storage (S3/R2), persistence, GDPR handling, notification |
| **Project listing/detail** | Static data | Read API + CMS CRUD |
| **Blog** | List only; **no `/blog/:slug` route, no article body** | CMS CRUD, article body, detail page |
| **Newsletter** | **Not present** (prompt asks for it) | Subscribe endpoint + double opt-in |
| **Search** | **Not present** | Optional; client-side index is enough at this scale |
| **Media gallery** | **Dropped** vs old site | Decide: restore as CMS media library or omit |

---

## 4. SEO audit (new frontend) — **this is the headline problem**

The live site at `morpheme-studios.vercel.app` returns **an empty `<div id="root">` plus script tags**. Confirmed by fetching raw HTML — no body content is server-delivered.

Consequences:
- **Crawlers / social link unfurls / LLM crawlers** that don't execute JS see almost nothing. Googlebot renders JS but with delay and budget limits; Bing/social scrapers largely do not.
- **One static `<title>` and one meta description** for the *entire* site (`index.html`). Every route — Projects, each project, Studio, Blog, Contact — shares the same title/description.
- **No** per-route metadata, canonical tags, Open Graph, Twitter Cards, JSON-LD structured data.
- **No** `robots.txt`, **no** `sitemap.xml` in `public/`.
- This is a **regression** vs WordPress, which (whatever its faults) server-rendered unique HTML + meta per page and typically had Yoast/RankMath sitemaps & schema.

**This single architectural fact (CSR SPA) caps SEO quality regardless of how good the backend is.** It is the central decision in §9.

---

## 5. Accessibility audit (WCAG 2.2 AA) — initial findings

- **Broken/placeholder links:** mobile overlay menu socials are `href="#"` (`Navbar.jsx` lines 99–101). Dead links, keyboard/AT traps.
- **Custom cursor** (`data-cursor`) — confirm it never removes the OS cursor or blocks focus visibility.
- **Forms:** Contact form labels are correctly associated (`htmlFor`/`id`) ✅. **Careers form labels are NOT associated** (no `htmlFor`/`id` on most fields) — screen-reader failure. No error messaging, no `aria-live` on success state.
- **Focus management:** route changes scroll to top (`ScrollToTop`) but focus is not moved to `<main>`/`<h1>` — SPA navigation announces nothing to AT.
- **Loader / intro animation** (5s) — needs `prefers-reduced-motion` respect across GSAP usage; verify.
- **Headings/landmarks:** single `<main>` ✅, `<footer>` ✅, `<header>` nav ✅. Need to verify single `<h1>` per route and logical heading order.
- **Color contrast:** `body-muted` on dark sections needs measured contrast check.

Full per-component WCAG pass to be done in Phase 7.

## 6. Performance (Core Web Vitals) — initial findings

- Lazy-loading of non-home routes ✅; manual vendor chunking (react / gsap) ✅.
- **Large unoptimized images in `public/`:** `city-by-sea.jpg` 2.45 MB, `bunify.jpg` 1.97 MB, `architecture.jpg` 0.84 MB — shipped raw. No responsive `srcset`, no AVIF/WebP pipeline for these. Major LCP/bandwidth risk.
- **Google Fonts via render-blocking `<link>`** with two families & many weights — self-host + `font-display: swap` recommended.
- GSAP + custom cursor + intro loader add JS/main-thread cost; measure TBT/INP.
- No CDN image transform, no caching headers strategy defined.

## 7. Security risks (current + planned) — initial findings

- No backend yet → no current server attack surface, but **planned** surface is large: two public forms (one with file upload + PII), an admin CMS, auth.
- PII + file uploads (Careers) demand: input validation, file type/size/content validation, AV scanning, encrypted storage, GDPR/Data-Protection-Act compliance (the footer already links the UK DPA 2018).
- No secrets management, env strategy, headers (CSP/HSTS/etc.) defined yet — Phase 5.

---

## 8. Gap analysis — Old WordPress vs New frontend

### Features present on OLD site, missing/incomplete on NEW

| Old site had | New site |
|---|---|
| **Media** page/gallery | **Dropped** |
| "Morphemeous 2.0" nav item | Dropped (verify what it was — possibly a sub-brand/product) |
| Granular per-service nav pages (Architecture, Interior, Residential, Retail, Arts, Competition, Renovation/Restoration as distinct pages) | Collapsed into project category *filters* + a services list. "Renovation & Restoration" service no longer distinct |
| **Working** contact form (WordPress delivered submissions by email) | Form is **non-functional** (frontend demo only) |
| Server-rendered SEO (unique meta/title per page, plugin sitemap/schema) | **Lost** — CSR empty shell |

### Broken flows on NEW site (cannot work without backend)

1. Contact form → no submission, no email, no lead saved.
2. Careers application → no submission, no file upload, PII collected then discarded.
3. Blog → no article bodies, no detail route.
4. Newsletter (required by brief) → does not exist.

### SEO regressions
Empty-shell CSR, single global meta, no sitemap/robots/schema/OG — all listed in §4.

### Content quality issues found in code
- `studio.js`: Architecture blurb is broken ("is an Architecture and design services."), Arts & Design blurb is **Lorem Ipsum** ("Lorem Ipsum is simply dummy text…a"), Competition blurb mismatched (describes renovation).
- `projects.js`: `cover` uses a mix of shared stock images and a few real `/assets/projects/*` files — most projects reuse the same handful of stock photos. Real project imagery is a content gap.
- Team photos are all `team-placeholder.svg`.

---

## 9. The decision that gates everything: rendering strategy

The brief demands **world-class SEO**, **green Core Web Vitals**, and a **CMS**. A client-rendered Vite SPA cannot deliver world-class SEO. Before writing backend code, the frontend rendering model must be decided, because it determines:
- whether SEO metadata/schema are injected server-side (real SEO) or client-side (cosmetic only),
- how the CMS content reaches pages (build-time SSG, request-time SSR, or client fetch),
- which backend topology makes sense.

**Options (recommendation: A):**

- **A. Migrate frontend to Next.js (App Router) + a backend API.** SSR/SSG/ISR gives true per-page meta, JSON-LD, sitemap, OG, fast LCP. Biggest effort; highest ceiling. Recommended for the stated goals.
- **B. Keep Vite SPA, add prerendering/SSG** (e.g. `vite-react-ssg` / prerender plugin) + a standalone API. Lower effort, recovers most SEO for static-ish pages; weaker for frequently-updated CMS content.
- **C. Keep CSR SPA as-is, build backend/API only.** Lowest effort; **does not meet the SEO goal** — only honest if SEO is downgraded in priority.

This, plus backend stack, DB, and CMS build-vs-buy, are posed as explicit questions to the stakeholder before Phase 3+.

---

## 10. Recommended sequencing (Phases 3–15)

1. **Lock decisions** (§9 + stack/DB/CMS) — *blocking*.
2. Phase 3–4: Backend requirements spec + data model/ER design.
3. Phase 5–6: Security & SEO architecture (depends on §9).
4. Phase 9: finalize stack (informed by §9).
5. Phase 10: implement backend (clean/modular, repository + service + validation + error + logging layers).
6. Phase 11–12: frontend integration + QA.
7. Phase 13–15: deploy prep, final verification, GitHub hygiene + push.

No backend code is written until the §9 decisions are made.

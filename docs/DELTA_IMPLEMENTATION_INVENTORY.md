# Delta Implementation Inventory (v1.5 addenda vs. current checkout)

**Stage:** 0 — Delta Read-only Inventory
**Status:** `VERIFIED` (read-only; no application file, migration or DB was modified)
**Branch / HEAD:** `42b2278` — "تست آپدیت ریدمی" (recorded at audit time)
**Scope:** only `F03.UX`, `F03.0`, `F12.1.1` and the minimal wiring of the existing
Provider / Telegram / Archive / Settings UIs. v1.3 domain features (F00–F16, F13 archive,
source bot, dedup, priority, ingestion, analysis) are **reused, not rebuilt**.

Working-tree caveat: the checkout already carries uncommitted owner changes across
`apps/web/src/*`, `backend/*`, `tests/*`, `db/migrations/env.py` and docs. Nothing was
reset, cleaned, stashed or rewritten; the deltas below are measured against that tree.

---

## 1. Frontend stack actually in use

| Area | Reality (evidence) |
|---|---|
| Framework | React 18.3 + Vite 5.4, TypeScript 5.5 (`apps/web/package.json`) |
| Styling | Hand-authored CSS (`apps/web/src/styles.css`, 250 lines) + token file `apps/web/src/design/tokens.css`; Tailwind 4 utilities imported **without preflight** for two chat components (`apps/web/src/tw.css`) |
| Router | Custom hash router, 27 route names, no per-route code splitting (`apps/web/src/router.ts`) |
| State | Local `useState` + a `useApi` hook; no query cache, no global store (`apps/web/src/ui.tsx`) |
| Components | One 569-line shared module `apps/web/src/ui.tsx` (Table, Modal, Field, Section, StatCard, Badge, Toast, Spinner, Empty, Err, charts) + 5 files under `components/ui/` (button, loader, response, markdown, conversation, mostly chat-oriented) |
| Icons | Local inline SVG set, 40 icons (`apps/web/src/icons.tsx`) — one icon system already, no dependency needed |
| Auth model | Internal API key typed by the user, held **in memory only** (`apps/web/src/api.ts`); no localStorage, matches the security rule |
| Theme | dark/light only, persisted in `localStorage` under `gi_theme` (`apps/web/src/theme.tsx`) |
| i18n | Persian RTL hard-coded (`index.html` `dir="rtl"`), Persian number/date formatting in `theme.tsx` |
| Tests | Playwright E2E only (`apps/web/e2e/*.spec.ts`), ESLint + `tsc --noEmit`; **no unit/component test runner** |

No frontend framework rewrite or new dependency is justified by this delta.

---

## 2. Requirement-by-requirement status

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1.1 | Single design-token source | `PARTIAL` | `design/tokens.css` holds color/space/radius/shell tokens; no status or P0–P4 tokens, no documented token contract. |
| 1.2 | Token values consumed everywhere | `PARTIAL` | `styles.css` reads tokens, but `styles.css` also hard-codes sizes (`width: 340px`, `height: 38px`, `52vh`, `130px`, `150px`). |
| 1.3 | Persian typography | **`CONFLICT` (defect)** | `tw.css` declares `@theme inline { --font-sans: var(--font-sans); }`, a self-reference that makes `var(--font-sans)` invalid; `body` computes `font-family: "Times New Roman"` on every route (measured, `docs/audit-baseline/baseline.json`). The whole Persian typographic stack is dead. |
| 1.4 | Light + dark + system theme | `PARTIAL` | `theme.tsx` supports `dark`/`light` with persistence; `system` preference is not offered and `color-scheme` is fixed per theme. |
| 1.5 | Base component set (Button, Input, Select, Switch, Table, Dialog, Drawer, Tabs, Badge, Toast, Empty, Error, Skeleton, Pagination, Tooltip, Breadcrumb) | `PARTIAL` | Exists: Button variants via CSS classes, Table (sortable), Modal, Field, Badge, Section, Spinner/skeleton, Empty, Err, Toast. Missing: Switch, Drawer, Tabs component (ad-hoc `.tabs` markup), Pagination component, Tooltip, Breadcrumb, FormField with `aria-describedby`, ConfirmAction semantics (only a `ConfirmDialog` that reuses Modal). |
| 1.6 | App shell + grouped task-based navigation | `PARTIAL` | `Shell` in `ui.tsx`; `NAV_GROUPS` in `router.ts` groups by domain (نمای کلی / داده و هوش مصنوعی / تحلیل جهان / بازار و تصمیم / سیستم) with 25 items in 5 groups — partially task-based, but "Settings"/"Archive" are untranslated English labels in a Persian menu and the first group mixes overview with the inbox. |
| 1.7 | Responsive shell, collapsible sidebar, mobile drawer | `EXISTS` | Collapse toggle persisted only for the session; mobile off-canvas at `<860px`; sidebar is `position: fixed` on mobile but **not focus-trapped** and not closed on route change by keyboard. |
| 1.8 | Command palette / shortcuts | `MISSING` | Only `/` focuses global search (`Shell` keydown). No palette. |
| 1.9 | Keyboard/focus management on route change | `MISSING` | `<main key={route.name}>` remounts but focus is not moved or announced; sidebar drawer keeps focus behind the scrim. |
| 1.10 | 404 / permission-denied route states | `MISSING` | `parseHash()` silently falls back to `dashboard`; unauthorized calls render the generic key notice. |
| 1.11 | Unified loading / empty / error / stale / offline states | `PARTIAL` | `useApi` + `Section` give loading/error; `Empty` exists. Missing: stale timestamp, offline/degraded banner, per-widget retry, no-results-with-clear-filters, partial-success reporting. |
| 1.12 | Dashboard KPIs are defined, sourced, timestamped | `PARTIAL` | Values come from real endpoints (`/api/ops/status`, `/api/sources`, `/api/classify/articles`, `/api/forecasts`, `/api/world-state/current`, `/api/risk/overview`), and the page states "نامشخص" when an API fails. But no `last_updated_at`, no metric definition, no per-KPI deep link with filters, and 8 identical `401` error blocks render at once when the key is missing. |
| 1.13 | Mock/hard-coded data never shown as real | `EXISTS` | `MockTag` badge on classified items; `StateBanner` marks `demo`/`dev`/`nc` sections; dashboard has no fabricated numbers. |
| 1.14 | Per-route page header + primary action | `PARTIAL` | `PageHeader` and ad-hoc `.page-head` blocks both exist (two patterns). |
| 1.15 | Wide-table handling on small viewports | `PARTIAL` | `.tablewrap` scrolls horizontally; no column priority, no row-card fallback, no scroll affordance. |
| 1.16 | URL reflects filter/sort state | `MISSING` | German-style filters live in component state only; the inbox detail uses `#/news/article-<id>` but the list filter/page/sort is lost on reload/back. |
| 1.17 | Component/unit tests, visual regression, a11y automation | `MISSING` | No test runner for components, no axe, no snapshot suite; E2E covers news priority, screening ops, settings models only. |
| 2.1 | Shared configuration descriptor/schema contract | `MISSING` | No `/api/configuration/*` surface; grep for `ConfigurationRevision` / `revision_number` / `config_revision` across `backend`, `domains`, `source_bot`, `db` returns **zero** hits. |
| 2.2 | Config revisions + rollback + audit + optimistic locking | `MISSING` | Same evidence; `PATCH /api/sources/{id}` mutates the single row in place (`backend/api/routers/sources.py:112`). |
| 2.3 | Encrypted, write-only secrets | `EXISTS` (provider credentials) / `MISSING` (sources) | Fernet-based store with "refuse plaintext" behaviour: `backend/ai/credentials.py`, model in `backend/database/models/ai_settings.py`, key from `APP_ENCRYPTION_KEY`. Source auth material has no store because `Source` has no credential fields. |
| 2.4 | Source adapter registry as single source of truth | `PARTIAL` | Registry exists (`source_bot/registry.py`: `pick_adapter`, `endpoint_options`; adapters `rss.py`, `rest_json.py`, `csv.py`, `xml.py`, `html.py`, `scrapy_policy.py`), but there is no descriptor endpoint and the frontend still hard-codes `TYPES = ["rss","api","dataset","official","scrape","manual","other"]` (`apps/web/src/pages/sources.tsx`). |
| 2.5 | Draft → validate → test → preview → enable lifecycle | `MISSING` | `POST /api/sources` writes an active-by-default row; only `POST /{id}/recheck` and `POST /{id}/health` exist. |
| 2.6 | Preview that never ingests | `MISSING` | The closest existing action calls `POST /api/ingest` with `limit: 5` — it **does** ingest (`pages/sources.tsx`, `trialFetch`). |
| 2.7 | Runtime pins the config revision per run | `MISSING` | No revision field on `Source`/`Job`; `source_bot/runner.py` resolves adapters live. |
| 3.1 | Server-side source list search/filter/sort/pagination | `MISSING` | `GET /api/sources?limit=500` then client-side filtering in the page. |
| 3.2 | Multi-step source wizard with field-level validation | `MISSING` | Single flat `SourceForm` modal, validation of `name` only; no test/preview/draft step; `enable` is a checkbox inside the same form. |
| 3.3 | Source duplicate / rollback actions | `MISSING` | Not present in UI or API. |
| 4.1 | Provider catalog read from backend | `EXISTS` | `GET /api/ai/providers`, `GET /api/settings/providers`, `/api/ai/status` consumed by `pages/ai.tsx`, `pages/keys.tsx`, `pages/connections.tsx`. |
| 4.2 | Provider lifecycle states (discovered → enabled) kept separate | `PARTIAL` | Credential save, connectivity verify and model verify are separate calls (`/api/settings/models/{id}/verify`, `/api/settings/models/{id}/block`), but there is no shared `CONFIGURED/CONNECTIVITY_VERIFIED/POLICY_APPROVED/ENABLED` vocabulary across UI and backend. |
| 4.3 | Telegram/archive config through one control plane | `PARTIAL` | `pages/archive.tsx` uses `/api/archive/{catalog,settings,storage,validate,restore/dry-run,purge/preview}`; token/chat ID are not managed from the UI at all (env-based). |
| 4.4 | Purge safety gates preserved in any redesign | `EXISTS` | `purge/preview` + `restore/dry-run` endpoints consumed by the archive page; must stay untouched by the redesign. |

---

## 3. Capabilities deliberately **not** rebuilt

- Provider catalog/discovery (`/api/ai/providers`, `/api/settings/providers`, routing apply).
- Telegram archive ZIP/manifest/upload/verify/restore/purge logic (`backend/api/routers/archive.py`, `domains/*`).
- Source adapters, SSRF guard, dedup, priority, ingestion and analysis pipeline.
- Fernet credential service (`backend/ai/credentials.py`) — the Control Plane must reuse it, not create a second secret store.

---

## 4. Smallest compatible change per missing item (design note for later stages)

| Gap | Smallest change | Dependency / risk |
|---|---|---|
| Broken font token | Remove the self-referential `--font-sans`/`--font-mono` lines from `tw.css @theme inline`; keep Tailwind utilities working | None; one-line fix, high visual impact |
| Status/P0–P4 tokens | Extend `design/tokens.css`, document the mapping | None |
| Config revision model | New `ConfigurationInstance`/`Revision`/`TestRun`/`AuditEvent` tables + Alembic migration | PostgreSQL run required; not to be written in a read-only stage |
| Source descriptor endpoint | Read-only `GET /api/configuration/definitions` derived from `source_bot/registry.py` | Requires a descriptor dataclass in `source_bot` |
| Non-ingesting preview | New adapter-level `preview()` path + `POST …/preview` returning sanitized samples | Must reuse `source_bot/security.py`; must not touch ingestion counters |
| Server-side source list | Extend `GET /api/sources` with `q/type/active/page/page_size` (backward compatible) | Existing callers use `limit` only |
| Component tests | Add `vitest` + `@testing-library/react` (already TypeScript/Vite) | **New devDependency** — gate on owner approval |
| Visual regression / axe | Playwright screenshots (already installed) + optional `@axe-core/playwright` | New devDependency only for axe |

---

## 5. Open risks

1. `styles.css` is a single global sheet with no component boundaries; every later stage must extend tokens instead of adding new global rules.
2. Two parallel page-header/section patterns already exist (`PageHeader` vs `.page-head`); consolidating them touches ~20 pages.
3. The frontend has no unit-test harness, so "component tests" for F03.UX.1 require a new devDependency and an explicit owner decision.
4. `Archive` and `Settings` labels are untranslated inside a Persian navigation; renaming affects E2E selectors (`settings-models.spec.ts`).

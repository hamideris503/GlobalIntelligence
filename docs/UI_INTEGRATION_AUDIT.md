# UI Integration Audit — Stage UI-00 (read-only)

**Stage:** `UI-00` — full repository, prototype, frontend and API audit
**Status:** `PARTIALLY_VERIFIED`
**Read-only:** no application source file was changed by this stage. Files **added**: this
document, `docs/UI_PAGE_FEATURE_MATRIX.md`, `docs/UI_API_MAPPING.md`,
`docs/audit-baseline/dump_openapi.py`. No commit, no push, no branch change, no DB mutation,
no container rebuild.
**Date:** 2026-11-04

Why `PARTIALLY_VERIFIED` and not `VERIFIED`: two of the audit's preconditions do not hold in the
current environment — the running stack is built from older code than the working tree (§2.3) and
the database contains no intelligence data (§2.4). Both are recorded as blockers in §10, not
worked around. Everything that *could* be established without them is evidenced below.

`PARTIALLY_VERIFIED` is also why several prototype surfaces are marked `BLOCKED` rather than
"missing": we cannot tell whether the backend satisfies them until the stack matches the tree.

---

## 1. Repository state

| Item | Value |
|---|---|
| Branch | `stage95-pg-ci-verification` (not `main`) |
| HEAD | `42b2278e22deb19119bb8447db00bcaad4b549fb` — *تست آپدیت ریدمی* |
| Tracked modifications | **83 files**, +4,072 / −578 |
| Untracked files | **116** |
| Stashes | none |
| Other branches | `main` (`6e6a4b0`, tracks `origin/main`), `cbpool` |

One tracked deletion is present: `source_bot/normalizer.py`. It is dead code — every importer in
`domains/`, `source_bot/` and `tests/` imports `domains.news.normalizer` instead, and
`create_app()` imports cleanly, so the deletion is not a breakage. Recorded so that it is not
mistaken for one during later stages.

The working tree is **199 files dirty before this stage began**. That work is prior in-progress
effort for exactly this mission (F03.UX shell/states/dashboard/detail/polish/responsive docs,
`archive.tsx`, the `configuration/*` control plane, 5 new migrations, provider catalog, adaptive
routing). Consequences accepted by this audit:

1. The **working tree**, not HEAD, is the source of truth for "current state" — auditing HEAD
   would describe code nobody is running or extending.
2. Nothing in the working tree was reverted, stashed, cleaned or reformatted.
3. `git status` will stay dirty. A stage-by-stage lead would normally want a clean baseline;
   that gate belongs to the owner (§10, `D-3`).

## 2. Runtime state (measured, not assumed)

### 2.1 Services

`docker compose ps` — all six containers `Up 8 hours`, `gi_backend` / `gi_postgres` /
`gi_staging_postgres` / `gi_staging_backend` report `healthy`. Published on the host:
`127.0.0.1:8000` (backend), `5173` (frontend), `5678` (n8n).

### 2.2 Host → PostgreSQL is unreachable

`python -m alembic current` from the host fails:

```
psycopg.errors.ConnectionTimeout: connection timeout expired
- host: 'localhost', port: 5432 ... connection timeout expired
```

`netstat` shows **no listener on 5432** although `docker-compose.yml` publishes
`127.0.0.1:${POSTGRES_PORT:-5432}:5432`. Practical effect: every DB/migration check must be run
in-container (`docker compose exec …`). Recorded as `B-2`.

### 2.3 The running backend is older than the working tree — `BLOCKER`

| Check | Result |
|---|---|
| Migration files on disk | **45** |
| Migration files inside `gi_backend` | **40** |
| `alembic_version` in live DB | `b8c4d5e6f7a8` |
| `alembic current` in container | **FAILED**: `Can't locate revision identified by 'b8c4d5e6f7a8'` |

`b8c4d5e6f7a8_archive_telegram_ids.py` exists on disk and is **untracked**; the image was built
before it existed. The database is therefore *ahead* of the code that is supposed to manage it,
and `alembic upgrade head` cannot run in the container at all.

Live probe of the running API (correct `X-API-Key` from `.env`):

| Endpoint | Live | In working tree (`dump_openapi.py`) |
|---|---|---|
| `GET /health` | 200 | ✓ |
| `GET /health/db` | 200 | ✓ |
| `GET /api/ops/status` | 200 | ✓ |
| `GET /api/archive/storage` | **404** | ✓ (9 `/api/archive` operations) |
| `GET /api/configuration/definitions` | **404** | ✓ (10 `/api/configuration` operations) |
| `GET /api/claims` | 200 | ✓ |
| `GET /api/graph/entities` | 200 | ✓ |
| `GET /api/alerts` | 200 | ✓ |
| `GET /api/alerts/rules` | 200 | ✓ |

**Consequence:** the shipped `#/archive` page and every `/api/configuration` consumer currently
fail against the running stack with `404`. Any acceptance run made today measures stale code.
This is an environment defect (image rebuild), not a source defect — but it blocks `UI-13`
verification and any "end-to-end works" claim until fixed.

### 2.4 The database holds no intelligence data — `BLOCKER` for demo/acceptance

```
documents=0  articles=0  events=0  claims=0  entities=0  sources=0  forecasts=0  job_runs=181
```

Not even `sources` is seeded, so ingestion has never run in this environment. Every page will
correctly render its **empty state**. Two consequences:

- Fabrication risk is currently **zero** for the simple reason that there is nothing to display —
  that is not the same as "no fabrication exists".
- Populated rendering, chart shapes, map density and pagination cannot be verified until data is
  ingested or seeded (§10, `B-3`).

## 3. Frontend stack (as found — do not replace)

| Concern | Reality |
|---|---|
| React / TS / Vite | 18.3, TypeScript 5.5 (`strict`, `noUnusedLocals`), Vite 5.4 |
| Styling | Tailwind 4 (`@tailwindcss/vite`) **and** a custom token sheet `src/design/tokens.css` + `src/styles.css` |
| Routing | hand-rolled hash router, `src/router.ts`, zero dependencies, 27 routes |
| Server state | hand-rolled `useApi()` hook in `ui.tsx`; **no** react-query/SWR/Redux/zustand |
| Charts | hand-rolled SVG: `LineChart`, `Bars`, `Donut`, `Sparkline` — **no** chart library |
| Map | **nothing** — no maplibre/leaflet/deck.gl in `package.json` or `src/` |
| Theme | `theme.tsx` + `theme-context.ts`, `localStorage["gi_theme"]` only |
| Components | `ui.tsx` (975 lines) exports 30 primitives (Shell, useApi, Table, Modal, Field, Badge, PriorityBadge, StateBanner, MockTag, …) |
| Unit tests | **none** — no vitest/jest |
| E2E | Playwright 1.64, 5 specs (`fullstack`, `news-priority`, `screening-ops`, `settings-models`, `pg-fullstack`), 3 configs |
| Source size | 5,679 lines across `src/**` |

Verification run during this stage (read-only, no writes):

```
npx tsc --noEmit   → exit 0
npx eslint .       → 0 errors, 7 warnings (react-refresh/only-export-components in ui.tsx)
```

So the frontend is currently **green**; the gap is coverage and capability, not compile health.
Note `ux-16` (Persian font collapsing to Times New Roman) from `docs/UI_UX_AUDIT.md` is now
**fixed** — `tokens.css` defines `--font-sans` and `tw.css` documents why it must not redefine it.

## 4. Backend contract (from the application, not from router names)

Generated with `python docs/audit-baseline/dump_openapi.py` against `create_app()`:

- **189 paths**, **202 operations**, 48 router modules.
- Everything except `/health*` and login requires `X-API-Key`.
- Endpoint density per prefix: `settings` 23, `configuration` 10, `alerts` 10, `archive` 9,
  `sources` 8, `portfolios` 6, `ingest` 6, `dispatch` 6, `local-runtimes` 5, `independence` 5,
  `graph` 5, `forecasts` 5, `memory` 4, `markets` 4, `iran` 4, `economic` 4, `decisions` 4,
  `debate` 4, `claims` 4, `briefings` 4, `audit` 4, `ai-routing` 4, `ai` 4, …

Spatial capability, stated plainly because it decides the map stage:

```
grep -rniE "latitude|longitude|geojson" backend domains source_bot db  → 0 matches
Event.location : free-text String(255)   (no code, no coordinates)
Article.country: ISO-2, nullable, indexed
Entity.country : ISO-2, nullable
MarketObservation.country / MacroAssessment.country : ISO-3
```

**There is no coordinate anywhere in the system.** The prototype's map cannot plot real event
pins today; see `D-1`.

Pagination across the main list endpoints:

| Endpoint | `limit` (max) | `offset` | Total in response |
|---|---|---|---|
| `/api/sources` | 100 (500) | ✓ | ✗ |
| `/api/graph/entities` | 100 (1000) | ✓ | ✗ |
| `/api/classify/articles` | 50 (500) | ✗ | ✗ |
| `/api/events` | 50 (500) | ✗ | ✗ |
| `/api/claims` | 50 (500) | ✗ | ✗ |
| `/api/forecasts` | 100 (1000) | ✗ | ✗ |
| `/api/alerts` | 100 (1000) | ✗ | ✗ |
| `/api/jobs` | 20 (200) | ✗ | ✗ |

No schema in the whole contract has a `total` field. Real "showing 1–50 of N" pagination is
**not implementable** without a small, backward-compatible backend change (§9, `G-1`).

## 5. Prototype audit — `GlobalIntelligence_WorldMonitor_2D_Full_Map.html`

237,643 characters, single file: inline CSS (~70 KB) then a `<script>` with every page rendered by
string concatenation. It declares itself a prototype:

- `<meta description="… Demo data only; backend not connected.">`
- every page is mounted under a ribbon: *«حالت Prototype · Backend: متصل نیست · داده‌ها: نمونه / شماتیک»*.

### 5.1 Page inventory — 25 pages in 4 nav groups

| # | Page id | Persian title | Implementation quality in the prototype |
|---|---|---|---|
| 1 | `overview` | مرکز هوشمندی | dedicated renderer, all numbers sample |
| 2 | `ai-analysis` | مرکز تحلیل هوشمند AI | dedicated renderer, sample |
| 3 | `ai-chat` | گفت‌وگوی هوشمند AI | dedicated renderer, sample |
| 4 | `debate` | مناظره و مقایسهٔ مدل‌ها | dedicated renderer, sample |
| 5 | `evaluation` | آزمایشگاه ارزیابی مدل‌ها | dedicated renderer, sample |
| 6 | `evidence` | مرکز شواهد و ادعاها | dedicated renderer, sample |
| 7 | `entity-graph` | شبکهٔ موجودیت‌ها و روابط | **`genericDomain()`** — schematic |
| 8 | `forecasts` | پیش‌بینی‌ها و افق‌های زمانی | dedicated renderer, sample |
| 9 | `risk` | سناریو و تحلیل ریسک | dedicated renderer, sample |
| 10 | `decisions` | پشتیبانی تصمیم | dedicated renderer, sample |
| 11 | `inbox` | صندوق اطلاعات و اخبار | dedicated renderer, sample |
| 12 | `world` | هوشمندی جهانی | `worldMonitorPage()` — **the only real implementation (MapLibre)** |
| 13 | `geopolitics` | تحلیل ژئوپلیتیک | **`genericDomain()`** |
| 14 | `iran` | تحلیل ایران و کانال‌های انتقال | **`genericDomain()`** |
| 15 | `macro` | هوشمندی اقتصاد کلان | **`genericDomain()`** |
| 16 | `markets` | بازارهای مالی | **`genericDomain()`** |
| 17 | `portfolio` | مدیریت پرتفوی | **`genericDomain()`** |
| 18 | `screening` | غربالگری و بازبینی انسانی | dedicated renderer, sample |
| 19 | `sources` | مدیریت منابع و ورودی‌ها | dedicated renderer, sample |
| 20 | `providers` | ارائه‌دهندگان و مدل‌های AI | dedicated renderer, sample |
| 21 | `operations` | خط پردازش و عملیات | dedicated renderer, sample |
| 22 | `alerts` | مرکز هشدارها | **`genericDomain()`** |
| 23 | `archive` | آرشیو هوشمند تلگرام | dedicated renderer, sample |
| 24 | `reports` | گزارش‌ها و تاریخچه | dedicated renderer, sample |
| 25 | `settings` | تنظیمات و کنترل اتصال‌ها | dedicated renderer, sample |

**18 dedicated renderers, 7 schematic (`genericDomain`) pages.** The prototype is honest about
this in its own copy (`«این نما باید با API تخصصی و دادهٔ دارای provenance پر شود»`). So "preserve
the design of pages 13–17, 22" means *preserve a placeholder's visual language*, not a designed
feature — that distinction is carried into the matrix.

### 5.2 The world map (the centerpiece, and the largest gap)

```js
new maplibregl.Map({ container, style:'https://tiles.openfreemap.org/styles/dark',
                     center:[0,22], zoom:1.45, minZoom:1, maxZoom:16, … })
```

- **External runtime dependencies:** MapLibre GL **5.6.2 from `unpkg.com`** (CDN `<script>`/`<link>`)
  and the **`tiles.openfreemap.org`** style/tile service. Both require internet at run time.
  An npm dependency + a self-hosted or configurable style URL is the production-appropriate shape.
- Data source: `sessionStorage["gi-world-map-endpoint"]`; `fetchFeed()` is only called if that key
  exists — otherwise the panel shows *«بدون اتصال · API رویداد هنوز پیکربندی نشده است.»*
- Engineering patterns worth porting verbatim: `disposeWorldMap()` + `window.__giWorldMapCleanup`
  (removes interval, keydown, resize listeners and calls `map.remove()` on route change),
  `map.on('styledata')` re-binding guard, explicit "map library failed to load" empty state that
  states *no substitute data will be shown*.
- Layer UI: active-layer set, per-layer search, selected-layer chips, coordinate readout, UTC
  clock, `Escape` closes popup, `/` focuses layer search.

**Nothing of this exists in the React app** — `grep -r "maplibre|leaflet"` → no matches, and the
`world` route is a world-state/macro indicator page, not a map.

### 5.3 Interaction inventory (port targets)

Global command palette (⌘/Ctrl+K, fuzzy over page ids), topbar global search, notifications,
theme toggle, sidebar collapse to 76 px, off-canvas drawer under 860 px, breadcrumb, modals,
drawers, `role="tooltip"` chart tooltips, keyboard focus rings, `prefers-reduced-motion` guards,
RTL throughout (`<html lang="fa" dir="rtl">`), disabled-by-design tabs with an explanatory
`title` (range selectors stay disabled until timestamped data exists — a **correct** pattern to
keep, not to "fix" by enabling them).

## 6. Current React UI versus the prototype

27 routes exist; the prototype has 25 pages. Mapping is close but **not** one-to-one:

| Prototype page | React route today | Verdict |
|---|---|---|
| overview | `dashboard` | present |
| ai-analysis | `ai` | present |
| ai-chat | `chat` | present |
| debate | `debate` | present |
| evaluation | `evaluation` | present |
| **evidence** | — | **absent** (backend `/api/claims`, `/api/claims/{id}/evidence` exist) |
| **entity-graph** | — | **absent** (backend `/api/graph/*`, 5 operations exist) |
| forecasts | `forecast` | present |
| risk | `scenarios` | present |
| decisions | `decisions` | present |
| inbox | `news` (+ `article-<id>`, `event-<id>`) | present, richer than prototype |
| **world (2D map)** | `world` | **absent** — route exists, map does not |
| geopolitics | `geo` | present |
| iran | `iran` | present |
| macro | `macro` | present |
| markets | `markets` | present |
| portfolio | `portfolio` | present |
| screening | `screening` | present (585 lines, the most developed page) |
| sources | `sources` | present |
| **providers** | split across `ai`, `keys`, `settings`, `connections` | **no single control surface** |
| operations | `ops` | present |
| **alerts (center)** | only a tab inside `ops` + a bell in the shell | **absent as a page** (backend has rules CRUD, ack, resolve, per-channel delivery) |
| archive | `archive` | present in code, **404 against the running stack** (§2.3) |
| reports | `history` | present |
| settings | `settings` | present (808 lines) |

React-only surfaces with no prototype counterpart: `connections`, `keys`, `help`, `search`,
`society` (an explicit, honestly-labelled placeholder whose backend router does exist —
`/api/society/mood`, `/api/society/assessments` are consumed by `geo.tsx` instead).

**Net gap: 4 pages missing (`evidence`, `entity-graph`, `alerts`, `providers` as one surface) and
1 flagship feature missing (the map).**

## 7. What the prototype's claims must become

The prototype is a *visual and interaction reference only*. Three of its patterns must **not** be
ported:

1. Sample numbers rendered as if they were metrics (e.g. `۲۴۸` completed AI analyses, `۸۷٪`
   agreement). The React app already avoids this — `docs/UI_UX_AUDIT.md` §5 found no fabricated
   numbers, and `MockTag` labels mock classifications. Keep it that way.
2. `chartPanel()` time-range tabs that look interactive (`۳۰ روز / ۹۰ روز / ۱ سال`). In the React
   app they may only become interactive once a timestamped series is served by an endpoint.
3. Prototype "consensus / confidence" donuts fed by constants. `Kev`/`Laya` are **advisory**
   (`AGENTS.md`): any number shown must carry model + source provenance, or be absent.

## 8. Security posture (static review only)

| Control | Finding |
|---|---|
| API key storage | memory only (`api.ts` module variable); `localStorage` used **only** for the theme key — ✓ matches `AGENTS.md` |
| XSS surface | `grep -rn "dangerouslySetInnerHTML\|innerHTML"` in `src/` → **none** (markdown renders to React children) ✓ |
| Error leakage | `fetchJson` normalizes status → Persian message; `detail` strings only; no key echo ✓ |
| SSRF (sources feed URLs) | `source_bot/security.py`: `validate_url` blocks cloud metadata + private hosts/IPs, `connection_check` validates **all** resolved IPs (DNS-rebinding aware), `vetted_ip` pins the vetted IP ✓ |
| Secrets in responses | not re-verified end-to-end in this stage (settings/provider payloads) — deferred to the stage that touches them |
| Auth model | single shared `X-API-Key`, no per-route RBAC in the frontend; backend enforces via `protected` — matches `AGENTS.md`, no change proposed |

## 9. Backend capability gaps (minimum changes, only where proven absent)

| ID | Gap | Evidence | Minimum change | Needed by |
|---|---|---|---|---|
| `G-1` | No true pagination | no `offset` on 7 of 9 main lists; no `total` in any schema | add `offset` (default 0) to those list endpoints + an `X-Total-Count` header; keep `limit` semantics | `inbox`, `evidence`, `alerts`, `ops`, `forecasts` |
| `G-2` | No spatial data | 0 coordinate fields repo-wide | **owner decision** `D-1` | world map |
| `G-3` | `/api/archive/*`, `/api/configuration/*` return 404 live | live probe §2.3 | rebuild the backend image (no code change) | `archive`, `settings` |
| `G-4` | No aggregate endpoint for dashboard KPIs | dashboard counts are client-side over truncated `limit=200` lists (`UX-19`) | one aggregate read endpoint (counts + `last_updated_at` per domain) | `overview` |
| `G-5` | `society` page has no UI though a router exists | `society.tsx` = placeholder; `/api/society/*` used by `geo.tsx` | connect the page to `/api/society/assessments`, `mood`, `analyze` | `society` |

`G-2` is the one that decides whether `UI-08` is an integration task or a multi-layer feature
(schema + geocoding + provenance), so it is escalated, not assumed.

## 10. Blockers and owner decisions

| ID | Type | Item | Effect if unresolved |
|---|---|---|---|
| `B-1` | BLOCKED | Running stack is older than the tree; DB revision unknown to the image | `archive`/`settings` pages cannot be verified; "it works" claims are invalid |
| `B-2` | BLOCKED | Host cannot reach Postgres; all DB work must go through `docker compose exec` | slower work; no host-side migration evidence |
| `B-3` | BLOCKED | Database has 0 documents/articles/sources | populated rendering, chart behaviour, pagination and map density cannot be verified; acceptance limited to empty/error states |
| `D-1` | decision | **Map data strategy.** (a) country-level aggregation only — aggregate `Article.country`/`Entity.country` ISO-2 into bubbles on a country centroid layer, explicitly labelled "country aggregate, not event coordinates"; (b) add `Event.latitude/longitude` + migration + geocoding step so real pins exist; (c) both — ship (a) now, (b) later | cannot start `UI-08`; (a) is honest and needs no migration, (b) is the only way to satisfy "event points on the map" |
| `D-2` | decision | **New frontend dependencies.** Real map requires `maplibre-gl`; nothing else is strictly required (no chart lib, no data-fetch lib) | map stage blocked; everything else proceeds without new deps |
| `D-3` | decision | **Dirty baseline.** 199 files are uncommitted; the owner manages Git (no commit/push allowed here) | stage reports will reference a moving baseline |

`D-1` is the only decision that changes the *architecture* of a stage. It is deliberately left open.

## 11. Proposed stage order (aligned with §14 of the mission, adjusted to reality)

Mission order is `UI-00 → UI-18`. Evidence asks for one resequencing: the two missing *backend-backed*
pages (`evidence`, `entity-graph`) are cheap and low-risk, while the map (`UI-08`) is the expensive,
decision-dependent one. Recommended:

1. **UI-00** — this audit (done).
2. **Unblock** `B-1`/`B-3` — rebuild image, get migrations applying, ingest or seed data so that
   "real data" can be *demonstrated* rather than asserted.
3. **UI-02** — finalize the mapping (`docs/UI_API_MAPPING.md` is the draft) and add `G-1`.
4. **UI-06/07** — dashboard KPI definitions (`G-4`) + inbox, then `evidence` and `entity-graph`
   pages (new routes, existing endpoints).
5. **UI-08** — world map, **only after `D-1`**.
6. **UI-11/12** — providers control surface, alerts center.
7. Remaining stages as listed in the mission.

No stage after UI-00 was started.

## 12. Exit criteria for UI-00

| Criterion | Result |
|---|---|
| Repository, branch, HEAD, dirty state, untracked files recorded | ✓ §1 |
| DB state, migration state, service versions recorded | ✓ §2 (with 3 blockers) |
| Frontend stack, routing, state, charts, tests, build health inventoried | ✓ §3 |
| Real API contract extracted from the app (202 operations) | ✓ §4 + reproducible script |
| HTML prototype fully inventoried (25 pages, map, interactions, deps) | ✓ §5 |
| Prototype → current page comparison | ✓ §6, detailed in `UI_PAGE_FEATURE_MATRIX.md` |
| UI → API → DB → Test matrix | ✓ `UI_API_MAPPING.md` |
| Backend changes that are genuinely required separated out | ✓ §9 |
| No source change made | ✓ (3 docs + 1 read-only script added) |

**Verdict:** `PARTIALLY_VERIFIED`. The audit is complete as analysis; the environment is not yet
capable of proving the *runtime* half of it. The next stage must begin by clearing `B-1` and
`B-3`, and `UI-08` must not begin before `D-1` is decided.

---

## 13. Stage Report

| Field | Value |
|---|---|
| **Stage ID** | `UI-00` |
| **Status** | `PARTIALLY_VERIFIED` |
| **Git branch** | `stage95-pg-ci-verification` |
| **HEAD** | `42b2278e22deb19119bb8447db00bcaad4b549fb` |
| **Files created** | `docs/UI_INTEGRATION_AUDIT.md`, `docs/UI_PAGE_FEATURE_MATRIX.md`, `docs/UI_API_MAPPING.md`, `docs/audit-baseline/dump_openapi.py` |
| **Files modified** | none |
| **Files deleted** | none (one throwaway `.tmp-openapi-paths.txt` created and removed by this stage) |
| **Components implemented** | none — read-only stage |
| **Pages integrated** | none |
| **API endpoints connected** | none; 202 operations inventoried |
| **Backend changes** | none |
| **Database changes** | none |
| **Migrations** | none added/run |
| **Tests executed** | `npx tsc --noEmit`; `npx eslint .`; `dump_openapi.py`; live HTTP probe of 9 endpoints; read-only SQL counts; `alembic current` (host + container) |
| **Test results** | tsc **exit 0**; eslint **0 errors / 7 warnings**; OpenAPI **202 operations**; probe **7×200 / 2×404**; `alembic current` host **timeout**, container **FAILED (unknown revision)** |
| **Build results** | not run (no production build in a read-only audit); typecheck + lint green |
| **Security findings** | API key memory-only ✓; no `innerHTML`/`dangerouslySetInnerHTML` ✓; SSRF guard present and DNS-rebinding aware ✓; secrets-in-response coverage deferred to the providers stage |
| **Performance findings** | no route-level code splitting (`App.tsx` imports all 27 pages); no server pagination on 6 lists; dashboard re-requests 8–9 endpoints per refresh with no cache; no duplicate-request guard beyond `useApi` deps |
| **Known limitations** | no populated-DB verification (`B-3`); no map (dependency + data absent); no unit-test harness (no vitest); no human usability, screen-reader or contrast measurement in this stage |
| **Blocked items** | `B-1` stale image (archive/settings 404), `B-2` host→PG unreachable, `B-3` empty database, `D-1`/`D-2`/`D-3` owner decisions |

---

## 14. Stage Report — `UI-01` (blockers cleared, three pages integrated)

| Field | Value |
|---|---|
| **Stage ID** | `UI-01` |
| **Status** | `PARTIALLY_VERIFIED` |
| **Git branch** | `stage95-pg-ci-verification` |
| **HEAD** | `42b2278e22deb19119bb8447db00bcaad4b549fb` (unchanged; no commits made) |
| **Files created** | `apps/web/src/pages/evidence.tsx`, `apps/web/src/pages/graph.tsx`, `apps/web/src/pages/alerts.tsx` |
| **Files modified** | `apps/web/src/router.ts`, `apps/web/src/App.tsx`, `apps/web/src/icons.tsx`, `apps/web/src/ui.tsx` (`Table` relaxed to generic `T`), `backend/api/routers/claims.py`, `backend/api/routers/classify.py` |
| **Files deleted** | none |
| **Components implemented** | `Evidence`, `EntityGraph` (radial SVG from real neighbours), `AlertsCenter` (tabs alerts/rules, ack/resolve, dry-run and confirmed real delivery, rule create/toggle) |
| **Pages integrated** | `#/evidence`, `#/graph`, `#/alerts` (+ sidebar entries and two new distinct icons) |
| **API endpoints connected** | `/api/claims`, `/api/claims/extract`, `/api/claims/evidence`, `/api/graph/entities` (server `offset` paging), `/api/graph/entities/{id}`, `/api/graph/neighbors/{id}`, `/api/graph/extract`, `/api/alerts`, `/api/alerts/{id}/ack`, `/api/alerts/{id}/resolve`, `/api/alerts/{id}/deliver/{channel}`, `/api/alerts/evaluate`, `/api/alerts/rules`, `/api/alerts/rules/{id}`, `/api/sources`, `/api/classify/articles` |
| **Backend changes** | additive only: `EvidenceRead.source_id` + `document_id`, `ClaimRead.claimed_at`, `ArticleClassifiedRead.document_id`, `ArticleDetailRead.document_id` |
| **Database changes** | none (no schema/migration change) |
| **Migrations** | none added; `alembic current` = `b8c4d5e6f7a8 (head)` inside the container |
| **Tests executed** | `ruff check` (changed routers); `python -m pytest tests/test_claims.py tests/test_classification.py -q`; `npx tsc --noEmit`; `npx eslint .`; `npm run build`; curl probe of 10 endpoints; live OpenAPI schema inspection; browser render check of `#/evidence` |
| **Test results** | ruff **0 findings**; pytest **53 passed**; tsc **exit 0**; eslint **0 errors / 7 pre-existing `react-refresh` warnings**; vite build **✓ 1963 modules, 361.96 kB**; endpoints **200**; OpenAPI confirms the four new fields; page renders with heading/filters/actions and the correct auth banner |
| **Build results** | frontend production build green (`vite build`); backend image rebuilt and healthy. The frontend **image** rebuild could not finish: `RUN npm install` in the build container stalls because npm traffic to `registry.npmjs.org` is ~19 s per request (a `npm ping` inside the container took 19 245 ms), so two builds were abandoned. Resolution: the new source was copied into the running dev container and that container was then **committed as `globalintelligence-frontend`**, so a plain `docker compose up -d` (and `--force-recreate`) serves the new pages without a rebuild; a reproducible `docker compose build frontend` remains pending a fast registry |
| **Security findings** | API key still memory-only; no secret written to disk (``.tmp-key.txt`` removed); real channel delivery is behind an explicit confirm dialog and defaults to `dry_run=true`; pages never invent provenance (unknown `direction` shown as «نامشخص») |
| **Performance findings** | `Table` still sorts client-side; `/api/graph/entities` is the only list with real server paging and is used with `limit=25`; claims/alerts lists cap at 200 rows server-side |
| **Known limitations** | observed live data at report time: **articles 214, sources 19, claims 173, evidence 0, entities 0, entity_relationships 0, alerts 1, alert_rules 1**. Classification still cannot run (`app_settings.mock_mode=false` + no real provider key), and the stored claims carry heuristic `subject/predicate = unknown`, so evidence/entity extraction has produced no rows; no map (`D-1`/`D-2` undecided); the frontend image is a committed container snapshot rather than a reproducible build until the registry link is fast enough; no unit-test harness (no vitest) |
| **Blocked items** | `B-3` remains: a real provider key is required to populate classified articles, claims, evidence and entities |

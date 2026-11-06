# UI Page / Feature Matrix — prototype vs reality

**Companion to:** `docs/UI_INTEGRATION_AUDIT.md` (stage `UI-00`)
**Scope:** all 25 pages of `GlobalIntelligence_WorldMonitor_2D_Full_Map.html`, mapped to the current
React app, the real backend contract (202 operations, `docs/audit-baseline/dump_openapi.py`) and an
acceptance test per page.
**Read-only:** this document changes nothing in the app.

Status vocabulary (per mission §18): `VERIFIED` · `PARTIALLY_VERIFIED` · `NOT_VERIFIED` ·
`BLOCKED` · `FAILED`.

> No page is `VERIFIED` by this audit. Verification requires running against a stack whose code
> matches the tree **and** a database with data — neither holds today (`B-1`, `B-3`). "Present" below
> means *the React route exists and calls real endpoints*, not "proven working".

## Summary

| Prototype page | React route | UI present | Backend present | Overall |
|---|---|---|---|---|
| overview | `dashboard` | ✓ | ✓ | PARTIALLY_VERIFIED |
| ai-analysis | `ai` | ✓ | ✓ | PARTIALLY_VERIFIED |
| ai-chat | `chat` | ✓ | ✓ | BLOCKED (no provider key) |
| debate | `debate` | ✓ | ✓ | PARTIALLY_VERIFIED |
| evaluation | `evaluation` | ✓ | ✓ | PARTIALLY_VERIFIED |
| evidence | — | ✗ | ✓ `/api/claims` | NOT_VERIFIED (no UI) |
| entity-graph | — | ✗ | ✓ `/api/graph` | NOT_VERIFIED (no UI) |
| forecasts | `forecast` | ✓ | ✓ | PARTIALLY_VERIFIED |
| risk | `scenarios` | ✓ | ✓ | PARTIALLY_VERIFIED |
| decisions | `decisions` | ✓ | ✓ | PARTIALLY_VERIFIED |
| inbox | `news` | ✓ | ✓ (limit-only) | PARTIALLY_VERIFIED |
| world | `world` | ✗ map | ✗ (no coordinates) | BLOCKED (`D-1`) |
| geopolitics | `geo` | ✓ | ✓ | PARTIALLY_VERIFIED |
| iran | `iran` | ✓ | ✓ | PARTIALLY_VERIFIED |
| macro | `macro` | ✓ | ✓ | PARTIALLY_VERIFIED |
| markets | `markets` | ✓ | ✓ | PARTIALLY_VERIFIED |
| portfolio | `portfolio` | ✓ | ✓ | PARTIALLY_VERIFIED |
| screening | `screening` | ✓ | ✓ | PARTIALLY_VERIFIED |
| sources | `sources` | ✓ | ✓ | PARTIALLY_VERIFIED |
| providers | `ai`/`keys`/`settings`/`connections` | partial | ✓ | PARTIALLY_VERIFIED |
| operations | `ops` | ✓ | ✓ | PARTIALLY_VERIFIED |
| alerts | tab in `ops` | partial | ✓ 10 ops | NOT_VERIFIED (no page) |
| archive | `archive` | ✓ | 404 live | BLOCKED (`B-1`) |
| reports | `history` | ✓ | ✓ | PARTIALLY_VERIFIED |
| settings | `settings` | ✓ | 404 live (configuration) | BLOCKED (`B-1`) |

---

## A. فضای کاری هوشمند (intelligent workspace)

### 1. `overview` → `dashboard.tsx`
- **Prototype:** executive synthesis card (AI headline + confidence + source/event/model pills),
  4 KPI cards with sparklines, risk-trend line chart, model-agreement donut, prioritised
  recommendations, evidence-flow chain (sources → events → claims → evidence → synthesis),
  mini entity network, model scorecards, recent AI outputs table. All values sample.
- **Expected real function:** one screen that answers "what changed, why does it matter, what do I do".
- **Current:** 8 panels / 6 stat cards on real endpoints (`/api/ops/status`, `/api/sources`,
  `/api/classify/articles`, `/api/forecasts`, `/api/world-state/current`, `/api/risk/overview`,
  `/api/markets/latest`, `/api/briefings`). No fabricated numbers (`UI_UX_AUDIT.md` §5).
- **Gap:** KPIs have no definition/`last_updated_at`/deep link (`UX-03`); counts computed over
  truncated `limit=200` lists (`UX-19`, needs `G-4`); one missing key produced 8 identical error
  panels (`UX-02`); no synthesis card that is itself backed by stored AI output.
- **Acceptance:** with ≥1 article/forecast present, every number is traceable to an endpoint and
  matches `psql` counts; a single auth failure yields exactly one page-level banner; each KPI links
  to its filtered dataset.

### 2. `ai-analysis` → `ai.tsx`
- **Prototype:** analysis queue, inference trace (evidence → contradiction → synthesis), model and
  provider attribution, confidence, run status.
- **Expected real function:** run an analysis through the gateway, list past runs with model/provider.
- **Current:** `/api/ai/providers`, `/api/ai/status`, `/api/ai-routing/routes`, `/api/ai-routing/apply`,
  `/api/ai/generate`. Gateway-only path preserved.
- **Gap:** analysis *history* with evidence and confidence is not surfaced as a first-class list;
  no per-run trace view.
- **Acceptance:** run once → a row appears with provider, model, latency, and the stored output;
  refreshing the page reloads the same row; no direct provider call from the browser (network tab).

### 3. `ai-chat` → `chat.tsx`
- **Prototype:** conversation, model picker limited to allowed models, source citations.
- **Current:** `/api/ai/chat`, `/api/settings/models`, `/api/settings/providers`; shell components in
  `components/ui/*`.
- **Gap / blocker:** no storage for conversations (`backend/database/models/memory.py` exists but
  chat history is not wired); `BLOCKED` for a real reply without a provider key or `MOCK_MODE`.
- **Acceptance:** with mock mode, a reply renders with its provider/model label and is *marked mock*;
  with a real key it renders with citations or an explicit "no source" state; errors are shown, not swallowed.

### 4. `debate` → `debate.tsx`
- **Prototype:** pro/con arguments, risk critique, final synthesis, run status, history.
- **Current:** `/api/debate/runs`, `/api/debate/runs/{id}`, `/api/decisions/from-debate`.
- **Gap:** agent selection is not exposed (agents are config, not UI); no per-turn evidence links.
- **Acceptance:** start a debate → status transitions and persist; opening a run shows arguments and
  the derived decision; a failed run shows its error and stays retryable.

### 5. `evaluation` → `portfolio.tsx` (`EvaluationPage`)
- **Prototype:** precision/recall/F1 cards, confusion matrix, calibration, gold-set state.
- **Current:** `/api/evaluation/*`, `/api/self-eval/*`, `/api/debate/scorecard`.
- **Gap:** without a valid gold set the page must state the limitation rather than show zeros as
  results; the prototype's "سه سنجه" tabs are disabled — same rule applies.
- **Acceptance:** with an empty gold set the page shows an explicit "NOT_EVALUATED / no gold set"
  state; with data, metrics match the stored evaluation rows.

### 6. `evidence` → **missing**
- **Prototype:** claims list, supporting vs opposing evidence, per-source provenance, claim graph,
  open-original-article. (`claims` table: `verification_status`, `supporting_source_count`,
  `independent_source_count`, `source_independence`; `evidence.direction ∈ {supports, contradicts}`.)
- **Backend:** `/api/claims`, `/api/claims/{claim_id}/evidence`, `/api/claims/extract`,
  `/api/claims/evidence`. **Fully available.**
- **Gap:** no route, no page. Claims appear only inside `news` detail and two dashboard buttons.
- **Acceptance:** a claim with both directions renders two separated lists with source name,
  `published_at`, `retrieved_at`, weight and confidence; a claim with no evidence shows an empty
  state, not "verified"; the original article opens from each evidence row.

### 7. `entity-graph` → **missing**
- **Prototype:** interactive node/edge canvas, node selection, detail, filter, search, zoom, pan
  (the prototype drawn by hand as a static SVG).
- **Backend:** `/api/graph/entities` (type, limit, offset), `/api/graph/entities/{id}`,
  `/api/graph/relationships`, `/api/graph/neighbors/{id}`, `/api/graph/extract`. **Available.**
- **Gap:** no route, no page; no graph rendering component.
- **Acceptance:** 2-hop neighbourhood of a seeded entity renders with labelled node types; clicking a
  node opens its entity detail; an entity with no relationships shows an empty state; graph is built
  **only** from `/api/graph/*` (no client-side inference).

### 8. `forecasts` → `analysis.tsx` (`ForecastPage`)
- **Prototype:** P50 / P10–P90 uncertainty fan, horizon, confidence, historical performance, actual outcomes.
- **Current:** `/api/forecasts`, `/api/forecasts/ledger/active`, `/api/forecasts/run`.
- **Gap:** uncertainty band must come from the stored forecast distribution; the prototype's fan chart
  is explicitly conceptual and must not be reproduced from constants.
- **Acceptance:** selecting a forecast renders its real point estimate and interval (or states that
  the interval is unavailable); resolved forecasts show actual vs predicted.

### 9. `risk` → `analysis.tsx` (`ScenariosPage`)
- **Prototype:** probability × severity, transmission speed, evidence quality, scenario comparison.
- **Current:** `/api/scenarios`, `/api/scenarios/run`, `/api/risk/overview`, `/api/risk/analyze`.
- **Gap:** no scenario diff/edit surface.
- **Acceptance:** two scenarios render side by side with probability, severity and evidence quality
  from stored rows; a missing probability is shown as "—", never as 0.

### 10. `decisions` → `analysis.tsx` (`DecisionsPage`)
- **Prototype:** ranked recommendations with score, confidence, assumptions, limitations.
- **Current:** `/api/decisions`, `/api/decisions/run`, `/api/audit/log`.
- **Gap:** assumptions/limitations are not rendered; the UI must not present output as a guarantee.
- **Acceptance:** each decision shows score, confidence, rationale and horizon; any decision created
  by a user action appears in `/api/audit/log`.

## B. اطلاعات و تحلیل حوزه‌ای (domain intelligence)

### 11. `inbox` → `news.tsx` (+ `article-<id>`, `event-<id>`)
- **Prototype:** unified feed with priority, topic relation, duplicate clusters, analysis status.
- **Current:** `/api/classify/articles`, `/api/classify/articles/{id}`, `/api/events`, `/api/claims`;
  detail route with claims. Priority rendered via `PriorityBadge` (P0–P4 implemented in `ui.tsx`).
- **Gap:** no pagination (`limit` only, no `offset`/`total` → `G-1`); duplicate clusters have no UI
  (`UX-12`); provenance timeline in detail incomplete (`UX-11`).
- **Acceptance:** server-side paging with a correct total; filters survive reload (hash query);
  opening an article shows published/retrieved timestamps, source, priority reason and cluster link.

### 12. `world` → `world.tsx` — **the flagship gap**
- **Prototype:** MapLibre 5.6.2 globe (CDN) + `tiles.openfreemap.org` dark style, event layers,
  category/time filters, place search, layer visibility, event detail, timeline, coordinate readout,
  explicit "no connection" and "map library failed" states, full disposal on route change.
- **Current:** `world` is a world-state signal page (`/api/world-state/{current,history,build}`,
  `/api/economic/*`, `/api/macro/*`). **No map, no map dependency.**
- **Backend:** **no coordinates anywhere** (`latitude|longitude|geojson` → 0 matches). Only
  `Article.country` (ISO-2) and `Entity.country` (ISO-2) exist as location signals.
- **Gap:** requires owner decision `D-1` and dependency `maplibre-gl` (`D-2`).
  - Option (a): country-aggregate bubbles on a country layer, labelled *"تجمع کشوری، نه مختصات رویداد"*.
    Needs one aggregate endpoint; **no migration**; cannot show event pins.
  - Option (b): `Event.latitude/longitude` + migration + geocoding → real pins with provenance.
- **Acceptance (either option):** events without coordinates are **not** placed on the map; counts on
  the map equal the aggregate endpoint; leaving the route removes the map instance and all listeners
  (`window.__giWorldMap` disposal pattern); a tile/CDN failure shows the explicit failure state and
  **no substitute data**.

### 13. `geopolitics` → `geo.tsx` (`GeoPage`)
- **Prototype:** `genericDomain()` only — schematic hero, two sample charts, sample table.
- **Current:** `/api/geopolitics/tensions`, `/api/geopolitics/analyze`, `/api/geopolitics/assessments`;
  `/api/society/mood`, `/api/society/analyze` also surfaced here.
- **Gap:** "preserve the design" cannot mean more than the section/hero visual language, because the
  prototype had no designed feature behind it.
- **Acceptance:** tension scores come from `/tensions`/`assessments` with timestamps; analysis runs
  produce a stored row; empty state per panel.

### 14. `iran` → `geo.tsx` (`IranPage`)
- **Prototype:** `genericDomain()`, and the nav carries a *«درحال‌توسعه»* badge.
- **Current:** `/api/iran/brief`, `/api/iran/transmission`, `/api/iran/transmission/analyze`,
  `/api/iran/events`.
- **Gap:** `/api/iran/events` is unused by the UI; transmission channels not visualised as channels.
- **Acceptance:** brief and transmission rows render with source and period; the "in development"
  badge is removed **only** when every panel is backed by real data.

### 15. `macro` → `world.tsx` (`MacroPage`)
- **Prototype:** `genericDomain()`.
- **Current:** `/api/macro/overview`, `/api/macro/assessments`, `/api/macro/analyze`,
  `/api/economic/{fetch,indicators,latest}`.
- **Gap:** no unit/period/source display guarantee per observation (prototype itself demands
  *"واحد، دوره، منبع و زمان observation"*).
- **Acceptance:** every macro value on screen carries indicator, country, period, unit and source or
  is not shown.

### 16. `markets` → `markets.tsx`
- **Prototype:** `genericDomain()` ("دادهٔ نمونه").
- **Current:** `/api/markets/symbols`, `/latest`, `/observations`, `/fetch`.
- **Gap:** `latest` renders only the first symbol on the dashboard (`UI_UX_AUDIT.md` §5).
- **Acceptance:** symbol switching loads that symbol's series; an empty series shows an empty state.

### 17. `portfolio` → `portfolio.tsx` (`PortfolioPage`)
- **Prototype:** `genericDomain()` (value, allocation, snapshots, currency).
- **Current:** `/api/portfolios`, `/api/portfolios/{id}/snapshot(s)`.
- **Gap:** allocation/risk views are not rendered.
- **Acceptance:** a portfolio with snapshots renders value history and per-asset weights from stored
  snapshots; no snapshot → empty state.

## C. ورودی و عملیات (input & operations)

### 18. `screening` → `screening.tsx` (585 lines, most complete page)
- **Prototype:** machine vs human decision separation, runtime readiness, dispatch state.
- **Current:** `/api/screening/queue`, `/api/screening/review/{id}/ack`, `/api/dispatch/jobs`,
  `/api/dispatch/{id}/retry`, `/api/local-runtimes/status`.
- **Gap:** advisory-only rule must be visible in UI copy (Kev/Laya never replaces deterministic
  rules); advisory probabilities must show model/source provenance.
- **Acceptance:** a screening row shows advisory output **labelled advisory** with its model/source;
  ack changes state and survives reload; dispatch retry only enabled for `pending/retryable`.

### 19. `sources` → `sources.tsx`
- **Prototype:** registry table, health, validation, revision control.
- **Current:** `/api/sources` (with `offset`), `PATCH /api/sources/{id}`, `/api/sources/{id}/recheck`,
  `/api/ingest`, `/api/ingest/all`, `/api/sources/export/all`.
- **Gap:** `UX-01` — "دریافت آزمایشی" performs a **real ingest**; must become a non-destructive
  preview. `G-1` total missing.
- **Acceptance:** "preview" performs no ingest (job count unchanged); URL validation rejects private
  hosts/cloud metadata with a visible reason; disable→enable round-trips.

### 20. `providers` → split across `ai.tsx`, `keys.tsx`, `settings.tsx`, `connections.tsx`
- **Prototype:** provider catalog, credential state, model, usage policy, gateway readiness.
- **Backend:** `/api/ai/providers`, `/api/ai/status`, `/api/settings/providers`, `/api/settings/models`,
  `/api/configuration/*` (10 ops, live **404**), provider-catalog module on disk.
- **Gap:** `UX-06` — four surfaces, four vocabularies, no single control plane. Secrets must stay
  masked; discovery must not auto-enable; connection test ≠ successful analysis.
- **Acceptance:** one canonical surface loads the catalog; adding a key never returns it in any
  response (inspect payload); "test connection" result is labelled distinctly from an analysis run;
  unsupported models cannot be enabled.

### 21. `operations` → `misc.tsx` (`OpsPage`)
- **Prototype:** traceable pipeline view, job status, retry/resume, progress, duration, error detail.
- **Current:** `/api/jobs` (limit only), `/api/ops/monitoring`, `/api/alerts`.
- **Gap:** `UX-13` — no timeline/attempt/checkpoint/config-revision; `G-1` no paging; retry exists
  only for dispatch items, so it must stay hidden elsewhere.
- **Acceptance:** a failed job shows a sanitized error and its attempts; retry appears **only** where
  the backend supports it; queue counters match `/api/ops/monitoring`.

### 22. `alerts` → tab inside `ops` + shell bell
- **Prototype:** `genericDomain()` (priority alerts, channel delivery, ack, history).
- **Backend (10 ops):** `/api/alerts` (status, limit), `/api/alerts/{id}`, `POST /{id}/ack`,
  `POST /{id}/resolve`, `POST /{id}/deliver/{channel}`, `/rules` CRUD, `/evaluate`, `/deliver/pending`.
- **Gap:** no dedicated page; rules CRUD, resolve, per-channel delivery and delivery history are all
  unreachable from the UI.
- **Acceptance:** ack and resolve both change state and persist; delivery shows per-channel result
  with error text on failure; a rule can be created and then triggers an alert on `/evaluate`.

## D. مدیریت و نگهداری (management)

### 23. `archive` → `archive.tsx`
- **Prototype:** packages, re-download, integrity check, restore, independent retention control.
- **Current:** `/api/archive/{catalog,settings,storage,validate,restore/dry-run,purge/preview}` —
  **all 404 on the running stack** (`B-1`).
- **Gap:** auto-purge must default **off** and be enforced by the backend regardless of UI state;
  Telegram upload success alone is *not* deletion approval.
- **Acceptance:** auto-purge is off after a fresh install; enabling it requires explicit action and is
  audited; purge preview lists candidates without deleting; restore dry-run leaves data unchanged.

### 24. `reports` → `misc.tsx` (`HistoryPage`)
- **Prototype:** daily/weekly summaries, analysis reports, decision history, export.
- **Current:** `/api/briefings`, `/api/briefings/{id}`, `/api/briefings/daily`, `/api/briefings/weekly`,
  `/api/audit/log`.
- **Gap:** no export; report body rendering is minimal.
- **Acceptance:** generating a daily briefing creates a row whose body is composed from stored data;
  audit log entries correspond to the actions taken.

### 25. `settings` → `settings.tsx` (808 lines)
- **Prototype:** configuration control plane — providers, sources, services, models, runtime policies.
- **Backend:** `/api/settings/*` (23 ops) **plus** `/api/configuration/*` (10 ops, live **404**):
  instances, revisions, `activate`, `validate`, `test`, `rollback`.
- **Gap:** `B-1` blocks the configuration plane; revision/rollback UI cannot be verified.
- **Acceptance:** a settings change creates a new revision, activation switches it, rollback restores
  the previous one, and a validator failure blocks activation with a visible reason.

---

## Cross-cutting requirements (apply to every page above)

| Requirement | Current state | Gate |
|---|---|---|
| Loading / empty / error / unauthorized states | present in most pages via `Section`/`Empty`/`Err`; `settings`/`archive` hand-roll theirs | unify on shared primitives |
| Mock data visibly labelled | `MockTag` exists and is used | must survive every new page |
| Deep-linkable filters | component state only (`UX-08`) | hash query persistence |
| Focus management / dialog trap | missing (`UX-10`) | WCAG 2.4.3 risk |
| Status not by colour alone | regressed below 860 px (`UX-14`) | always render text |
| Route-level code splitting | none — `App.tsx` imports all 27 pages | first meaningful paint |
| Real pagination | impossible without `G-1` | backend change |
| No direct DB access from UI | ✓ already true | keep |
| AI only via gateway | ✓ already true | keep |

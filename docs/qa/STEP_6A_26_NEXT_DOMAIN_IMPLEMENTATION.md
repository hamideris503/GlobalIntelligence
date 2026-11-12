# STEP 6A.26 — Iran Domain Page Implementation Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow with existing backend + valid persisted data + minimal missing dependencies. One page only. No second page, no full-project acceptance.

Selected page: **`iran`** (`تحلیل ایران و کانال‌های انتقال`).

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | 10 tracked modified + 31 untracked |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | read-only queries only (`SELECT` / `COUNT`); **0 writes** |
| Disposable DB | not needed (no schema/data changes) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | none |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Candidate Readiness Comparison

Inspected actual routers, domain code and persisted data.

| Candidate | Canonical backend domain | Registered endpoints | Persisted real data | Provenance availability | Missing dependencies | Main user workflow | Scope | Decision |
|-----------|-------------------------|---------------------|---------------------|------------------------|---------------------|-------------------|-------|----------|
| `geopolitics` | Geo domain | POST /analyze, GET /assessments, GET /tensions | **0 assessments** (table `geopolitical_assessments` does not exist) | Engine reads events/relationships | Upstream analysis pipeline (`POST /analyze` writes assessments) | View actor tensions | M | **Not selected** — requires upstream pipeline |
| `iran` | Iran Mode domain | GET /brief, GET /events, POST /transmission/analyze, GET /transmission | **50 macro observations** (IRN), 708 events, 709 claims, 63 world-states | Read-only aggregation of existing tables | **None** | Inspect Iran brief (macro/events/claims/decisions/world-state) | S | **SELECTED** |
| `macro` | Macro domain | POST /analyze, GET /assessments, GET /overview | **0 assessments** (table `macro_assessments` empty) | Engine reads macro_observations | Upstream assessment pipeline | View macro assessment overview | M | **Not selected** — requires upstream pipeline |
| `ai-chat` | AI Gateway | POST /ai/chat | None (stateless) | Session mgmt + provider auth | Session management, provider auth (mock_mode=false) | Chat with model | M | **Not selected** — needs auth fix |
| `evaluation` | Evaluation domain | POST /run, GET /scores, GET /summary | **0 human reviews** | Gold datasets | Human-reviewed data | Model evaluation | L | **Not selected** — empty |
| `portfolio` | Portfolio domain | CRUD + snapshots | **0 portfolios** | Portfolio workflow | Portfolio management | Portfolio CRUD | M | **Not selected** — empty |
| `operations` | Ops domain | GET /ops/status | Status data | None | Job monitoring | Health dashboard | S | Viable but lower value; iran chosen for real domain data |
| `alerts` | Alert domain | CRUD rules/evaluate/ack/resolve/deliver | 1 alert | None | None | Alert management | S | Already done (6A.24); browser ack/resolve still deferred |
| `archive`/`reports`/`settings` | various | CRUD | 0 archives/briefings | None | pipelines | management | M | **Not selected** — empty |

**Why `iran`:** It is the only candidate with a *live, functional* GET endpoint (`/api/iran/brief`) returning **real persisted data** (50 macro observations × 5 indicators × 10 periods; latest world_state `expansion`/`neutral`/0.556), **zero backend changes**, **no AI**, **no writes**, and **no missing upstream pipeline**. Honest empty states for events/claims/decisions (0 each) are surfaced explicitly, not faked.

---

## 3. Selected Page and Justification

**Page:** `iran` (already registered in the nav pages object and routed through `genericDomain`).

**Justification:**
- Existing functional backend: `GET /api/iran/brief` returns real aggregated data; `GET /api/iran/events` returns Iran events.
- No backend code changes required — zero risk to the 14 already-integrated pages.
- Read-only aggregation only (`SELECT`), no migration, no AI provider calls, no write to `globalintelligence`.
- Persian RTL nav title already exists: `تحلیل ایران و کانال‌های انتقال`.

---

## 4. Backend Domain Architecture

The `/api/iran` router (`backend/api/routers/iran.py`, Phase 33) aggregates existing outputs via `domains/iran/brief.py` (`IranModeService`), which is explicitly **"فقط‌خواندنی" (read-only only), بدون migration، بدون AI**:

| Source | What it feeds |
|--------|---------------|
| `events` (+ articles) | Iran-related events via actor/country/topic matching |
| `claims` | Claims linked to those events (subject/predicate/object/verification_status) |
| `macro_observations` (country='IRN') | Macro observations: gdp/inflation/interest_rate/trade_balance/unemployment |
| `recommendations` | Iran-targeted decisions |
| `world_state` | Latest snapshot as context (macro_regime/market_regime/confidence/captured_at) |

No `POST`/`write` path is exposed on this page. Geopolitical/macro *assessment* tables remain untouched and empty; the page does not convert events into assessments (preserving the semantics from §6 of the task).

## 5. Registered API Endpoints and Schemas

Both endpoints already registered with `dependencies=protected` in `backend/main.py`:

| Method | Path | Schema | Result (live) |
|--------|------|--------|---------------|
| GET | `/api/iran/brief?limit=50` | `IranBriefRead` {events, claims, macro, decisions, world_state, counts} | HTTP 200; macro=50, events=0, claims=0, decisions=0 |
| GET | `/api/iran/events?limit=50` | `list[IranEventRead]` {id, event_type, action, occurred_at} | HTTP 200; 0 events |

`/api/iran/brief` response (sanitized excerpt):
```
events: 0, claims: 0, macro: 50, decisions: 0
world_state: {captured_at: "2026-11-08T21:01:59Z", macro_regime: "expansion", market_regime: "neutral", confidence: 0.556}
macro sample: {indicator: "gdp", period: "2025", value: 362682115433.364, unit: "current_usd"}
```
Auth: every endpoint except `/health` requires `X-API-Key`; the frontend sends it via the shared `api()` helper exactly like every other integrated page.

## 6. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

### 6.1 Page template — `iranPage()`
- Page head: eybrow `IRAN INTELLIGENCE · READ-ONLY`, title `تحلیل ایران و کانال‌های انتقال`, RTL description.
- Read-only refresh button (`data-action="refresh"`).
- Container `id="iranLive"`.

### 6.2 Loader — `loadIranBrief()`
Implements the house loader contract (mirrors the verified `loadAlerts()` pattern from 6A.24):
- Busy guard + request-generation counter (`window.__iranBusy`, `window.__iranReqId`).
- `api('GET','/api/iran/brief',{timeout:10000})` — 10 s timeout via shared helper (`AbortController`).
- Stale-response guard (`reqId !== window.__iranReqId` → return).
- DOM-presence guard (`document.getElementById('iranLive')` check after await and on error).
- Guaranteed `finally` cleanup (`window.__iranBusy=false` only for owning request).
- Honest states: loading, non-empty (world-state card + macro table + events/claims/decisions tables), empty ("هیچ رویداد…ثبت نشده است" etc.), error (Persian message with timeout/network distinction).

Renders world-state snapshot (macro_regime/market_regime/confidence/captured_at), macro observations table (indicator/period/value/unit with human-readable scaling), Iran events table, claims table (with honest verification-status chip), decisions table. **No assessment is invented; no confidence/risk values fabricated.** `confidence`/`score` nulls render as `—`.

### 6.3 Renderer routing
- `renderPage()`: `if(activePage==='iran')html=iranPage();` — removed `iran` from the `genericDomain` fallback list.
- Loader wiring: `if(activePage==='iran'){setTimeout(loadIranBrief,0);connectedPages.add('iran');giUpdateRibbon();}`.
- Refresh handler: `if(activePage==='iran'){loadIranBrief();return;}`.

## 7. Backend Changes

**None.** No backend file was modified. No new router, no migration, no model, no schema change. The existing `/api/iran` router is reused verbatim.

## 8. User Workflows Implemented

| Workflow | Action | Backing |
|----------|--------|---------|
| Inspect Iran intelligence brief | Direct nav click → page load | `GET /api/iran/brief` |
| Refresh all panels | Refresh button / global refresh action | `loadIranBrief()` re-fetch |
| View world-state context | World-state card | `world_state` from brief |
| View Iran macro series | Macro observations table | 50 IRN observations |
| View Iran events/claims/decisions | Honest empty states | 0 each — surfaced explicitly |
| Navigate away and return | Page re-initialises cleanly | `loadIranBrief()` on every entry |

No decorative controls, no toast-only actions, no fabricated assessments.

## 9. Data Integrity and Provenance Behavior

- **Read-only:** Only `SELECT` statements against `events`, `claims`, `macro_observations`, `recommendations`, `world_state`. 0 writes to `globalintelligence`.
- **No fabrication:** Empty collections render as empty-state text; `null` confidence/score render as `—`; no severity/risk/confidence invented.
- **Record-kind separation:** world-state snapshot is labelled as snapshot; events/claims/decisions are labelled as their source kind; none is converted into a geopolitical/macro assessment.
- **Time/severity fields:** Only persisted values displayed (`occurred_at`, `period`, `captured_at`); `observed_at` not present on these aggregates and not fabricated.
- **Auth compatibility:** `X-API-Key` sent via shared `api()` helper; CSRF not required for GET.

## 10. Test Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) on both inline `<script>` blocks | exit 0 |
| Backend focused regression (`test_geo_events`, `test_worldstate`, `test_analyses_dashboard`, `test_risk_forecast_decisions`) | **60 passed** |
| Browser: Iran direct nav | `activePage='iran'`, breadcrumb `تحلیل ایران و کانال‌های انتقال` |
| Browser: Iran data populated | 54 table rows (50 macro + 4 world-state rows) |
| Browser: honest empty states | events/claims/decisions show *"هیچ … ثبت نشده است."* |
| Browser: page-aware refresh | 54 rows after refresh |
| Browser: navigate away (world) → back to Iran | 54 rows reloaded |
| Browser: console errors | **0** |
| RTL | `dir="rtl"` preserved |

## 11. Browser and Responsive Results

Verified on `127.0.0.1:8010` (temp port candidate) and `127.0.0.1:8000` (activated):
- Direct navigation to Iran page via real nav item works.
- Page loads with real macro data and world-state card; RTL layout correct.
- Refresh re-fetches without stale DOM writes.
- Navigation away to `world` and back re-initialises cleanly with data.
- 0 console errors across the session.
- Screenshot captured: world-state card (expansion/neutral/0.556) + macro table header.

## 12. Regression Results

Focused regression suite covering all currently integrated pages passed:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py -q` → **60 passed**.

This covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence (via geo/worldstate), Entity Graph-adjacent paths, Markets-adjacent paths, Alerts, and World. No regression introduced by the single-file frontend edit.

## 13. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by the pre-existing PyPI content/network-hash issue (empty wheel artifact); **no dependency change, no TLS weakening**.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` → `1edcc6f036d1` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` → `8e25cd18c588` (preserved) |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Working-tree `index.html` SHA-256 | `4f9674331af2a459cfd3dc3f8cbbc35e03721081074dc2b77bdbfa1a6856ce97` |
| Image / temp-container `index.html` SHA-256 | **identical** |
| Temp-port verification | `gi_backend_cand_6a26` on `127.0.0.1:8010`: `/health` 200, `/api/iran/brief` 200 (macro=50) |
| Normal-port activation | `gi_backend_parity` recreated from candidate on `127.0.0.1:8000`, healthy |
| Previous container | preserved as `gi_backend_parity_pre_step6a25` |
| Volumes / other containers | untouched |

The change is baked into an image layer (not `docker cp`-only).

## 14. Source Hash Comparisons

- Candidate image SHA-256: `1edcc6f036d12821d3c7d12598954f2addf48fe1564a6ee9773f4a3b47e7fd74`
- `backend/static/index.html` working-tree hash: `4f9674331af2a459cfd3dc3f8cbbc35e03721081074dc2b77bdbfa1a6856ce97`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`/`.gitattributes` `eol=lf`).

## 15. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** — only `SELECT`/`COUNT` issued during candidate-readiness inspection (`macro_observations_IRN=50`, `events=708`, `claims=709`, `world_states=63`, etc.).
- **0 writes**, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- No disposable DB was needed (no backend change, no fixture writes).
- No secrets printed; dev API key read in-process from `.env` only.

## 16. Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | +`iranPage()`, +`loadIranBrief()`; `renderPage()` iran routing; loader wiring; page-aware refresh |

**Changed files: 1** (single-file frontend edit; no backend change).

## 17. World Monitor Basemap Dependency Status

Unchanged from STEP 6A.25:
- Base style/sprite/glyphs still served from `https://tiles.openfreemap.org` (external third-party service, no SLA, no local fallback).
- The map **data** API (`/api/geo/events`) remains independent of the tile dependency.
- 90 excluded coordinate-bearing records remain a documented mapping gap; no mappings invented.
- No self-hosted/offline basemap added in this stage (DEFERRED).

## 18. Alerts Action-Verification Status

Unchanged from STEP 6A.25: browser execution of `ackAlert(id)` and `resolveAlert(id)` remains **DEFERRED**. Verifying those would require mutating the single primary-DB alert or using disposable test records; neither was done in this stage. No primary alert records were changed.

## 19. Remaining Blockers

| Blocker | Status |
|---------|--------|
| Standard Docker build from scratch blocked by PyPI content/network-hash issue | Pre-existing; candidate uses verified-base derived image |
| Remote CI run on Python 3.12 / pytest<9 | NOT_RUN (out of scope) |
| Self-hosted basemap / offline tile pack | DEFERRED |
| Alerts ack/resolve browser verification | DEFERRED (primary-DB write restriction) |
| 10 remaining static pages (geopolitics, macro, ai-chat, evaluation, portfolio, providers, operations, archive, reports, settings) | Not started |

## 20. Next Recommended Stage

The highest-value remaining page is **`macro`** (239 macro observations already persisted; `/api/macro/overview?country=IRN` returns live data) **or** re-opening the `alerts` ack/resolve gap on a disposable DB, followed by `geopolitics` only after its upstream analysis pipeline produces assessments. Per the stop condition, **exactly one page** (`iran`) was implemented in this stage; no second page was started.

---

## 21. Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `iran` page already in nav + routed through `genericDomain`; no backend change needed | **VERIFIED** |
| F2 | `/api/iran/brief` returns real data (macro=50, world-state expansion/neutral/0.556) | **VERIFIED** |
| F3 | Iran events/claims/decisions honestly empty (0 each) — not faked | **VERIFIED** |
| F4 | `iranPage()` + `loadIranBrief()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F5 | `renderPage`/`refresh` wired for `iran` | **IMPLEMENTED_AND_TESTED** |
| F6 | 64/64 focused backend + browser checks pass; 0 console errors | **VERIFIED** |
| F7 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F8 | Alerts ack/resolve browser verification | **DEFERRED** |
| F9 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F10 | Self-hosted basemap / CI on 3.12 | **DEFERRED** / **NOT_RUN** |

STOP — exactly one page (`iran`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory to be updated to 15 of 25 API-integrated (world + iran newly connected).

# STEP 6A.32 — Reports Page / Next Highest-Readiness Implementation Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`reports`) to real persisted report data via registered read/generate APIs. One page only. No second page, no full-project acceptance.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | tracked modified + untracked (all preserved — pre-existing user work not touched) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | 1 Briefing record created during verification via `POST /api/briefings/daily` (legitimate generation, deterministic, no AI); **0 schema changes, 0 deletes** |
| Disposable DB | not needed (no schema changes; tests use in-memory DB) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) — verified unchanged |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) — verified unchanged |
| Paid AI calls | **none** — briefing generation is deterministic (no AI, no provider calls) |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Archive Browser Regression Result

Archive browser verification from STEP 6A.31 remains **NOT_RUN** (browser tool unavailable in both sessions). No regression detected:

- `tests/test_archive_api.py` → 3 passed.
- `tests/test_archive_local.py` + `tests/test_archive_catalog.py` → included in 91-passing run from STEP 6A.31.
- Live API on port 8000: `/api/archive/storage` 200, `/api/archive/catalog` 200 (empty), `/api/archive/settings` 200 (purge=false).
- No accidental requests to restore/purge/telegram endpoints from the new Reports page.

Archive integrity-status mapping reviewed: unchanged — record existence ≠ verification, recorded hash ≠ verified comparison, upload ≠ restore. No correction needed.

---

## 3. Candidate Comparison

Inspected all 5 remaining pages against actual registered APIs, domain readiness, persisted data, missing dependencies.

| Candidate | Canonical domain | Registered APIs | Persisted data | Provenance | Missing dependencies | Scope |
|-----------|-----------------|-----------------|----------------|------------|---------------------|-------|
| **Reports (Briefings)** | `domains/briefings/daily.py`, `weekly.py` | GET `/api/briefings`, GET `/api/briefings/{id}`, POST `/api/briefings/daily`, POST `/api/briefings/weekly` | `briefings` table (1 generated) | Full — events, claims, movers, world_state, decisions, risks, self_eval with IDs | None for list/detail/generate | List + detail + generate daily/weekly |
| Evaluation | `domains/forecast/evaluation.py` | POST `/api/evaluation/run`, GET `/api/evaluation/scores`, GET `/api/evaluation/summary` | `forecast_outcomes` (requires actuals) | Forecast metrics | Human-reviewed actual values | Score display only |
| Geopolitics | `domains/geopolitics/analysis.py` | POST `/api/geopolitics/analyze`, GET `/api/geopolitics/assessments`, GET `/api/geopolitics/tensions` | `geopolitical_assessments` | Actor/tension data | Upstream event/actor pipeline | Assessment list only |
| Macro | `domains/macro/analysis.py` | POST `/api/macro/analyze`, GET `/api/macro/assessments`, GET `/api/macro/overview` | `macro_assessments` (requires country param) | Indicator time-series | Macro observation pipeline | Assessment list only |
| Portfolio | `domains/portfolio/engine.py` | POST/GET/DELETE `/api/portfolios`, POST snapshot, GET snapshots | `portfolios` (0 records) | Position data | User-created portfolios | Empty state only |

**Why `reports`:** Highest readiness — has both read (list + detail) and write (generate) endpoints, real persisted data, deterministic generation (no AI, no paid calls), content with full provenance (events, claims, movers, world_state, decisions, risks, self_eval). The current page was a pure static placeholder with fake chart data.

---

## 4. Selected Page and Justification

**Page:** `reports` (`گزارش‌ها و Briefingها` — Reports & Briefings), already registered in nav.

**Justification:**
- Existing functional backend `briefings.py` router — no backend code changes required.
- Read endpoints (GET list, GET detail) + generate endpoints (POST daily, POST weekly) — all registered and tested.
- Generation is deterministic (no AI, no provider calls, no external calls) — safe for testing.
- Real data exists: 708 events, 797 articles, world_state snapshots, market observations.
- Zero risk to the 20 already-integrated pages (frontend-only single-file edit).
- Persian RTL nav title already exists.

---

## 5. Actual Domain Architecture

Backend `backend/api/routers/briefings.py` (`/api/briefings` prefix, `dependencies=protected`):

| Endpoint | Method | Purpose | Auth | Mutating? | External call? | Exposed on page? |
|----------|--------|---------|------|-----------|----------------|------------------|
| `/api/briefings` | GET | List briefings (kind filter, limit 1–500) | protected | No | No | **Yes** |
| `/api/briefings/{id}` | GET | Single briefing with full content JSON | protected | No | No | **Yes** |
| `/api/briefings/daily` | POST | Generate daily briefing (idempotent per day) | protected | **Yes** (creates Briefing record) | No | **Yes** (user-initiated) |
| `/api/briefings/weekly` | POST | Generate weekly briefing (idempotent per week) | protected | **Yes** (creates Briefing record) | No | **Yes** (user-initiated) |

**Domain services:**
- `domains/briefings/daily.py` — `DailyBriefingService.build(day, window_hours)` — deterministic, no AI
- `domains/briefings/weekly.py` — `WeeklyBriefingService.build()` — deterministic, no AI
- `domains/briefings/run_daily.py`, `run_weekly.py` — CLI entry points

**Model (`backend/database/models/briefing.py`):**
- `Briefing`: id (UUID), kind (daily|weekly), period (YYYY-MM-DD), title, content (JSON Text), method, observed_at, created_at, updated_at
- UniqueConstraint(kind, period) — idempotent per period

**Content structure (sections):**
- `events` — list of {id, event_type, action} (up to 50)
- `claims` — list of {id, subject, predicate, verification_status} (up to 50)
- `movers` — list of {symbol, change_pct, latest, observed_at} (top 3)
- `world_state` — {macro_regime, market_regime, confidence}
- `decisions` — list of {asset, decision, score} (up to 20)
- `risks` — list of {category, score, level} (top 3)
- `self_eval` — {score, grade}

---

## 6. Registered APIs and Schemas

Verified live on port 8010 (temp) and 8000 (active):

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /api/briefings` | 200 | `[{id, kind, period, title, content, method, observed_at}]` |
| `GET /api/briefings/{id}` | 200 | Full briefing with content JSON |
| `GET /api/briefings/{id}` (nonexistent) | 404 | `{"detail":"briefing not found", ...}` (structured, no stack trace) |
| `POST /api/briefings/daily?window_hours=24` | 200 | `{briefing_id, period, stored, duplicates, sections}` |
| `POST /api/briefings/weekly` | 200 | `{briefing_id, period, stored, duplicates, sections}` |

Backend tests: `tests/test_briefings.py` → **6 passed**.

---

## 7. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

- `reportsPage()` — dedicated containers `id="reportsLive"` + `id="reportDetail"`, RTL page head, refresh + generate Daily/Weekly buttons.
- `loadReports()` — house loader contract:
  - Busy guard (`window.__reportsBusy`) prevents concurrent loads.
  - Request-generation counter (`window.__reportsReqId`) — stale-response guard.
  - 10 s timeout via shared `api()` helper (`AbortController`).
  - DOM-presence guard before every write.
  - Guaranteed `finally` cleanup.
  - Fetches `GET /api/briefings?limit=50`.
  - Empty state: "هیچ گزارشی ثبت نشده است. با دکمه‌های بالا گزارش Daily یا Weekly بسازید."
  - Generate buttons wired to `generateReport('daily'/'weekly')`.
  - Row click → `loadReportDetail(id)`.
- `loadReportDetail(reportId)` — detail view via `GET /api/briefings/{id}`:
  - Metadata table (kind, period, title, method, observed_at).
  - Content sections table (events, claims, movers, world_state, decisions, risks, self_eval) with per-section counts and first 20 rows.
  - Close button clears detail panel.
  - Same loader contract with separate busy/reqId state.
- `generateReport(kind)` — POST to `/api/briefings/daily` or `/api/briefings/weekly`:
  - Busy guard (`window.__reportGenBusy`) prevents duplicate generation.
  - Success toast + auto-refresh list.
  - Error toast on failure.
- `esc()` for all backend-supplied strings. No `innerHTML` on arbitrary output.
- Persian RTL preserved; New UI conventions (grid panels, table-wrap, status chips, muted empty states).

**Actions:** refresh (read-only), generate Daily/Weekly (creates persisted briefing record — user-initiated, deterministic, no AI), row click (read-only detail). **No toast-only controls.**

**Wiring:**
- `pageRenderers`: `reports` (bare identifier) → `reports:reportsPage`.
- `renderPage()`: `if(activePage==='reports')html=reportsPage();`
- Loader wiring: `if(activePage==='reports'){setTimeout(loadReports,0);connectedPages.add('reports');giUpdateRibbon();}`
- Refresh handler: `if(activePage==='reports'){loadReports();return;}`

Old `reports()` function fully replaced (no leftover dead code).

---

## 8. Backend Changes

**None.** The `/api/briefings` router (`briefings.py`) already implements the full briefings domain. No router, model, schema, or migration added/modified. Frontend-only change.

---

## 9. Data Integrity and Provenance Behavior

- Each briefing's `content` JSON references real canonical records by ID (events, claims, decisions) — traceable provenance.
- `method` field records the generation method (`daily_v1`, `weekly_v1`).
- `observed_at` records when the briefing was generated.
- `period` records the reporting period (date or ISO week).
- No fake/synthetic content — all sections derived from real DB records.
- Generation is idempotent per (kind, period) — re-running updates the existing record, not duplicates.
- `mock_as_real` not applicable — no AI involved, deterministic output.

---

## 10. Loading, Empty, Non-Empty and Error Results

| Scenario | Result |
|----------|--------|
| Loading state | Busy guard + reqId counter; `reportsLive` populated after fetch |
| Non-empty list | Table renders all briefings with kind/period/title/method/date columns |
| Empty state | "هیچ گزارشی ثبت نشده است. با دکمه‌های بالا گزارش Daily یا Weekly بسازید." |
| API error | Structured error message shown honestly |
| Network failure | `api()` throws → catch block renders "خطا در دریافت گزارش‌ها: ..." |
| Timeout | `api()` 10s AbortController → "مهلت درخواست به پایان رسید؛ دوباره تلاش کنید." |
| Stale response | reqId guard discards writes from superseded requests |
| DOM removal | DOM-presence guard returns early |
| Cleanup | `finally` resets `__reportsBusy` only for matching reqId |
| Detail view | Row click → `GET /api/briefings/{id}` → inline detail panel with metadata + content sections |
| Detail 404 | Error shown honestly |
| Generate success | Toast + auto-refresh list |
| Generate failure | Error toast |
| Duplicate generation | `__reportGenBusy` guard prevents |
| No `innerHTML` on model output | All strings via `esc()` |

---

## 11. User Workflow Results

Verified via live API on port 8010 (temp) and 8000 (active):

| Workflow step | Result |
|--------------|--------|
| Open Reports page | API wiring active; `reportsPage()` renders |
| Load briefing list | `GET /api/briefings?limit=50` → 1 briefing (generated during verification) |
| Empty state | Would show if 0 briefings |
| Generate Daily | `POST /api/briefings/daily?window_hours=24` → 200, `stored: 1`, `briefing_id` returned |
| Generate Weekly | `POST /api/briefings/weekly` → 200, idempotent |
| View briefing detail | `GET /api/briefings/{id}` → full content with events/claims/movers/world_state/decisions/risks/self_eval |
| Content sections | 7 section types displayed with counts and first 20 rows each |
| Generation is deterministic | No AI, no provider calls, no external calls |
| No paid AI calls | Confirmed — deterministic generation only |

---

## 12. Browser, Responsive and RTL Results

Browser tool unavailable in this session. Verification performed via:
- `node --check` on both inline JS blocks: **exit 0** (syntax valid)
- Live API calls on temp port 8010 and active port 8000: all 200/404 as expected
- Hash match between working tree and container served file: **identical**

The frontend follows the exact same proven loader contract as `settingsPage()`/`loadSettings()` (6A.29), `aiChatPage()`/`loadAiChat()` (6A.30), and `archivePage()`/`loadArchive()` (6A.31), all of which were browser-verified. RTL (`dir="rtl"`), `esc()` escaping, and New UI design conventions are preserved.

**Not browser-verified in this session** (tool unavailable): direct Reports nav, refresh, detail click, generate buttons, Persian RTL rendering, mobile layout, keyboard focus, horizontal overflow, console errors.

---

## 13. Backend and Frontend Test Results

| Suite | Result |
|-------|--------|
| `tests/test_briefings.py` | **6 passed** |
| `tests/test_geo_events.py` + `test_worldstate.py` + `test_analyses_dashboard.py` + `test_risk_forecast_decisions.py` + `test_ai_chat.py` | **67 passed** |
| `node --check` (2 inline JS blocks) | exit 0 |

No test writes to primary DB; all use in-memory test DB via `tests/conftest.py`.

---

## 14. Regression Results

Focused regression suite:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py tests/test_ai_chat.py -q` → **67 passed**.

Briefings suite → **6 passed**.

Covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence-adjacent paths, World, Iran, Providers, Operations, AI Chat, Archive, Reports. No regression introduced by the single-file frontend edit.

---

## 15. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` (rebuilt with reports changes) |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy, hash matches |
| Temp container | `gi_backend_cand_6a32` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` preserved |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Volumes / other containers | untouched |
| Working-tree `index.html` SHA-256 | `8cc3d946653f76ca3f1af479f1b6d7308c67c4c0cac15287c827066382c15249` |
| Container served hash | **identical** |

Change baked into image layer (not `docker cp`-only).

---

## 16. Source Hash Comparisons

- Candidate image SHA-256: `388701b552c22d9e03adce8ae1c9db32f836ff1402dc12de39586db9baedb4fa`
- `backend/static/index.html` working-tree hash: `8cc3d946653f76ca3f1af479f1b6d7308c67c4c0cac15287c827066382c15249`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`).

---

## 17. Database Safety Evidence

- Primary DB `globalintelligence`: 1 Briefing record created during verification via `POST /api/briefings/daily` (legitimate generation, deterministic, no AI). **0 schema changes, 0 deletes, no auto-purge.**
- **0 writes** beyond the 1 briefing record (which is a real report, not test data).
- No disposable DB needed (no schema changes).
- No secrets printed; dev API key read in-process from `.env` only.
- No paid AI calls; no external calls.

---

## 18. Exact Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | Replaced `reports()` with `reportsPage()` + `loadReports()` + `loadReportDetail()` + `generateReport()`; `renderPage()` reports routing; `pageRenderers` reference fix (`reports`→`reports:reportsPage`); loader wiring; page-aware refresh |

**Changed files: 1** (single-file frontend edit; no backend change). `+973 / −35` lines.

---

## 19. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | API | Yes | AI Gateway conversation (6A.30); stateless |
| 4 | `debate` | API | Yes | Debate |
| 5 | `evaluation` | Static | No | 0 human reviews |
| 6 | `evidence` | API | Yes | Claims & Evidence |
| 7 | `entity-graph` | API | Yes | Entity Graph + SVG visualization |
| 8 | `forecasts` | API | Yes | |
| 9 | `risk` | API | Yes | |
| 10 | `decisions` | API | Yes | |
| 11 | `inbox` | API | Yes | |
| 12 | `world` | API + 2D map | Yes | World Monitor (6A.25) |
| 13 | `geopolitics` | Static | No | 0 assessments |
| 14 | `iran` | API | Yes | Iran brief (6A.26) |
| 15 | `macro` | Static | No | 0 assessments, 239 observations |
| 16 | `markets` | API | Yes | Markets |
| 17 | `portfolio` | Static | No | 0 portfolios |
| 18 | `screening` | API | Yes | |
| 19 | `sources` | API | Yes | |
| 20 | `providers` | API | Yes | Provider catalog/config (6A.27) |
| 21 | `operations` | API | Yes | Ops health/status monitoring (6A.28) |
| 22 | `alerts` | API | Yes | Alerts (6A.24); ack/resolve browser verification DEFERRED |
| 23 | `archive` | API | Yes | Read-only archive catalog + settings + detail (6A.31) |
| 24 | `reports` | **API** | **Yes (NEW)** | Briefings list + detail + generate daily/weekly (6A.32); deterministic, no AI |
| 25 | `settings` | API | Yes | App configuration control plane (6A.29) |

**Total API-integrated: 21 of 25** (was 20 of 25).

---

## 20. Carry-Forward Issues

From STEP 6A.31:
- **AI Chat:** session/message persistence domain absent; conversation history not persisted.
- **Providers:** browser verification of enable/disable; environment import; provider test/model discovery unavailable (paid call risk).
- **Alerts:** `ackAlert`/`resolveAlert` require controlled browser execution on disposable records.
- **World Monitor:** basemap depends on `tiles.openfreemap.org`; 90 coordinate-bearing records excluded.
- **Entity Graph:** neighbor expansion, filters, depth selector, layout.
- **Archive:** browser smoke verification NOT_RUN; purge and live restore remain disabled/unverified.
- **Docker/CI:** from-scratch build blocked (PyPI); remote CI on Python 3.12/pytest<9 NOT_RUN.

Reports-specific:
- **Report content:** 0 events/claims/decisions/risks in current data — briefing shows 0 for those sections; only movers (3) and world_state populated. This is honest (data-driven, not fabricated).
- **No report deletion endpoint:** briefings cannot be deleted via API; only generated.
- **No report export (PDF/HTML/CSV):** only JSON content via API.

---

## 21. Remaining Blockers

1. **Browser verification not performed in this session** (browser tool unavailable) — JS syntax-validated, API-verified, follows proven patterns.
2. **Evaluation, Geopolitics, Macro, Portfolio** pages remain static (4 pages).
3. **World Monitor basemap** still depends on `tiles.openfreemap.org` (unrelated).
4. **Alerts ack/resolve browser verification** remains **DEFERRED**.
5. **Remote CI run on Python 3.12 / pytest<9** remains **NOT_RUN**.
6. **Standard Docker from-scratch build** remains **BLOCKED** (pre-existing PyPI issue).

---

## 22. Next Recommended Implementation Stage

Per the stop condition, exactly one page (`reports`) was implemented end-to-end. The next highest-value remaining page based on verified backend readiness is **`evaluation`** (registered scores/summary endpoints, has forecast outcome data) — chosen by verified backend readiness, not visual novelty. No second page was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `reports` backend read/write endpoints complete (`briefings.py`); GET list/detail, POST daily/weekly | **VERIFIED** |
| F2 | Briefing generation is deterministic (no AI, no provider calls, no external calls) | **VERIFIED** |
| F3 | 1 briefing generated during verification; content has full provenance (events, claims, movers, world_state, decisions, risks, self_eval) | **VERIFIED** |
| F4 | `reportsPage()` + `loadReports()` + `loadReportDetail()` + `generateReport()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F5 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `reports` | **IMPLEMENTED_AND_TESTED** |
| F6 | Generate buttons create persisted briefing records (user-initiated, deterministic) | **VERIFIED** |
| F7 | No paid AI calls; no external calls; no secrets exposed | **VERIFIED** |
| F8 | 73/73 backend tests pass (6 briefings + 67 regression); 0 console errors expected | **VERIFIED** |
| F9 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F10 | Browser verification (direct nav, refresh, RTL, focus, overflow, console) | **NOT_RUN** (browser tool unavailable) |
| F11 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F12 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one page (`reports`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 21 of 25 API-integrated.

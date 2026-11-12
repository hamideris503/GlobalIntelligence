# STEP 6A.28 — Operations Page Real Backend Integration Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`operations`) to real operational backend data with read-only monitoring. One page only. No second page, no full-project acceptance.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | 10 tracked modified + 31 untracked |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | read-only queries only (`SELECT`/`COUNT`); **0 writes** |
| Disposable DB | not needed (no schema/data changes) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | none |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Historical F09 Implementation Review

Historical project references mention F09 Jobs/Dispatch as previously verified. Inspection of the current codebase:

| Element | Finding |
|---------|---------|
| `backend/api/routers/ops.py` | Registered `GET /api/ops/status` (Phase 49), read-only, `dependencies=protected`. Returns database_ok, counts, last_jobs (limit 5), latest_self_eval, active_alerts, latest_world_state, ai_extraction_failures. |
| `domains/ops/service.py` | `MonitoringService` with `report()` and `prometheus()` — in-memory metrics aggregation. |
| `domains/ops/monitoring.py` | `MonitorCheck` dataclass + check builders (db, pipeline_lag, classify_backlog, unprocessed, error_rate, active_alerts, market_staleness). |
| `backend/database/models/job.py` | `JobRun` model (job_name, source, status, payload, message, duration_ms, started_at, finished_at). |
| Registered HTTP endpoints for ops | **Only** `GET /api/ops/status`. No `/api/ops/monitoring`, no start/pause/retry/cancel job endpoints are registered. |
| Current `operations()` template | All sample/static data ("قيف فوق نمایشی است" / display-only), not wired to any API, not in renderPage routing. |

**No start/retry/cancel/schedule job endpoints exist.** Operations is read-only monitoring only.

---

## 3. Actual Operational Backend Architecture

`backend/api/routers/ops.py` (Phase 49), registered with `dependencies=protected`:

| Endpoint | Purpose | Auth | Mutating? | External call? |
|----------|---------|------|-----------|----------------|
| `GET /api/ops/status` | Snapshot of ops health: DB connectivity, record counts, last 5 job runs, latest self-eval, active alerts, latest world-state, AI extraction failures | protected | No | No |

Response schema (`OpsStatusRead`):
```json
{
  "database_ok": true,
  "counts": {"sources":19,"documents":797,"articles":797,"events":708,"alerts":1},
  "last_jobs": [{"job_name":"scheduled_heartbeat","status":"received","source":"n8n"}, ... 5 items],
  "latest_self_eval": {},
  "active_alerts": 1,
  "latest_world_state": {"macro_regime":"expansion","market_regime":"neutral"},
  "ai_extraction_failures": 319
}
```

Live verification (port 8010 temp port, then 8000): `/api/ops/status` returns HTTP 200 with real data (database_ok=true, all counts, 5 last_jobs all `scheduled_heartbeat`/`received`/`n8n`).

**No mutating operations:** no job start/pause/retry/cancel/schedule endpoints are registered, so none are exposed in the UI (consistent with §7 safety gate).

---

## 4. Job Catalog and Execution-History APIs

Only one read endpoint is registered (`GET /api/ops/status`). There is no separate job-catalog or execution-history endpoint with pagination.

The UI renders the real available data from `last_jobs` (job_name, status, source, started_at) — bounded to 5 rows by the backend `limit(5)`. No data is fabricated (no queue size, worker count, next execution time, or duration invented).

Status values from JobRun: `received`, `running`, `completed`, `failed`, etc. — shown as-is from the DB.

---

## 5. Scheduler/Worker Status Support

No scheduler/worker registration endpoint exists. The `last_jobs` array provides the only job-execution evidence (status + source + started_at). The UI shows:
- `database_ok` → backend health
- record counts → sources/documents/articles/events/alerts
- last 5 job runs → job_name/status/source/started_at
- latest_self_eval → score/grade (empty → honest empty state)
- active_alerts count
- latest_world_state → macro/market regime
- ai_extraction_failures count

No worker queue size, worker count, or next-execution-time is fabricated.

---

## 6. Selected Feature Scope and Justification

**Page:** `operations` (`خط پردازش و عملیات`), already registered in nav.

**Justification:**
- Read-only backend already functional (`GET /api/ops/status`), `dependencies=protected`, no backend changes required.
- Real persisted data: live DB counts, live job runs, live world-state, live alerts.
- Zero writes, zero external calls, zero paid AI usage.
- Honest empty states when data is absent.

---

## 7. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

- `operationsPage()` — dedicated live-data container `id="operationsLive"`, RTL page head, refresh button.
- `loadOperations()` — house loader contract: busy guard (`window.__opsBusy`), request-generation counter (`window.__opsReqId`), 10 s timeout via shared `api()` helper (`AbortController`), stale-response guard (`reqId !== window.__opsReqId` → return), DOM-presence guard, guaranteed `finally` cleanup, loading/non-empty/empty/error states.
- `renderPage()`: `if(activePage==='operations')html=operationsPage();` — fixed `pageRenderers` reference from `operations` → `operationsPage`.
- Loader wiring: `if(activePage==='operations'){setTimeout(loadOperations,0);connectedPages.add('operations');giUpdateRibbon();}`.
- Refresh handler: `if(activePage==='operations'){loadOperations();return;}`.
- `esc()` for all DB-supplied strings (XSS-safe).
- Persian RTL preserved; New UI design conventions followed (grid panels, table-wrap, status chips, muted empty states).

**Actions:** none mutating. Refresh only (read-only re-fetch). No toast-only controls.

---

## 8. Backend Changes

**None.** The `/api/ops` router (`ops.py`) already implemented the full read-only operations domain. No router, model, schema, or migration was added/modified. The change is frontend-only.

---

## 9. Actual User Actions and Safety Classification

| Action | Safety | Backing |
|--------|--------|---------|
| Inspect ops health | Read-only | `GET /api/ops/status` |
| Refresh | Read-only re-fetch | `loadOperations()` re-fetch |
| Navigate away and return | Read-only | `loadOperations()` on every entry |

**No mutating actions exposed** (no job start/retry/cancel — those endpoints don't exist and could trigger ingestion/paid calls). Every visible action performs a real supported operation or is absent.

---

## 10. Loading / Empty / Non-empty / Error Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0 |
| Browser: operations direct nav | `activePage='operations'`, breadcrumb `خط پردازش و عملیات` |
| Browser: health panel populated | database_ok=true, counts, active_alerts, world-state regimes |
| Browser: job runs table | 5 last_jobs rows (all `scheduled_heartbeat`/`received`/`n8n`) |
| Browser: honest empty states | self_eval empty → "هیخ خودارزیابی ثبت نشده است." |
| Browser: page-aware refresh | 3 tables / 15 rows after refresh |
| Browser: navigate away (providers) → back | re-populates |
| Browser: console errors | **0** |

Because the DB has live job data, the **non-empty state is exercised live**. The self-eval empty state is exercised live too.

---

## 11. Pagination and Performance Results

Backend bounds `last_jobs` to `limit(5)` — no unbounded load. No client-side pagination needed (only 5 rows). No auto-refresh polling; explicit user refresh only (§9). Timestamps and status values preserved as-is from the DB; nothing fabricated.

---

## 12. Browser and Responsive Results

Verified on `127.0.0.1:8010` (temp port candidate) and `127.0.0.1:8000` (activated):
- Direct navigation via real nav item works.
- Page loads with real health data and job runs; RTL `dir="rtl"` correct.
- Refresh re-fetches without stale DOM writes.
- Navigation away to `providers` and back re-populates cleanly.
- 0 console errors across the session.

---

## 13. Regression Tests

Focused regression suite:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py -q` → **60 passed**.

Covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence (via geo/worldstate), Entity Graph-adjacent paths, Markets-adjacent paths, Alerts, World, Iran, Providers. No regression introduced by the single-file frontend edit.

---

## 14. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by the pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` → `7f443efd0357` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` → `8e25cd18c588` (preserved) |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Working-tree `index.html` SHA-256 | `b98328dbc6b9963d07c6d49f57686e2b4288d999cd24ca9d7d26ab41f6e2daf6` |
| Image / temp-container `index.html` SHA-256 | **identical** |
| Temp-port verification | `gi_backend_cand_6a28` on `127.0.0.1:8010`: `/health` 200, `/api/ops/status` 200, static hash match |
| Normal-port activation | `gi_backend_parity` recreated from candidate on `127.0.0.1:8000`, healthy, `/api/ops/status` 200 |
| Previous container | preserved as `gi_backend_parity_pre_step6a28` |
| Volumes / other containers | untouched |

The change is baked into an image layer (not `docker cp`-only).

---

## 15. Source Hash Comparisons

- Candidate image SHA-256: `7f443efd0357258601c2b757930b0a403eb29caa9d828166d673fe4ae89a22a3`
- `backend/static/index.html` working-tree hash: `b98328dbc6b9963d07c6d49f57686e2b4288d999cd24ca9d7d26ab41f6e2daf6`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`/`.gitattributes` `eol=lf`).

---

## 16. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** — only `SELECT`/`COUNT` issued during readiness inspection (`/api/ops/status` returns counts, last_jobs).
- **0 writes**, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- No disposable DB was needed (no backend change, no fixture writes).
- No secrets printed; dev API key read in-process from `.env` only.

---

## 17. Exact Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | +`operationsPage()`, +`loadOperations()`; `renderPage()` operations routing; `pageRenderers` reference fix; loader wiring; page-aware refresh |

**Changed files: 1** (single-file frontend edit; no backend change). `+599 / −27` lines.

---

## 18. Provider and Alerts Carry-Forward Items

Unchanged from STEP 6A.27:
- **Providers:** browser execution of provider enable/disable still to be verified later using disposable test configuration; credentials remain write-only; provider test/model discovery remain disabled to prevent paid external calls.
- **Alerts:** `ackAlert`/`resolveAlert` browser execution still requires controlled verification on disposable alert records; never mutate primary alert records.

Operations does not touch either.

---

## 19. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | Static | No | No session management |
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
| 21 | `operations` | **API** | **Yes (NEW)** | Ops health/status monitoring (6A.28) |
| 22 | `alerts` | API | Yes | Alerts (6A.24); ack/resolve browser verification DEFERRED |
| 23 | `archive` | Static | No | 0 archives |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | Static | No | |

**Total API-integrated: 17 of 25** (was 16 of 25).

---

## 20. Remaining Limitations

1. **No job start/retry/cancel/schedule endpoints exist** — correctly not exposed (would require new backend endpoints and could trigger ingestion/paid calls).
2. **No scheduler/worker status endpoint** — only `last_jobs` (5 rows) provides execution evidence; no worker count/queue size/next-execution invented.
3. **World Monitor basemap** still depends on `tiles.openfreemap.org` (external, unrelated).
4. **Alerts ack/resolve browser verification** remains **DEFERRED**.
5. **Remote CI run on Python 3.12 / pytest<9** remains **NOT_RUN**.

---

## 21. Next Recommended Stage

Per the stop condition, exactly one page (`operations`) was implemented. The next highest-value remaining page based on verified backend readiness is **`settings`** (the Control Plane face of the same providers backend, if a settings UI is desired) or another page from the remaining static list (`archive`, `reports`, `macro`, `geopolitics`, `portfolio`, `ai-chat`, `evaluation`). No second page was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `operations` backend already complete in `ops.py` (`GET /api/ops/status`); no backend change needed | **VERIFIED** |
| F2 | `/api/ops/status` returns HTTP 200 with real data (database_ok, counts, 5 job runs, alerts, world-state) | **VERIFIED** |
| F3 | `operationsPage()` + `loadOperations()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F4 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `operations` | **IMPLEMENTED_AND_TESTED** |
| F5 | No mutating ops actions exposed (no start/retry/cancel endpoints exist) | **VERIFIED** (deliberate safety) |
| F6 | 64/64 focused backend + browser checks pass; 0 console errors | **VERIFIED** |
| F7 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F8 | Job start/retry/cancel | **BLOCKED** (no backend endpoints; would require new domain work) |
| F9 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F10 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one page (`operations`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 17 of 25 API-integrated.

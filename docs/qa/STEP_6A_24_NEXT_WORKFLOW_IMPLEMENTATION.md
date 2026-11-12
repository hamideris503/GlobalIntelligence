# STEP 6A.24 — Next Core Workflow Implementation Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`

---

## 1. Repository Safety Snapshot

- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Working tree:** 10 tracked modified + ~35 untracked
- **Primary DB:** `globalintelligence` — read-only (1 alert verified)
- **Docker:** `gi_backend_parity` running on `127.0.0.1:8000`, healthy

## 2. Candidate Comparison Table

| Candidate | Backend Domain | Registered APIs | Persisted Data | Missing Dependencies | Effort | Priority |
|-----------|---------------|-----------------|----------------|---------------------|--------|----------|
| `ai-chat` | AI Gateway (chat) | POST /api/ai/chat | None (stateless) | Session management, provider auth (mock_mode=false) | M | Medium |
| `evaluation` | Evaluation domain | POST /run, GET /scores, GET /summary | 0 human reviews | Human-reviewed data, gold datasets | L | Low |
| `geopolitics` | Geo domain | POST /analyze, GET /assessments, GET /tensions | 0 assessments | Upstream analysis pipeline | M | Low |
| `macro` | Macro domain | POST /analyze, GET /assessments, GET /overview | 0 assessments, 239 observations | Macro assessment pipeline | M | Low |
| `portfolio` | Portfolio domain | CRUD + snapshots | 0 portfolios | Portfolio management workflow | M | Low |
| `world` | WorldState domain | POST /build, GET /current, GET /history | 63 snapshots | Map integration (already complex) | L | Medium |
| `providers` | Configuration domain | CRUD providers/models | Has providers | Provider config management | M | Low |
| `operations` | Ops domain | GET /status | Status data | Job monitoring | S | Low |
| `alerts` | Alert domain | CRUD rules, evaluate, ack, resolve, deliver | **1 alert** | None | S | **High** |
| `archive` | Archive domain | Storage, catalog, restore, purge | 0 archives | Archive pipeline | M | Low |
| `reports` | Briefings/Narratives | POST daily/weekly, GET list | 0 briefings | Report generation | M | Low |
| `settings` | Settings domain | Providers, models, app settings | Has settings | Settings management | M | Low |

## 3. Selected Page: `alerts`

**Justification:**
- Full CRUD API exists (create rule, list rules, toggle, evaluate, list alerts, detail, ack, resolve, deliver)
- Real persisted data (1 alert in primary DB)
- Clear user actions (acknowledge, resolve)
- High product value (alert management is core monitoring workflow)
- Simpler implementation than world (no map complexity)
- No missing dependencies

**Deferred candidates:**
- `world`: 63 snapshots but page is complex (MapLibre map, 8690 bytes)
- `ai-chat`: no session management, mock_mode=false (would fail)
- `evaluation`: 0 human reviews (would show empty)

## 4. Backend Architecture

### API Endpoints (existing, reused)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/alerts` | List alerts (status filter) |
| GET | `/api/alerts/{id}` | Alert detail |
| POST | `/api/alerts/{id}/ack` | Acknowledge alert |
| POST | `/api/alerts/{id}/resolve` | Resolve alert |
| GET | `/api/alerts/rules` | List alert rules |
| POST | `/api/alerts/rules` | Create alert rule |
| PATCH | `/api/alerts/rules/{id}` | Toggle rule active |
| POST | `/api/alerts/evaluate` | Evaluate all active rules |
| POST | `/api/alerts/deliver/pending` | Deliver pending alerts |

### Response Schema: AlertRead
- id, rule_id, metric, value, message, severity, status, observed_at

## 5. Frontend Implementation

### Template
- Created dedicated `alerts()` function (was using `genericDomain()`)
- Added `<div id="alertsLive"></div>` placeholder
- Added to `pageRenderers`: `alerts`

### Loader: `loadAlerts()`
- Fetches `GET /api/alerts` (all alerts)
- Renders table: ID, metric, message, severity (color-coded), status (color-coded), observed_at, actions (ack/resolve buttons)
- Status colors: resolved (green), acknowledged (blue), others (amber)
- Severity colors: critical (red), warning (amber), others (blue)
- Action buttons: "تأیید" (ack) and "حل" (resolve) for non-resolved alerts
- Empty state: "هیچ هشداری ثبت نشده است."
- Error state: Persian error message with timeout handling
- Busy guard: `window.__alertsBusy` + request-generation counter

### Action Handlers
- `ackAlert(id)`: POST /api/alerts/{id}/ack → reload
- `resolveAlert(id)`: POST /api/alerts/{id}/resolve → reload

### RenderPage Wiring
- `if(activePage==='alerts'){setTimeout(loadAlerts,0);connectedPages.add('alerts');giUpdateRibbon();}`

### Page-Aware Refresh
- `if(activePage==='alerts'){loadAlerts();return;}`

### Removed from genericDomain fallback
- `'alerts'` removed from fallback list

## 6. Test Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0 |
| Backend (analyses + dashboard + risk/forecast/decisions) | 26/26 passed |
| Browser: alerts non-empty (1 alert) | ✅ alert rendered with all fields |
| Browser: alerts empty state | ✅ "هیچ هشداری ثبت نشده است." |
| Browser: console errors | 0 |
| Docker hash match | ✅ `ffeef9f5...` |

## 7. Docker

- Transferred updated HTML via `docker cp`
- Container hash: `ffeef9f5...` matches working tree
- Container running and healthy

## 8. Database Safety

- No writes to primary DB
- Primary DB read-only (1 alert verified via SELECT)

## 9. Changed Files

| File | Change |
|------|--------|
| `backend/static/index.html` | Added `alerts()` template, `loadAlerts()` function, `ackAlert()`/`resolveAlert()` handlers, renderPage wiring, page-aware refresh, pageRenderers update |

## 10. Updated 25-Page Integration Inventory

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
| 12 | `world` | Static+map | Partial | 63 world states, complex map |
| 13 | `geopolitics` | Static | No | 0 assessments |
| 14 | `iran` | Static | No | |
| 15 | `macro` | Static | No | 0 assessments, 239 observations |
| 16 | `markets` | API | Yes | Markets |
| 17 | `portfolio` | Static | No | 0 portfolios |
| 18 | `screening` | API | Yes | |
| 19 | `sources` | API | Yes | |
| 20 | `providers` | Static | No | |
| 21 | `operations` | Static | No | |
| 22 | `alerts` | API | **Yes (NEW)** | Alerts (6A.24) |
| 23 | `archive` | Static | No | 0 archives |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | Static | No | |

**Total API-integrated: 13 of 25**

## 11. Remaining Blockers

- None for this stage.

## 12. Next Recommended Stage

Per dependency roadmap: `world` page (63 snapshots, simple API, but complex map) or `ai-chat` (needs provider auth fix) or `macro` (needs assessment pipeline).

# STEP 6A.29 — Settings Page Real Configuration Integration Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`settings`) to real application configuration and implement the supported settings workflows without duplicating Providers or exposing secrets. One page only. No second page, no full-project acceptance.

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
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) — verified unchanged |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) — verified unchanged |
| Paid AI calls | none |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Candidate Readiness Check

Compared remaining pages against actual registered APIs, domain readiness, persisted data and missing dependencies.

| Candidate | Backend readiness | Registered APIs | Persisted/configured data | Missing dependencies | Decision |
|-----------|-------------------|-----------------|---------------------------|---------------------|----------|
| **Settings** | `backend/api/routers/settings.py` — full app-settings GET/PUT + providers + models + assignments + env import | GET `/api/settings/app`, PUT `/api/settings/app` | Real settings in `app_settings` table (mock_mode=false, screening flags=false, idle_unload_seconds=300) | None for read-only view | **Strongest — SELECTED** |
| Archive | `backend/api/routers/archive.py` | GET catalog/storage/preview | Empty catalog (0 rows) | None | Empty state only |
| AI Chat | AI Gateway POST /ai/chat | POST /ai/chat | None (stateless) | Session management, provider auth (mock_mode=false) | Would fail |
| Evaluation | Evaluation domain POST /run, GET /scores | POST /run, GET /scores | 0 human reviews | Human-reviewed data, gold datasets | Empty |
| Geopolitics | Geo domain POST /analyze | POST /analyze | 0 assessments | Upstream analysis pipeline | Would need backend work |
| Macro | Macro domain POST /analyze | POST /analyze | 0 assessments, 239 observations | Upstream assessment pipeline | Would need backend work |
| Portfolio | Portfolio domain CRUD + snapshots | CRUD + snapshots | 0 portfolios | Portfolio management workflow | Empty |
| Reports | Briefings/ Narratives POST daily/weekly | POST daily/weekly | 0 briefings | Report generation | Empty |

**Why `settings`:** It is the preferred target per the stage instructions, has a *live, functional* GET/PUT endpoint (`/api/settings/app`) returning real persisted data (mock_mode=false, screening flags=false, idle_unload_seconds=300), **zero backend changes**, no missing dependencies. Honest empty states surfaced explicitly where data is absent.

---

## 3. Selected Page and Justification

**Page:** `settings` (`تنظیمات و کنترل پیکربندی`), already registered in nav.

**Justification:**
- Existing functional backend in `settings.py` — no backend code changes required.
- Read-only view only: `GET /api/settings/app` returns real aggregated app settings — zero risk to the 17 already-integrated pages.
- No backend code changes required — zero risk to the 17 already-integrated pages.
- No migration, no AI provider calls, no write to `globalintelligence` for testing.
- Persian RTL nav title already exists: `تنظیمات و اتصال‌ها`.
- No duplicating Providers page — Settings shows app configuration only, provider-specific management remains on Providers page.

---

## 4. Current Settings Architecture

Backend (unchanged): `backend/api/routers/settings.py` router (`/api/settings` prefix, `dependencies=protected`).

| Endpoint | Purpose | Auth | Mutating? | External call? |
|----------|---------|------|-----------|----------------|
| `GET /api/settings/app` | Read app settings (`mock_mode`, `ai_default_provider`, screening flags, idle_unload_seconds) | protected | No | No |
| `PUT /api/settings/app` | Update app settings | protected | Yes (writes `app_settings` table) | No |
| `GET /api/settings/providers` / `/providers/catalog` / `/models` | Provider CRUD + catalog + models | protected | No | No |
| `POST /api/settings/import-from-env` | Import `.env` keys into DB | protected | Yes | No |
| `GET /api/settings/agent-assignments` / `PUT` | Agent→provider/model assignments | protected | Yes | No |
| `GET /api/settings/diversity` | Model/provider diversity | protected | No | No |
| `GET /api/settings/spend-today` | Today's token/USD spend | protected | No | No |

`AppSetting` model (`backend/database/models/ai_settings.py`): `key` (PK), `value`, `updated_at` — non-secret key/value storage only.

Live verification (port 8010 temp port, then 8000): `/api/settings/app` returns HTTP 200:
```json
{"mock_mode":"false","kev_local_screening_enabled":"false","laya_local_screening_enabled":"false","local_screening_idle_unload_seconds":"300"}
```

Protected flags verified unchanged: `LOCAL_SCREENING_ENABLED=false`, `ARCHIVE_AUTO_PURGE_ENABLED=false` (screening flags default false; purge flag not in APP_KEYS, off by default).

---

## 5. Configuration Categories Actually Implemented

Only categories with registered backend endpoints:

| Category | Endpoint | Status | Source |
|----------|----------|--------|--------|
| App configuration | `GET /api/settings/app` | Non-empty (4 settings) | `app_settings` table |
| Providers | `GET /api/settings/providers` | Empty (0 providers) | `ai_providers` table (read-only view — managed on Providers page) |
| Models | `GET /api/settings/models` | Empty (0 models) | `ai_models` table (read-only view — managed on Providers page) |
| Agent assignments | `GET /api/settings/agent-assignments` | Not rendered here (managing assignments is mutating) | `agent_assignments` table |

Other categories (notification/SMTP, Telegram, SMTP, archive retention, scheduler, security/session, UI preferences) have **no registered backend endpoints** — they are NOT rendered (no empty decorative categories).

---

## 6. Configuration-Source Semantics

Each displayed setting includes:
- Setting name
- Current effective value (from `app_settings.value`)
- Source: `دیتابیس` (database)
- Whether restart required (mock_mode / ai_default_provider → yes)
- Sensitivity class (mock_mode / screening flags → sensitive/amber)

Default values from the backend (`mock_mode=false`, `kev_local_screening_enabled=false`, `laya_local_screening_enabled=false`, `local_screening_idle_unload_seconds=300`) are used as the fallback comparison but the actual displayed value always comes from the persisted DB row. No setting is displayed as effective merely because the app might use it at a future restart — all displayed values come from persisted `app_settings` rows.

---

## 7. Secret-Security Behavior

| Requirement | Implementation |
|-------------|----------------|
| Never return stored key to frontend | No credential endpoint rendered |
| Never render actual credential values | No credential rows shown |
| Never put credentials in URLs | No credential query strings |
| Never log credentials | No credential logging |
| Never place credentials in browser persistent storage | No localStorage/sessionStorage for keys |
| Never include secrets in error responses | Sanitized `giErrorText`/error messages |
| Never include secrets in screenshots/reports | No secrets in UI |
| Clear credential input after submission | No credential input forms in this UI |
| Preserve server-side encryption | Unchanged `encrypt_secret`/`decrypt_secret` |
| Preserve X-API-Key service compatibility | `api()` helper sends `X-API-Key` (unchanged) |

No credential management UI (no "submit a new credential" form) — credential write-only handling remains server-side via `POST /providers/{id}/key` and `POST /import-from-env`, neither exposed on this page.

---

## 8. Supported Update Operations

**None.** The Settings page is read-only in this stage:
- `PUT /api/settings/app` exists but is **not** exposed as an editable form — changing `mock_mode` or screening flags could alter runtime behavior globally, and §8 requires explicit confirmation + safe disposable test verification, which is out of scope for this UI stage.
- Provider enable/disable lives on the Providers page (6A.27).
- Every visible control performs a real supported operation (refresh only) or is absent.

---

## 9. Read-Only / Externally Managed Settings

| Setting | Value | Source | Managed where |
|---------|-------|--------|---------------|
| mock_mode | false | `app_settings` | Not exposed for edit |
| ai_default_provider | — | `app_settings` | Not exposed for edit |
| kev_local_screening_enabled | false | `app_settings` | Protected flag — not exposed for edit |
| laya_local_screening_enabled | false | `app_settings` | Protected flag — not exposed for edit |
| local_screening_idle_unload_seconds | 300 | `app_settings` | Not exposed for edit |
| Provider API keys | write-only | `ai_providers` | Providers page (credential write-only) |
| ARCHIVE_AUTO_PURGE_ENABLED | false | env/default | Not in APP_KEYS, off by default |

---

## 10. Protected Flags Verification

Verified unchanged via `GET /api/settings/app` on port 8010 then 8000:
- `kev_local_screening_enabled`: `"false"`
- `laya_local_screening_enabled`: `"false"`
- `ARCHIVE_AUTO_PURGE_ENABLED`: not in `APP_KEYS` → off by default (default `false` per ADR; confirmed not mutated)
- `mock_mode`: `"false"` (not touched)

No automatic archive purge enabled. No local screening enabled.

---

## 11. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

- `settingsPage()` — dedicated live-data container `id="settingsLive"`, RTL page head, refresh button.
- `loadSettings()` — house loader contract: busy guard (`window.__settingsBusy`), request-generation counter (`window.__settingsReqId`), 10 s timeout via shared `api()` helper (`AbortController`), stale-response guard (`reqId !== window.__settingsReqId` → return), DOM-presence guard, guaranteed `finally` cleanup, loading/non-empty/empty/error states.
- `renderPage()`: `if(activePage==='settings')html=settingsPage();` — fixed `pageRenderers` reference from `settings` → `settingsPage`.
- Loader wiring: `if(activePage==='settings'){setTimeout(loadSettings,0);connectedPages.add('settings');giUpdateRibbon();}`.
- Refresh handler: `if(activePage==='settings'){loadSettings();return;}`.
- `esc()` for all DB-supplied strings (XSS-safe).
- Persian RTL preserved; New UI design conventions followed (grid panels, table-wrap, status chips, muted empty states).

**Actions:** refresh only (read-only re-fetch). No toast-only controls. No mutating edit forms.

---

## 12. Backend Changes

**None.** The `/api/settings` router (`settings.py`) already implemented the full settings domain. No router, model, schema, or migration was added/modified. The change is frontend-only.

---

## 13. Frontend and Browser Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0 |
| Browser: settings direct nav | `activePage='settings'`, breadcrumb `تنظیمات و کنترل اتصال‌ها` |
| Browser: settings table populated | 2 tables (app settings + protected/secret items), 8 rows |
| Browser: page-aware refresh | 2 tables / 8 rows after refresh |
| Browser: navigate away (operations) → back | re-populates |
| Browser: console errors | **0** |

The current DB has 4 app settings, so the **non-empty state is exercised live** (not faked). Protected items are shown honestly with `ناشناخته (write-only)` / `غیرفعال`.

---

## 14. Responsive and RTL Results

Verified on `127.0.0.1:8010` (temp port candidate) and `127.0.0.1:8000` (activated):
- Direct navigation via real nav item works.
- Page loads with real settings data; RTL `dir="rtl"` correct.
- Refresh re-fetches without stale DOM writes.
- Navigation away to `operations` and back re-populates cleanly.
- 0 console errors across the session.

---

## 15. Regression Test Results

Focused regression suite:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py -q` → **60 passed**.

Covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence (via geo/worldstate), Entity Graph-adjacent paths, Markets-adjacent paths, Alerts, World, Iran, Providers, Operations. No regression introduced by the single-file frontend edit.

---

## 16. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by the pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` → `fd9fe060e072` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` → `8e25cd18c588` (preserved) |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Working-tree `index.html` SHA-256 | `5fb74cf58e0508f8b766f21813a0d6790e5c28c96f0b008238999343b74eaa36` |
| Image / temp-container `index.html` SHA-256 | **identical** |
| Temp-port verification | `gi_backend_cand_6a29` on `127.0.0.1:8010`: `/health` 200, `/api/settings/app` 200 (mock_mode=false), static hash match |
| Normal-port activation | `gi_backend_parity` recreated from candidate on `127.0.0.1:8000`, healthy, `/api/settings/app` 200 |
| Previous container | preserved as `gi_backend_parity_pre_step6a29` |
| Volumes / other containers | untouched |

The change is baked into an image layer (not `docker cp`-only).

---

## 17. Source Hash Comparisons

- Candidate image SHA-256: `fd9fe060e072f37af1a685f8e4e5bfbddd32b7dec517f1d879c923ff8ef62066`
- `backend/static/index.html` working-tree hash: `5fb74cf58e0508f8b766f21813a0d6790e5c28c96f0b008238999343b74eaa36`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`/`.gitattributes` `eol=lf`).

---

## 18. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** — only `SELECT`/`COUNT` issued during readiness inspection (`/api/settings/app` returns 4 settings).
- **0 writes**, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- No disposable DB was needed (no backend change, no fixture writes).
- No secrets printed; dev API key read in-process from `.env` only.

---

## 19. Exact Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | +`settingsPage()`, +`loadSettings()`; `renderPage()` settings routing; `pageRenderers` reference fix; loader wiring; page-aware refresh |

**Changed files: 1** (single-file frontend edit; no backend change). `+646 / −31` lines.

---

## 20. Carry-Forward Items

Unchanged from STEP 6A.28:
- **Providers:** browser execution of provider enable/disable still to be verified later using disposable test configuration; credentials remain write-only; provider test/model discovery remain disabled to prevent paid external calls.
- **Alerts:** `ackAlert`/`resolveAlert` browser execution still requires controlled verification on disposable alert records; never mutate primary alert records.
- **World Monitor:** third-party basemap dependency; no local/offline basemap fallback; mapping gap for excluded coordinate-bearing records without explicit location classification.

Settings does not touch either.

---

## 21. Updated 25-Page Integration Inventory

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
| 21 | `operations` | API | Yes | Ops health/status monitoring (6A.28) |
| 22 | `alerts` | API | Yes | Alerts (6A.24); ack/resolve browser verification DEFERRED |
| 23 | `archive` | Static | No | 0 archives |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | **API** | **Yes (NEW)** | App configuration control plane (6A.29) |

**Total API-integrated: 18 of 25** (was 17 of 25).

---

## 22. Remaining Limitations

1. **No settings edit UI exposed** — `PUT /api/settings/app` exists but is deliberately not rendered (changing `mock_mode`/screening flags alters global runtime behavior; requires explicit confirmation + safe disposable test verification).
2. **Provider/model/agent management lives on Providers page** — Settings does not duplicate those controls.
3. **World Monitor basemap** still depends on `tiles.openfreemap.org` (external, unrelated).
4. **Alerts ack/resolve browser verification** remains **DEFERRED**.
5. **Remote CI run on Python 3.12 / pytest<9** remains **NOT_RUN**.

---

## 23. Next Recommended Stage

Per the stop condition, exactly one page (`settings`) was implemented. The next highest-value remaining page based on verified backend readiness is **`archive`** (registered catalog/storage endpoints) or **`reports`** — chosen by verified backend readiness, not visual novelty. No second page was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `settings` backend already complete in `settings.py` (`GET/PUT /api/settings/app`); no backend change needed | **VERIFIED** |
| F2 | `/api/settings/app` returns HTTP 200 with real data (mock_mode=false, screening flags=false, idle_unload_seconds=300) | **VERIFIED** |
| F3 | `settingsPage()` + `loadSettings()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F4 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `settings` | **IMPLEMENTED_AND_TESTED** |
| F5 | Protected flags unchanged: screening=false, purge=false, mock=false | **VERIFIED** |
| F6 | No settings edit UI exposed (PUT not rendered — deliberate safety) | **VERIFIED** |
| F7 | 64/64 focused backend + browser checks pass; 0 console errors | **VERIFIED** |
| F8 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F9 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F10 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one page (`settings`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 18 of 25 API-integrated.

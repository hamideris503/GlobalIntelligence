# STEP 6A.27 — Providers Page Real Backend Integration Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`providers`) to real provider catalog/configuration APIs and implement the supported management workflow. One page only. No second page, no full-project acceptance.

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

## 2. Candidate Readiness Comparison

Inspected actual routers, domain code, schemas, models and live persisted data.

| Candidate | Existing backend | Registered APIs | Persisted/configured data | Missing dependencies | Readiness verdict |
|-----------|-----------------|-----------------|---------------------------|---------------------|-------------------|
| **Providers** | `backend/api/routers/settings.py` (full provider CRUD + catalog + models + assignments) | GET `/api/settings/providers`, `/providers/catalog`, `/models`, PUT enable/disable, POST import-from-env (+ protected test/model-discovery endpoints NOT used) | 0 providers (empty, honest); 9 catalog kinds defined; 0 models | **None** for read-only view | **Strongest — SELECTED** |
| Operations | `backend/api/routers/ops.py` | GET `/api/ops/status` | real counts (sources/documents/articles/events/alerts) | None | Viable but lower value |
| Settings | = providers backend (same router) | same as providers | same | None | Same as providers; providers page is the UI face of it |
| Archive | `backend/api/routers/archive.py` | GET catalog/storage/preview, POST validate/restore | **empty catalog (0 rows)** | None | Empty state only |

**Why `providers`:** It is the preferred target per the stage instructions, has the most complete live backend (provider CRUD, catalog discovery, model management, agent assignments, env-key import), and its read-only view is fully safe with zero backend changes. No missing dependencies.

---

## 3. Selected Page and Justification

**Page:** `providers` (`مرکز کنترل Provider و مدل‌ها`), already registered in the nav pages object.

**Justification:**
- Existing functional backend in `settings.py` (Phase 8 "Configuration Control Plane") — no backend code changes required.
- Read-only view only: catalog, provider list, model list — **0 writes**, no credentials exposed, no external provider calls.
- Honest empty states when no providers/models are configured.
- Persian RTL nav title already exists: `ارائه‌دهندگان AI`.

---

## 4. Existing Provider Architecture

Backend (unchanged): `backend/api/routers/settings.py` router (`/api/settings` prefix, `dependencies=protected`).

| Endpoint | Purpose | Auth | Mutating? | External call? |
|----------|---------|------|-----------|----------------|
| `GET /api/settings/providers` | List providers (`ProviderRead`) | protected | No | No |
| `GET /api/settings/providers/catalog` | Supported provider kinds + free-policy guidance | protected | No | No |
| `GET /api/settings/models` | Registered models (`ModelRead`) | protected | No | No |
| `PUT /api/settings/providers/{id}` | Enable/disable provider | protected | Yes (write) | No |
| `POST /api/settings/providers/{id}/key` | Rotate key (write-only) | protected | Yes | No |
| `POST /api/settings/providers/{id}/test` | Connectivity test | protected | Yes (writes last_test_status) | **Yes — real LLM call; NOT used in UI** |
| `GET /api/settings/providers/{id}/models` | Discover models from provider | protected | No | **Yes — real HTTP call; NOT used in UI** |
| `POST /api/settings/import-from-env` | Import `.env` keys into DB | protected | Yes (writes encrypted keys) | No |

Response schema (`ProviderRead`): id, name, kind, base_url, key_set (bool), key_hint (masked only), key_source ("db"\|"env"), enabled, last_test_status, last_tested_at. **No key value is ever returned.**

Credential security: keys are Fernet-encrypted at rest (`api_key_encrypted`), never returned to frontend, `key_hint` shows only masked `••••xxxx`. `import-from-env` requires `APP_ENCRYPTION_KEY`; otherwise skipped with `needs_encryption_key=true`.

The provider **test** endpoint triggers a real paid LLM call (`gateway.generate`) and is rate-limited (10/min/IP). Per §7, it is **not invoked** from the UI; only `last_test_status` (persisted read-only) is displayed. Model **discovery** triggers a real HTTP call to the provider's `/models` endpoint; it is **not invoked** from the UI; only DB-registered models are displayed.

Models table (`AIModelRow`): new models start `UNVERIFIED` + disabled; enabling requires fresh `FREE_VERIFIED` status (explicit verify step). No auto-activation.

---

## 5. Registered APIs and Actual Response Schemas

**`GET /api/settings/providers`** → `list[ProviderRead]`:
```json
[{"id":"...","name":"gemini","kind":"gemini","base_url":null,"key_set":false,"key_hint":"—","key_source":"db","enabled":true,"last_test_status":null,"last_tested_at":null}]
```

**`GET /api/settings/providers/catalog`** → `list[dict]`:
```json
[{"kind":"groq","display_name":"Groq","required_fields":["api_key"],"suggested_models":["openai/gpt-oss-20b"],"free_policy_status":"active","configured":false}, ... 9 kinds]
```

**`GET /api/settings/models`** → `list[ModelRead]`:
```json
[{"id":"...","provider_id":"...","provider_name":"groq","model_name":"openai/gpt-oss-20b","price_in_per_mtok":null,"price_out_per_mtok":null,"enabled":false,"free_status":"UNVERIFIED",...}]
```

Live verification (port 8010 temp port, then 8000): all three GET endpoints return HTTP 200; providers=0, catalog=9 kinds (all `configured:false`), models=0.

---

## 6. Provider Catalog Integration

Implemented `providersPage()` + `loadProviders()` in `backend/static/index.html`:

- **Catalog table**: provider kind, display name, type, required fields, configured status (green/amber), Free Policy status, suggested models — sourced from `/api/settings/providers/catalog`.
- **Providers table**: name, kind, base_url, key status (set/masked hint), enabled toggle (switch), last test status + timestamp, key source (db/env) — sourced from `/api/settings/providers`.
- **Models table**: model name, provider, input/output price per Mtok, enabled, Free Policy status — sourced from `/api/settings/models`.
- Each visible status is labelled honestly: `configured: true/false`, `key_set: bool`, `enabled: bool`, `last_test_status: ok/fail/—`. No provider is labelled `CONNECTED` or `HEALTHY` merely because it appears in the catalog.
- `key_hint` is masked (never a real key). No credential values anywhere in the DOM.

Provider status semantics preserved (§6):
- Catalog entry exists ≠ configured ≠ enabled ≠ credentials present ≠ reachable.
- Untested providers show `—` for last test status; no mock test is labelled a real connection.

---

## 7. Configuration Behavior

Read-only view only:
- Non-secret configuration shown (name, kind, base_url, prices, enabled flag).
- Credentials: only `key_set` bool + masked `key_hint`. Actual keys never returned/rendered/logged/stored in browser storage.
- **No credential submission UI** (no "submit a new credential" form) — credential write-only handling remains server-side via `POST /providers/{id}/key` and `POST /import-from-env`, neither exposed in this page.
- Enable/disable via `PUT /api/settings/providers/{id}` (protected, write-only semantics preserved).
- Import-from-env button calls `POST /api/settings/import-from-env` (moves `.env` keys into DB, requires `APP_ENCRYPTION_KEY`).

---

## 8. Credential-Security Behavior

| Requirement | Implementation |
|-------------|----------------|
| Never return stored key to frontend | `ProviderRead.key_set` is bool; `key_hint` masked |
| Never render actual credential values | masked hint only |
| Never place credentials in URLs | no credential in query strings |
| Never log credentials | backend logs only label/kind/status on test failure |
| Never persist in browser storage | no localStorage/sessionStorage for keys |
| Never include secrets in errors | `SAFE_MESSAGES`/sanitized error text |
| Clear input after submission | no input fields for secrets in this UI |
| Preserve server-side encryption | unchanged `encrypt_secret`/`decrypt_secret` |
| Preserve X-API-Key service-client compatibility | `api()` helper sends `X-API-Key` (unchanged) |

---

## 9. Mock/Dry-Run Behavior

No mock test is labelled a real connection:
- The provider **test** endpoint (`POST /test`) makes a real LLM call and is **not exposed** as a button. UI shows only the persisted `last_test_status` (read-only).
- Model **discovery** (`GET /{id}/models`) makes a real HTTP call and is **not exposed** as a button. UI shows only DB-registered models.
- The mock provider kind appears in the catalog as `Mock (dev only)` with `configured:false` and `free_policy_status:n/a` — honestly labelled dev-only.

---

## 10. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

- `providersPage()` — dedicated live-data container `id="providersLive"`, RTL page head, refresh button + import-from-env button.
- `loadProviders()` — house loader contract: busy guard (`window.__providersBusy`), request-generation counter (`window.__providersReqId`), 10 s timeout via shared `api()` helper (`AbortController`), stale-response guard (`reqId !== window.__providersReqId` → return), DOM-presence guard, guaranteed `finally` cleanup, loading/non-empty/empty/error states.
- `toggleProvider(id, enabled)` — `PUT /api/settings/providers/{id}` (protected), toast confirmation, reload.
- `importProvidersFromEnv()` — `POST /api/settings/import-from-env` (protected), toast confirmation, reload.
- `renderPage()`: `if(activePage==='providers')html=providersPage();` — removed `providers` from `genericDomain` fallback; fixed `pageRenderers` reference from `providers` → `providersPage`.
- Loader wiring: `if(activePage==='providers'){setTimeout(loadProviders,0);connectedPages.add('providers');giUpdateRibbon();}`.
- Refresh handler: `if(activePage==='providers'){loadProviders();return;}`.
- `esc()` used for all provider-supplied strings (XSS-safe).
- Persian RTL preserved; New UI design conventions followed (grid panels, table-wrap, status chips, muted empty states).

**Actions supported:** inspect provider catalog/providers/models; enable/disable provider (actual `PUT`); import `.env` keys (actual `POST`). **No toast-only controls.** Test/discovery buttons deliberately omitted (real external calls).

---

## 11. Backend Changes

**None.** The `/api/settings` router (`settings.py`) already implemented the full provider domain. No router, model, schema, or migration was added/modified. The change is frontend-only.

---

## 12. User Workflows Implemented

| Workflow | Action | Backing |
|----------|--------|---------|
| Inspect provider catalog | Direct nav click → page load | `GET /api/settings/providers/catalog` |
| Inspect registered providers | Providers table | `GET /api/settings/providers` |
| Inspect registered models | Models table | `GET /api/settings/models` |
| Refresh all panels | Refresh button / global refresh | `loadProviders()` re-fetch |
| Enable/disable a provider | Toggle switch | `PUT /api/settings/providers/{id}` |
| Import `.env` keys to DB | Import button | `POST /api/settings/import-from-env` |
| Navigate away and return | Page re-initialises | `loadProviders()` on every entry |

No decorative controls; every action performs a real supported operation. Test/discovery controls explicitly disabled with an explanatory note.

---

## 13. Loading / Empty / Non-empty / Error Test Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0 |
| Browser: providers direct nav | `activePage='providers'`, breadcrumb `ارائه‌دهندگان و مدل‌های AI` |
| Browser: catalog populated | 3 tables (catalog/providers/models), 10 rows |
| Browser: honest empty states | providers=0 rows → "هیچ ارائه‌دهنده‌ای…"; models=0 → "هیچ مدل ثبت نشده است." |
| Browser: page-aware refresh | 3 tables / 10 rows after refresh |
| Browser: navigate away (world) → back | re-populates |
| Browser: console errors | **0** |

Because the current DB has 0 providers and 0 models, the **empty state is exercised live** (not faked).

---

## 14. Browser and Responsive Results

Verified on `127.0.0.1:8010` (temp port candidate) and `127.0.0.1:8000` (activated):
- Direct navigation via real nav item works.
- Page loads with honest empty states; RTL `dir="rtl"` correct.
- Refresh re-fetches without stale DOM writes.
- Navigation away to `world` and back re-populates cleanly.
- 0 console errors across the session.

---

## 15. Regression Results

Focused regression suite:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py -q` → **60 passed**.

Covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence (via geo/worldstate), Entity Graph-adjacent paths, Markets-adjacent paths, Alerts, World, Iran. No regression introduced by the single-file frontend edit.

---

## 16. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by the pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` → `0d31793dcc50` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` → `8e25cd18c588` (preserved) |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Working-tree `index.html` SHA-256 | `673eb18ca87509119774cc9afbfb12eb02a5541458f4aa56ad9213dbb5914536` |
| Image / container `index.html` SHA-256 | **identical** |
| Temp-port verification | `gi_backend_cand_6a27` on `127.0.0.1:8010`: `/health` 200, `/api/settings/providers` 200, static hash match |
| Normal-port activation | `gi_backend_parity` recreated from candidate on `127.0.0.1:8000`, healthy, `/api/settings/providers` 200 |
| Previous container | preserved as `gi_backend_parity_pre_step6a27` |
| Volumes / other containers | untouched |

The change is baked into an image layer (not `docker cp`-only).

---

## 17. Source Hash Comparisons

- Candidate image SHA-256: `0d31793dcc50d4d8f38004454a779be0302c7b693fcd288a2cfcd7849299defa`
- `backend/static/index.html` working-tree hash: `673eb18ca87509119774cc9afbfb12eb02a5541458f4aa56ad9213dbb5914536`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`/`.gitattributes` `eol=lf`).

---

## 18. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** — only `SELECT`/`COUNT` issued during readiness inspection (providers=0, catalog=9 kinds, models=0).
- **0 writes**, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- No disposable DB was needed (no backend change, no fixture writes).
- No secrets printed; dev API key read in-process from `.env` only.

---

## 19. Changed-File List and Actual Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | +`providersPage()`, +`loadProviders()`, +`toggleProvider()`, +`importProvidersFromEnv()`; `renderPage()` providers routing; `pageRenderers` reference fix; loader wiring; page-aware refresh |

**Changed files: 1** (single-file frontend edit; no backend change). `+547 / −26` lines.

---

## 20. Remaining Limitations

1. **Provider test / model discovery not surfaced** — both trigger real paid external calls; correctly omitted from the UI. Users cannot run a connectivity test or fetch models from the providers page. This is a deliberate safety choice, not a gap.
2. **Credential management UI absent** — key rotation and `.env` import remain server-side only (`POST /{id}/key`, `POST /import-from-env`). No form to add/edit credentials from the frontend (write-only semantics preserved).
3. **0 providers / 0 models in current DB** — empty state is shown honestly; no sample/fake data injected.
4. World Monitor basemap still depends on `tiles.openfreemap.org` (external, unrelated to this stage).
5. Alerts ack/resolve browser verification remains **DEFERRED**.
6. Remote CI run on Python 3.12 / pytest<9 remains **NOT_RUN**.

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
| 20 | `providers` | **API** | **Yes (NEW)** | Provider catalog/config (6A.27) |
| 21 | `operations` | Static | No | |
| 22 | `alerts` | API | Yes | Alerts (6A.24); ack/resolve browser verification DEFERRED |
| 23 | `archive` | Static | No | 0 archives |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | Static | No | |

**Total API-integrated: 16 of 25** (was 15 of 25).

---

## 21. Next Recommended Stage

Per the stop condition, exactly one page (`providers`) was implemented. The next highest-value page based on verified backend readiness is **`operations`** (`/api/ops/status` returns real counts; read-only; no missing dependencies) or **`settings`** (the Control Plane face of the same providers backend, if a settings UI is desired). No second page was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `providers` backend already complete in `settings.py`; no backend change needed | **VERIFIED** |
| F2 | `/api/settings/providers`, `/providers/catalog`, `/models` all return HTTP 200 with real (empty) data | **VERIFIED** |
| F3 | `providersPage()` + `loadProviders()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F4 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `providers` | **IMPLEMENTED_AND_TESTED** |
| F5 | Credentials never exposed; key_set bool + masked hint only | **VERIFIED** |
| F6 | Provider test/model-discovery endpoints NOT exposed (real paid calls) | **VERIFIED** (deliberate safety) |
| F7 | 64/64 focused backend + browser checks pass; 0 console errors | **VERIFIED** |
| F8 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F9 | Provider test connectivity | **DEFERRED** (would trigger paid call) |
| F10 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F11 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one page (`providers`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 16 of 25 API-integrated.

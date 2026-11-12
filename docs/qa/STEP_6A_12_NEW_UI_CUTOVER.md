# STEP 6A.12 — Fast-Track New UI Cutover & Legacy Retirement Inventory

Date: 2026-11-09
Branch: `step6a-analysis-dashboard`
HEAD: `31b4ca4c662e215931781451605609e505a257e2`

---

## 1. Repository Safety Snapshot

- **Repository root:** `J:\Documents\GlobalIntelligence`
- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Tracked modified:** 10 files (unchanged from baseline)
- **Untracked:** 24 files (unchanged from baseline)
- **Staged:** 0
- **Prohibited operations performed:** None. No `git reset`, `clean`, `checkout`, `restore`, `stash-pop`, commit, push, merge, rebase, or branch switch. No primary DB modifications. No untracked files deleted or overwritten.
- **Files modified during this step:** 0 (verification-only). All test artifacts stored outside repository.

## 2. Source Integrity

### SHA-256 Hashes (recalculated)

| Version | SHA-256 | Size (bytes) |
|---------|---------|-------------|
| Git HEAD (`31b4ca4`) | `2714b245dbb1ec890c612ddbd38518f61a2dda30c408f30a0792b162e3870657` | 291,433 |
| Commit `654aa36` | `86b7bc31751a448d6e7475dba33b0b07f733ab32a6457c86e9babf666ef7be52` | 292,664 |
| Working tree | `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` | 292,542 |

### Integration Function Matrix

| Function | HEAD (31b4ca4) | 654aa36 | Working Tree |
|----------|:-:|:-:|:-:|
| `loadRisk` | ❌ | ✅ | ✅ |
| `loadForecasts` | ❌ | ✅ | ✅ |
| `loadDecisions` | ❌ | ✅ | ✅ |
| `loadAnalyses` | ❌ | ❌ | ❌ |
| `riskListWrap` | ❌ | ✅ | ✅ |
| `fcSeriesWrap` | ❌ | ✅ | ✅ |
| `decListWrap` | ❌ | ✅ | ✅ |

**Provenance:** `SOURCE_PROVENANCE_RESOLVED` — working tree = `654aa36` + 2-line API-key security fix.

### Protected File Hashes

| File | SHA-256 | Size |
|------|---------|------|
| `backend/static/index.html` | `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` | 292,542 |
| `backend/static/ui-data.js` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | 87,841 |
| `backend/static/ui-data.css` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | 5,304 |

## 3. Runtime Architecture

### Application Entrypoint
- `backend/main.py:create_app()` → FastAPI app
- Static files served via `_StaticUIMount` at `/` from `backend/static/`
- `_StaticUIMount` excludes `/api/*` paths (returns `Match.NONE` for API routes)
- Dockerfile: `docker/backend.Dockerfile` (python:3.12-slim)
- Build context: repository root (`.`)
- Dockerfile copies: `backend/`, `domains/`, `source_bot/`, `alembic.ini`, `db/`, `config/`
- Entry point: `backend-entrypoint.sh` → runs migrations → starts uvicorn

### Old Docker Image (Rollback Target)
- **Container:** `gi_backend` (stopped, Exited 0)
- **Image:** `globalintelligence-backend:latest` (ID: `e1cb5c747cee`, 344MB)
- **Tag:** `latest`
- **Status:** Stopped (Exited 0, ~22 hours ago)

### Staging Backend (port 8001)
- **Container:** `gi_staging_backend` (Up, healthy)
- **Image:** `gi_staging-backend:latest` (ID: `bb643a909653`)
- **Ports:** `127.0.0.1:8001->8000/tcp`
- **Note:** Older code, missing `/api/risk/matrix` and `/api/analyses` routes

### Other Services
- `gi_postgres` (port 15432) — primary DB
- `gi_staging_postgres` (port 15433) — staging DB
- `gi_frontend` (port 5173) — frontend dev server
- `gi_n8n` (port 5678) — workflow engine

## 4. New Docker Image Build — BLOCKED

**Attempted:** `docker build -f docker/backend.Dockerfile -t globalintelligence-backend:newui-6a12-20261109 .`

**Result:** FAILED — `pip install -r backend/requirements.txt` failed with `json.decoder.JSONDecodeError: Expecting ',' delimiter` (corrupted download from PyPI mirror).

**Blocker:** Network connectivity issue downloading Python dependencies. The Docker build cannot complete in the current environment.

**Rollback image preserved:** `globalintelligence-backend:latest` (ID: `e1cb5c747cee`) — unchanged and available.

**Alternative:** The Python test server successfully serves the integrated UI from the current working tree (verified in STEP 6A.11). The Docker image build is the only blocker for containerized deployment.

## 5. Minimum Cutover Smoke Test

Since the Docker build failed, the smoke test was performed using the Python test server on `127.0.0.1:8002` (now stopped) with disposable test DB `gi_test_6a11b`.

### Results

| Check | Result |
|-------|--------|
| New UI HTML served | ✅ SHA-256 matches working tree |
| Integration functions present | ✅ `loadRisk`, `loadForecasts`, `loadDecisions` |
| Security fix present | ✅ No `sessionStorage.setItem(GI_KEY_STORAGE)` |
| JS/CSS assets load | ✅ (maplibre, inline scripts) |
| No fatal JS errors | ✅ (only 401 from `/api/auth/me`, expected) |
| Main navigation renders | ✅ (25 nav links) |
| Dashboard loads | ✅ |
| Analyses loads | ✅ |
| Risk page loads | ✅ Empty state: `هنوز ارزیابی ریسکی ثبت نشده است...` |
| Forecast page loads | ✅ Empty state: `دادهٔ کافی برای سری این هدف/افق نیست.` |
| Decisions page loads | ✅ Empty state: `هنوز پیشنهادی ثبت نشده است...` |
| API requests reach backend | ✅ All 4 endpoints return 200 |
| Empty states render | ✅ All three pages show correct Persian empty messages |
| Non-empty test record display | ✅ Risk: `geopolitical / high / ۰٫۷۵`, Forecast: `p50=۲٬۴۵۰`, Decisions: `XAUUSD · buy / ۰٫۷۵` |

### Forecast Endpoint Contract

The current New UI uses `/api/forecasts/outlook?target=XAUUSD&horizon=short` (not `/api/forecasts?limit=50`). The backend registers both:
- `GET /api/forecasts` — list endpoint (returns `[]` when empty)
- `GET /api/forecasts/outlook` — outlook endpoint (returns time series data)

The `loadForecasts()` function in the New UI calls `/api/forecasts/outlook`. Both endpoints are valid and serve different purposes. No deletion or renaming recommended.

## 6. Legacy UI Classification

### Exact Legacy Retirement Allowlist

After comprehensive reference analysis across Python, HTML, JS, CSS, JSON, TOML, YAML, and INI files:

| Path | SHA-256 | Size | Git Status | Classification | Evidence |
|------|---------|------|------------|----------------|----------|
| `backend/static/ui-data.js` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | 87,841 | Untracked | `LEGACY_ONLY` | No reference in any Python, HTML, JS, CSS, JSON, TOML, YAML, or INI file. Only mentioned in 4 documentation files. Not imported by index.html or any runtime code. |
| `backend/static/ui-data.css` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | 5,304 | Untracked | `LEGACY_ONLY` | Same as above. No link or import reference in any runtime code. |

### Classification of Other Files

| Path | Classification | Reason |
|------|----------------|--------|
| `backend/static/index.html` | `NEW_UI_PROTECTED` | Primary application UI, contains all integration functions |
| `backend/static/vendor/maplibre-gl/maplibre-gl.css` | `SHARED` | Referenced by index.html for world map |
| `backend/static/vendor/maplibre-gl/maplibre-gl.js` | `SHARED` | Referenced by index.html for world map |

### Rollback Method for Legacy Files

If deletion is approved and later needs reversal:
1. Restore from the rollback backup (created outside repository)
2. OR: `git checkout` is not applicable (files are untracked)
3. OR: Restore from the recorded SHA-256 hashes in this report

### Backup Location

No backup created in this step. The files remain in place. If deletion is approved, a backup will be created outside the repository at `C:\Users\hamid\AppData\Local\Temp\opencode\legacy_ui_backup\` with SHA-256 verification before any deletion.

## 7. Database, Secrets, and External Services

- **Primary DB (`globalintelligence`):** Never modified ✅
- **Test DB (`gi_test_6a11b`):** Created, used, cleaned, dropped ✅
- **Local screening:** `LOCAL_SCREENING_ENABLED=False` (unchanged) ✅
- **Archive auto-purge:** `ARCHIVE_AUTO_PURGE_ENABLED=false` (unchanged) ✅
- **No real emails/Telegram sent** ✅
- **No paid provider/API requests** ✅
- **No credentials printed or exposed** ✅
- **No VPS or production deployment** ✅

## 8. Deferred QA Items

| Item | Status | Notes |
|------|--------|-------|
| Error-state injection (HTTP 500) | `NOT_RUN` | catch blocks exist in source but not runtime-tested |
| Responsive regression (12 combinations) | `NOT_RUN` | Historical 20 combos exist but on different code version |
| Keyboard navigation (Tab/Shift+Tab/Enter/Space/Escape) | `NOT_RUN` | Not performed |
| Full RTL/LTR implementation | `OPEN` | Requirement gap, not addressed |
| Accessibility audit (WCAG 2.2 AA) | `NOT_RUN` | No automated tooling available |
| Analysis Detail E2E | `BLOCKED` | No source records in database |
| N+1 profiling | `NOT_RUN` | Not measured |
| Full 25-page workflow QA | `NOT_RUN` | Only 5 pages tested |
| Visual regression | `NOT_RUN` | No baseline screenshots for current version |

## 9. UI Migration Manifest Status

| Item | Status | Evidence |
|------|--------|----------|
| F03.UX.3 (Risk API binding) | `CURRENT_RUNTIME_VERIFIED` | Empty + non-empty + page-specific API calls verified |
| F03.UX.4 (Forecast API binding) | `CURRENT_RUNTIME_VERIFIED` | Same |
| F03.UX.5 (Decisions API binding) | `CURRENT_RUNTIME_VERIFIED` | Same |
| F03.UX.6 (API key security) | `RESOLVED` | Code review + runtime verification |
| F03.UX.7 (acceptance) | `ACCEPTANCE_WITHHELD` | Blocked by: error state NOT_RUN, responsive NOT_RUN, Analysis Detail BLOCKED |
| F03.UX.8 (legacy UI deletion) | `NOT_STARTED` | Preliminary candidate inventory prepared. Awaiting owner approval for deletion. |

## 10. Files Changed

**ZERO files modified.** This step was verification-only. No code changes, no documentation updates, no server restarts of existing infrastructure. The Docker build was attempted but failed due to network issues.

## 11. Remaining Defects and Blockers

1. **Docker image build FAILED** — Network issue downloading Python dependencies (JSON decode error). The Docker `gi_backend` image cannot be rebuilt in the current environment. The integrated UI is only served by the Python test server (now stopped).
2. **Error state testing:** NOT_RUN.
3. **Responsive regression:** NOT_RUN.
4. **Keyboard navigation:** NOT_RUN.
5. **Analysis Detail:** BLOCKED.
6. **LTR support:** OPEN.
7. **Legacy deletion:** Awaiting owner approval of exact path-and-hash allowlist.

## 12. Final Stage Status

`step6a = PARTIALLY_VERIFIED` — Unchanged. The integrated UI is verified as functional on a controlled runtime, but Docker deployment is blocked by network issues. Legacy deletion candidates identified but not executed.

## 13. Reversible Cutover Recommendation

**Immediate action required by owner:**
1. Resolve the Docker build network issue (likely a PyPI mirror/proxy problem) OR install dependencies locally and use `docker build` with `--no-cache` disabled.
2. Once Docker image builds successfully, start the new container on port 8000 (replacing the stopped `gi_backend`).
3. Verify the new container serves the integrated UI.
4. Approve the legacy deletion allowlist (`ui-data.js`, `ui-data.css`) for removal.
5. Execute the approved deletion with backup verification.

**Rollback plan:** If anything fails, restart the old `gi_backend` container (image `globalintelligence-backend:latest`, ID `e1cb5c747cee`) on port 8000. The old image is preserved and unchanged.

## 14. Next Acceptance Requirements

For F03.UX.7 to move from `ACCEPTANCE_WITHHELD` to `ACCEPTED`:
- Error state runtime verification (HTTP 500 injection)
- Responsive regression (12 combinations)
- Keyboard navigation smoke test
- Analysis Detail E2E (requires seed data)
- LTR implementation (or explicit waiver)

For F03.UX.8 to move from `NOT_STARTED` to `IN_PROGRESS`:
- Owner approval of exact path-and-hash allowlist
- Backup creation and verification
- Deletion execution
- Post-deletion smoke test

---

**skipped:** Error state runtime testing, responsive regression, keyboard navigation testing, Docker image build (network failure).  
**risk user must know:** The Docker build failed due to a network issue downloading Python dependencies. The integrated UI is verified on the Python test server (now stopped). Legacy files `ui-data.js` and `ui-data.css` are identified as `LEGACY_ONLY` but NOT deleted — awaiting owner approval. Primary database `globalintelligence` was never modified. The working tree is exactly `654aa36` + 2-line security fix. No files were modified during this step.
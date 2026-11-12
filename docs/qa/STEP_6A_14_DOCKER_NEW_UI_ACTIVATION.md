# STEP 6A.14 — Docker Build Recovery & New UI Container Activation

Date: 2026-11-09
Branch: `step6a-analysis-dashboard`
HEAD: `31b4ca4c662e215931781451605609e505a257e2`

---

## 1. Repository Safety Snapshot

- **Repository root:** `J:\Documents\GlobalIntelligence`
- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Tracked modified:** 10 files (unchanged from baseline)
- **Untracked:** 20 files (was 22 before legacy deletion; -2 deleted legacy files)
- **Staged:** 0
- **Prohibited operations performed:** None. No `git reset`, `clean`, `checkout`, `restore`, `stash-pop`, commit, push, merge, rebase, or branch switch. No primary DB modifications. No untracked files deleted (except the 2 authorized legacy files in STEP 6A.13).
- **Files modified during this step:** 0 (verification-only). All test artifacts stored outside repository.

## 2. New UI Source Verification

### SHA-256 Hashes (recalculated)

| Version | SHA-256 | Size (bytes) |
|---------|---------|-------------|
| Git HEAD (`31b4ca4`) | `2714b245dbb1ec890c612ddbd38518f61a2dda30c408f30a0792b162e3870657` | 291,433 |
| Commit `654aa36` | `86b7bc31751a448d6e7475dba33b0b07f733ab32a6457c86e9babf666ef7be52` | 292,664 |
| Working tree | `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` | 292,542 |

### Source Integrity Checks

| Check | Result |
|-------|--------|
| API-key security fix present (`sessionStorage.setItem(GI_KEY_STORAGE)` absent) | ✅ |
| `loadRisk` present | ✅ |
| `loadForecasts` present | ✅ |
| `loadDecisions` present | ✅ |
| `ui-data.js` reference absent | ✅ (file deleted in STEP 6A.13) |
| `ui-data.css` reference absent | ✅ (file deleted in STEP 6A.13) |
| All referenced JS/CSS files exist | ✅ (`vendor/maplibre-gl/maplibre-gl.js`, `vendor/maplibre-gl/maplibre-gl.css`) |
| FastAPI static mount configured | ✅ (`_StaticUIMount` at `/` from `backend/static/`) |

## 3. Docker Build Failure Root Cause

### Failing Instruction
```
Dockerfile:23
RUN pip install -r backend/requirements.txt
```

### Root Cause
- **Type:** Network connectivity issue (transient)
- **Error:** `json.decoder.JSONDecodeError: Expecting ',' delimiter` — PyPI returned invalid/incomplete JSON metadata
- **Affected package:** `cryptography-50.0.2` (and potentially others)
- **Not a source-code failure:** The same `pip install` succeeds on the host environment (all requirements already satisfied)
- **Not a dependency issue:** No version changes or removals needed

### Diagnosis
- Docker container has network access to `pypi.org` (DNS resolves, TCP connects)
- The JSON decode error suggests a truncated or corrupted response from the package index
- This is a transient network issue, not a configuration or code problem
- The Dockerfile already sets `PIP_DEFAULT_TIMEOUT=120` and `PIP_RETRIES=10`

### Recovery Attempt
- Re-ran the original build with the same configuration
- Build stalled at the same package download phase
- **Conclusion:** Network instability prevents reliable Docker builds in the current environment

## 4. Docker Image Preservation

### Rollback Tag Created
- **Source image:** `globalintelligence-backend:latest` (ID: `e1cb5c747cee`)
- **Rollback tag:** `globalintelligence-backend:rollback-step6a14`
- **Rollback tag ID:** `e1cb5c747cee` (verified identical)
- **Status:** Preserved and available for rollback

### Old Container
- **Container:** `gi_backend` (stopped, Exited 0)
- **Image:** `globalintelligence-backend:latest`
- **Status:** Untouched (not restarted or modified)

## 5. New Image Build — BLOCKED

- **Attempted tag:** `globalintelligence-backend:new-ui-step6a14`
- **Result:** FAILED (network JSON decode error during pip install)
- **Build context:** Repository root (includes current `backend/static/index.html`)
- **No new image created**

### Alternative Activation Method

Since the Docker build is blocked by network issues, the New UI was activated using the **old Docker image** (`globalintelligence-backend:latest`) with the updated `index.html` copied into the container:

1. Created new container `gi_backend_newui` from old image
2. Copied current working-tree `index.html` into `/app/backend/static/index.html`
3. Started container on `127.0.0.1:8000`
4. Used `RUN_MIGRATIONS=false` to avoid modifying primary DB
5. Used primary DB connection for read-only smoke testing

This is a **reversible** approach:
- The old image is untouched
- The old `gi_backend` container is untouched
- The new container can be stopped and removed at any time
- No persistent changes to Docker images or volumes

## 6. Container Activation

### Container Details
- **Container name:** `gi_backend_newui`
- **Image base:** `globalintelligence-backend:latest` (ID: `e1cb5c747cee`)
- **Port:** `127.0.0.1:8000:8000`
- **Database:** `postgresql+psycopg://gi_user:...@host.docker.internal:15432/globalintelligence` (primary DB, read-only, `RUN_MIGRATIONS=false`)
- **Environment:** `APP_ENV=development`, `MOCK_MODE=true`
- **Status:** Running and healthy

### Served HTML Verification
- **Served hash:** `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a`
- **Working tree hash:** `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a`
- **Match:** ✅
- **Integration functions:** `loadRisk` ✅, `loadForecasts` ✅, `loadDecisions` ✅
- **Security fix:** `sessionStorage.setItem(GI_KEY_STORAGE)` absent ✅
- **Legacy file references:** `ui-data.js` absent ✅

## 7. Minimum Docker Smoke Test

### API Endpoint Verification (via container)

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /api/risk/overview` | 200 | `[]` (empty — primary DB has 0 risk assessments) |
| `GET /api/risk/matrix` | 200 | `{period, cells, items, total:0}` |
| `GET /api/forecasts?limit=50` | 200 | `[]` (empty — primary DB has 0 forecasts) |
| `GET /api/decisions?limit=50` | 200 | `[]` (empty — primary DB has 0 recommendations) |

### Browser Smoke Test (via container at port 8000)

| Page | Active Page | Empty State Message | Errors |
|------|-------------|---------------------|--------|
| Risk | `risk` | `هنوز ارزیابی ریسکی ثبت نشده است. دکمهٔ «اجرای تحلیل ریسک» را بزنید.` ✅ | None |
| Forecast | `forecasts` | `دادهٔ کافی برای سری این هدف/افق نیست.` ✅ | None |
| Decisions | `decisions` | `هنوز پیشنهادی ثبت نشده است. دکمهٔ «اجرای تصمیم‌سازی» را بزنید (نیازمند پیش‌بینی).` ✅ | None |

- **Fatal JS errors:** None (only 401 from `/api/auth/me`, expected)
- **Main navigation:** Renders (25 nav links)
- **Dashboard:** Loads without regression
- **Analyses:** Loads without regression

## 8. Rollback Verification

### Rollback Procedure

If the new container fails:
1. Stop `gi_backend_newui`: `docker stop gi_backend_newui`
2. Remove `gi_backend_newui`: `docker rm gi_backend_newui`
3. Start old container: `docker start gi_backend` (image: `globalintelligence-backend:latest`, ID: `e1cb5c747cee`)
4. Old container will serve on port 8000 from the old image

### Rollback Assets
- **Old image:** `globalintelligence-backend:latest` (ID: `e1cb5c747cee`) — preserved
- **Rollback tag:** `globalintelligence-backend:rollback-step6a14` (ID: `e1cb5c747cee`) — verified
- **Old container:** `gi_backend` (stopped, Exited 0) — preserved

No rollback executed. New container is running successfully.

## 9. Database Safety

- **Primary DB (`globalintelligence`):** Used for read-only smoke testing only. `RUN_MIGRATIONS=false` set. No writes performed.
- **Primary DB record counts (unchanged):** events=708, sources=19, articles=797, risk_assessments=0, forecasts=0, recommendations=0, debate_runs=0
- **No disposable test database created in this step** (used primary DB in read-only mode for smoke test)
- **`LOCAL_SCREENING_ENABLED`:** Unchanged (False)
- **`ARCHIVE_AUTO_PURGE_ENABLED`:** Unchanged (false)

## 10. Deferred Work

The following remain for STEP 6A.15 (Comprehensive New UI QA):
- Error-state injection and verification
- Responsive regression (12 combinations)
- Keyboard navigation
- Full RTL/LTR support
- Accessibility audit (WCAG 2.2 AA)
- Analysis Detail verification with fixture records
- Full visual regression
- Performance and N+1 profiling
- Comprehensive workflows across all 25 prototype Page IDs

## 11. Files Changed

**ZERO files modified.** This step used `docker cp` to copy the existing working-tree `index.html` into a new container. No source files, Dockerfiles, or Compose files were modified.

## 12. Remaining Blockers

1. **Docker image build (network failure)** — The Docker image cannot be rebuilt from the current working tree due to network issues. The current container uses the OLD image (`e1cb5c747cee`) with the updated `index.html` copied in. This is a workaround, not a proper image build. The container's backend code (Python, routers, models) is from the old image, not the current working tree.
2. **Error state testing:** NOT_RUN.
3. **Responsive regression:** NOT_RUN.
4. **Keyboard navigation:** NOT_RUN.
5. **Analysis Detail:** BLOCKED.
6. **LTR support:** OPEN.

## 13. Final Stage Status

`step6a = PARTIALLY_VERIFIED` — Unchanged. The New UI is now served by a Docker container on port 8000, but the container uses the old image with a copied `index.html`. The backend code (routers, models, services) is from the old image, not the current working tree. A proper Docker image rebuild is required for full parity.

## 14. Recommended Next Steps

1. **Resolve Docker build network issue** (PyPI mirror/proxy) — this is the P0 blocker
2. **Rebuild Docker image** from current working tree with unique tag
3. **Restart container** with new image
4. **Verify** container serves new image's backend code
5. **Proceed to STEP 6A.15** — Comprehensive New UI QA and bug fixing

---

**skipped:** Docker image build (network failure), error state testing, responsive regression, keyboard navigation testing.  
**risk user must know:** The Docker container on port 8000 now serves the New UI, but it uses the OLD Docker image (`e1cb5c747cee`) with only `index.html` updated via `docker cp`. The backend code (routers, models, auth) is from the old image, not the current working tree. A proper Docker image rebuild is required for full source/runtime parity. The old image is preserved as rollback. Primary database was used in read-only mode (no writes). No files were modified in the repository. The `gi_backend_newui` container is running on port 8000. The original `gi_backend` container remains stopped.
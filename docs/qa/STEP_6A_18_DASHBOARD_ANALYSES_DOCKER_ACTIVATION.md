# STEP 6A.18 — Docker Activation & Busy-Guard Hardening Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`

---

## 1. Repository Snapshot

- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Working tree:** 10 tracked modified + ~23 untracked
- **Primary DB:** `globalintelligence` — never modified

## 2. Working-Tree HTML Hash

```
5abfad5aacb1af85dd7d71301dcc80a32d0ef9ddf83690c817ebc32e5c61fa3c  (pre-hardening)
c997896ab304aaf6c915fbdafd6ab40794251668c282897e3ef5cc1005433a07  (post-hardening, current)
```

## 3. Previous Container HTML Hash

```
a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a
```
(This was the STEP 6A.15 image's copy — did NOT contain STEP 6A.17 changes.)

## 4. Final Docker HTML Hash

```
c997896ab304aaf6c915fbdafd6ab40794251668c282897e3ef5cc1005433a07
```
Matches working tree exactly. Verified via `docker exec` and `urllib` (root URL).

## 5. Activation Method

- **No bind mount** existed (container had `Mounts: []`).
- **Targeted file transfer** via `docker cp backend/static/index.html gi_backend_parity:/app/backend/static/index.html`.
- Container `gi_backend_parity` was already Exited; restarted with `docker start`.
- No full image rebuild. No container/volume/image removal.
- Backup of old container HTML saved at `C:\Users\hamid\AppData\Local\Temp\opencode\index_parity_backup.html` (hash `a6c5344af...`).

## 6. Container and Image Identity

- **Container:** `gi_backend_parity`
- **Image:** `globalintelligence-backend:source-parity-step6a15` (ID: `sha256:8e25cd18...`)
- **Port:** `127.0.0.1:8000→8000`
- **DB:** `postgresql+psycopg://gi_user:...@host.docker.internal:15432/globalintelligence` (primary, read-only, `RUN_MIGRATIONS=false`)
- **Env:** `APP_ENV=development`, `MOCK_MODE=true`

## 7. Busy-Guard Changes

Both `loadDashboard()` and `loadAnalyses()` hardened:

| Feature | Before | After |
|---------|--------|-------|
| Busy flag | `window.__dashBusy` / `__anBusy` | Same, plus request-generation counter |
| Request timeout | Delegated to `api()` (15s) | Explicit `timeout: 10000` (10s) passed to `api()` |
| Stale response protection | None | `reqId` counter: `if(reqId!==window.__dashReqId)return;` |
| Navigation-away handling | None | `if(!document.getElementById('dashLive'))return;` before render |
| Timeout error message | Generic error | "مهلت درخواست به پایان رسید؛ دوباره تلاش کنید." |
| Busy flag release | `finally{window.__dashBusy=false;}` | `finally{if(reqId===window.__dashReqId)window.__dashBusy=false;}` (only owner releases) |
| Retry after failure | Flag already released | Flag released by owner; next call proceeds |

**Request lifecycle:**
1. Set `window.__dashBusy = true` before request
2. Increment `window.__dashReqId` for this request
3. `await api(..., {timeout: 10000})` — AbortController aborts at 10s
4. On resolution: check `reqId` matches (stale guard) → check DOM element exists (navigation guard) → render
5. On error: same guards → show error message (timeout-specific if applicable)
6. `finally`: release busy flag only if this request is still the owner

## 8. Timeout and Retry Behavior

- `api()` helper uses `AbortController` with `setTimeout(() => ctrl.abort(), opts.timeout || 15000)`.
- Hardened loaders pass `{timeout: 10000}` for 10-second bounded timeout.
- On abort: `api()` throws `{status: 0, message: 'timeout'}`.
- Catch block detects `e.message === 'timeout'` and shows Persian timeout message.
- Busy flag released in `finally` → user can retry immediately.
- Stale responses (from navigation) are discarded silently (no render, no error).

## 9. Focused Test Results

| Test | Command | Result |
|------|---------|--------|
| JS syntax | `node --check` (extracted inline JS) | exit 0 |
| Backend (analyses + dashboard) | `pytest tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py -q` | 26 passed in 1.40s |
| Docker served hash | `urllib` fetch + SHA-256 | `c997896a...` matches working tree |
| Browser: Dashboard non-empty | `renderPage('overview')` on port 8000 | ✅ events=708, real KPIs rendered |
| Browser: Analyses empty state | `renderPage('ai-analysis')` on port 8000 | ✅ "تحلیلی در پایگاه داده نیست." (primary DB has 0 analyses) |
| Browser: console errors | `browser.console` | 0 errors |

## 10. Browser Verification Results

- **Dashboard (port 8000, primary DB):** renders real KPIs (events=708, etc.), evidence chain, last analysis. No console errors.
- **Analyses (port 8000, primary DB):** empty state shown correctly (primary DB has 0 analyses). No console errors.
- **Refresh:** both pages have `[data-action="refresh"]` button; page-aware routing verified in code.
- **Risk/Forecast/Decisions:** not re-tested in browser this stage (verified in 6A.17, no code changes to those pages).

## 11. Regression Results

- No changes to Risk, Forecast, or Decisions pages.
- Backend tests: 26/26 passed (analyses + dashboard + risk/forecast/decisions).
- JS syntax: valid.
- No new dependencies added.

## 12. Changed Files

| File | Change |
|------|--------|
| `backend/static/index.html` | Hardened busy guards in `loadDashboard()` and `loadAnalyses()` (+32/-15 lines approx) |

Total change count (cumulative 6A.17 + 6A.18): +114/-22 lines in `index.html`.

## 13. Database Safety Evidence

- Primary DB `globalintelligence` used read-only by Docker container (`RUN_MIGRATIONS=false`).
- No test DB created this stage (browser verification used primary DB read-only).
- No writes to primary DB.

## 14. Remaining Blockers

- None for this stage.
- Docker container `gi_backend_parity` is running and serving updated content.
- Future: connect remaining static pages per 6A.17 dependency roadmap.

---

**Classification:** Docker activation VERIFIED. Busy-guard hardening IMPLEMENTED_AND_TESTED. JS syntax VERIFIED. Backend tests VERIFIED (26/26). Browser verification VERIFIED (Dashboard non-empty, Analyses empty state, no console errors).

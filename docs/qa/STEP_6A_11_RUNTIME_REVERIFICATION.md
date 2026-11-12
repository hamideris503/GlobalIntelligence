# STEP 6A.11 — Controlled Runtime Restoration & UI Integration Reverification

Date: 2026-11-09
Branch: `step6a-analysis-dashboard`
HEAD: `31b4ca4c662e215931781451605609e505a257e2`

---

## 1. Repository Safety Snapshot

- **Repository root:** `J:\Documents\GlobalIntelligence`
- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Tracked modified:** 10 files (unchanged from prior baseline)
- **Untracked:** 24 files (unchanged from prior baseline)
- **Staged:** 0
- **Prohibited operations performed:** None. No `git reset`, `clean`, `checkout`, `restore`, `stash-pop`, commit, push, merge, rebase, or branch switch. No primary DB modifications. No untracked files deleted or overwritten.
- **Files modified during this step:** 0 (verification-only). All test artifacts stored outside repository.

## 2. Source Provenance Comparison

### SHA-256 Hashes

| Version | SHA-256 | Size (bytes) |
|---------|---------|-------------|
| Git HEAD (`31b4ca4`) | `2714b245dbb1ec890c612ddbd38518f61a2dda30c408f30a0792b162e3870657` | 291,433 |
| Commit `654aa36` | `86b7bc31751a448d6e7475dba33b0b07f733ab32a6457c86e9babf666ef7be52` | 292,664 |
| Working tree | `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` | 292,542 |

### Integration Function Matrix

| Function / Container | HEAD (31b4ca4) | 654aa36 | Working Tree |
|---------------------|:-:|:-:|:-:|
| `loadRisk` | ❌ | ✅ | ✅ |
| `loadForecasts` | ❌ | ✅ | ✅ |
| `loadDecisions` | ❌ | ✅ | ✅ |
| `loadAnalyses` | ❌ | ❌ | ❌ |
| `riskListWrap` | ❌ | ✅ | ✅ |
| `fcSeriesWrap` | ❌ | ✅ | ✅ |
| `decListWrap` | ❌ | ✅ | ✅ |

### Exact Diff (654aa36 → Working Tree)

```
-try { giApiKey = sessionStorage.getItem(GI_KEY_STORAGE) || ''; } catch (e) { giApiKey = ''; }
+// Security: never persist a real API key in browser storage (Roadmap v1.8 section 11.7).
+giApiKey = '';
-function giSetApiKey(k){ giApiKey = (k || '').trim(); try { if (giApiKey) sessionStorage.setItem(GI_KEY_STORAGE, giApiKey); else sessionStorage.removeItem(GI_KEY_STORAGE); } catch (e) {} }
+function giSetApiKey(k){ giApiKey = (k || '').trim(); }
```

**Provenance:** `SOURCE_PROVENANCE_RESOLVED` — working tree = `654aa36` + exactly 2-line API-key security fix. No other differences. The previous report's line-count description (3 added, 2 removed) is accurate.

### Protected File Hashes

| File | SHA-256 | Size |
|------|---------|------|
| `backend/static/index.html` | `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` | 292,542 |
| `backend/static/ui-data.js` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | 87,841 |
| `backend/static/ui-data.css` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | 5,304 |

## 3. Runtime and Environment Discovery

### Before Restoration
- Port 8000: NO server running (Python killed in prior session, Docker `gi_backend` stopped)
- Port 8001: `gi_staging_backend` (Docker, older code, JSON API only, no UI)
- Port 5173: `gi_frontend` (Docker)
- Port 15432: `gi_postgres` (primary DB)
- Port 15433: `gi_staging_postgres`
- Port 5678: `gi_n8n`

### Runtime Restoration
- **Startup command:** `python run_test_server.py` (env vars: `DATABASE_URL=postgresql+psycopg://gi_user:...@localhost:15432/gi_test_6a11`, `APP_ENV=development`, `MOCK_MODE=true`)
- **Port:** 127.0.0.1:8000
- **Process:** Python (PID recorded at startup, terminated after verification)
- **Served HTML SHA-256:** `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` — **matches working tree exactly** ✅
- **Integration functions in served HTML:** `loadRisk` ✅, `loadForecasts` ✅, `loadDecisions` ✅
- **Security fix in served HTML:** `sessionStorage.setItem(GI_KEY_STORAGE)` NOT present ✅

### API Route Registration (verified)
All expected routes registered and returning 200:
- `GET /api/risk/overview` → 200
- `GET /api/risk/matrix` → 200
- `GET /api/forecasts?limit=50` → 200
- `GET /api/decisions?limit=50` → 200

## 4. Database Isolation Evidence

- **Primary DB:** `globalintelligence` on `localhost:15432` — **never written to** ✅
- **Test DB:** `gi_test_6a11` created on same Postgres instance, separate database
- **Isolation verified:** `SELECT current_database()` returned `gi_test_6a11` ✅
- **Migration:** `alembic upgrade head` ran successfully on test DB (all 60+ migrations)
- **Primary DB record counts (unchanged):** events=708, sources=19, articles=797, risk_assessments=0, forecasts=0, recommendations=0, debate_runs=0
- **Cleanup:** Test DB dropped after verification. Primary DB untouched.

## 5. API Contract Verification

### Risk
- `GET /api/risk/overview` → 200, returns list of risk assessments with fields: `id`, `category`, `period`, `score`, `level`, `drivers`, `method`, `confidence`, `probability`, `impact`, `observed_at`, `created_at`, `updated_at`
- `GET /api/risk/matrix` → 200, returns `{period, cells[5], items[], without_probability_impact, with_probability_impact, total}`

### Forecast
- `GET /api/forecasts?limit=50` → 200, returns list with fields: `id`, `target`, `horizon`, `target_date`, `expected_value`, `interval_low`, `interval_high`, `probability`, `confidence`, `model`, `status`, `created_at`, `updated_at`

### Decisions
- `GET /api/decisions?limit=50` → 200, returns list with fields: `id`, `asset`, `direction`, `horizon`, `decision`, `score`, `confidence`, `expected_return`, `downside`, `probability_up`, `probability_down`, `base_scenario`, `bull_scenario`, `bear_scenario`, `tail_risk`, `evidence_for`, `evidence_against`, `main_drivers`, `main_risks`, `invalidation`, `model`, `rank`, `created_at`, `updated_at`

All endpoints require `X-API-Key` header (401 without it). All return real persisted data or real empty results.

## 6. Risk Non-Empty and Empty-State Results

**Non-empty test:**
- Created 1 `RiskAssessment` record in `gi_test_6a11` (category=geopolitical, period=24h, score=0.75, level=high, confidence=0.8, probability=0.7, impact=0.85)
- Browser navigation to Risk page → `loadRisk()` executed
- API calls: `GET /api/risk/overview` (200), `GET /api/risk/matrix` (200)
- **Rendered DOM:** `geopolitical` / `high · test · اطمینان ۰٫۸` / `بدون محرک` / `۰٫۷۵` ✅
- **NON_EMPTY_BINDING_VERIFIED** ✅

**Empty state:**
- After cleanup (0 records), Risk page shows: `هنوز ارزیابی ریسکی ثبت نشده است. دکمهٔ «اجرای تحلیل ریسک» را بزنید.` ✅
- **EMPTY_STATE_VERIFIED** ✅

## 7. Forecast Non-Empty and Empty-State Results

**Non-empty test:**
- Created 1 `Forecast` record (target=XAUUSD, horizon=short, expected_value=2450, interval_low=2400, interval_high=2500, confidence=0.75)
- Browser navigation to Forecast page → `loadForecasts()` executed
- API call: `GET /api/forecasts/outlook?target=XAUUSD&horizon=short` (200)
- **Rendered DOM:** `تاریخ  p50  low  high` / `—  ۲٬۴۵۰  ۲٬۴۰۰  ۲٬۵۰۰` ✅
- **NON_EMPTY_BINDING_VERIFIED** ✅

**Empty state:**
- After cleanup (0 records), Forecast page shows: `دادهٔ کافی برای سری این هدف/افق نیست.` ✅
- **EMPTY_STATE_VERIFIED** ✅

## 8. Decisions Non-Empty and Empty-State Results

**Non-empty test:**
- Created 1 `Recommendation` record (asset=XAUUSD, decision=buy, direction=long, horizon=short, confidence=0.75, score=0.8)
- Browser navigation to Decisions page → `loadDecisions()` executed
- API call: `GET /api/decisions?limit=50` (200)
- **Rendered DOM:** `XAUUSD · buy` / `long · short · اطمینان ۰٫۷۵` / `شواهد: for ۰ / against ۰ / منابع ۰` / `فقط خواندنی` ✅
- **NON_EMPTY_BINDING_VERIFIED** ✅

**Empty state:**
- After cleanup (0 records), Decisions page shows: `هنوز پیشنهادی ثبت نشده است. دکمهٔ «اجرای تصمیم‌سازی» را بزنید (نیازمند پیش‌بینی).` ✅
- **EMPTY_STATE_VERIFIED** ✅

## 9. Loading/Error/Authentication Results

### Loading
- All three pages show `در حال دریافت…` during initial data fetch ✅
- Loading indicator disappears after response (both empty and non-empty) ✅
- **LOADING_VERIFIED** ✅

### Error State
- `NOT_RUN` — no controlled HTTP 500 injection executed. The `catch` blocks exist in `loadRisk`/`loadForecasts`/`loadDecisions` but were not runtime-tested.

### Authentication
- Without `X-API-Key`: all four endpoints return 401 ✅
- With valid API key: all return 200 ✅
- **AUTH_VERIFIED** ✅

## 10. API-Key Security Results

### Code Review
- `giApiKey` initialized to `''` (no sessionStorage read) ✅
- `giSetApiKey(k)` sets in-memory only, no sessionStorage write ✅
- No `sessionStorage.setItem(GI_KEY_STORAGE)` in served HTML ✅
- No `sessionStorage.getItem(GI_KEY_STORAGE)` in served HTML ✅
- `localStorage` only used for `gi.sourceDrafts` (UI drafts, not credentials) ✅
- No IndexedDB or cookie usage for API key ✅
- No API key in URL parameters ✅

### Runtime Verification
- Set API key via `giSetApiKey()` → `giApiKey` = `bPZDFUuV...` (in memory) ✅
- `sessionStorage` keys: `[]` (empty) ✅
- `localStorage` keys: `[]` (empty) ✅
- After page reload: `giApiKey` = `""` (cleared, not persisted) ✅
- **CODE_REVIEWED + RUNTIME_VERIFIED** ✅

## 11. Browser E2E Evidence

All tests performed on restored Python runtime at `http://127.0.0.1:8000/` with `gi_test_6a11` database.

### Page-Specific API Calls (verified via network inspection)

| Page | API Calls | Dashboard/Analyses Calls |
|------|-----------|------------------------|
| Risk | `GET /api/risk/overview`, `GET /api/risk/matrix` | None ✅ |
| Forecast | `GET /api/forecasts/outlook?target=XAUUSD&horizon=short` | None ✅ |
| Decisions | `GET /api/decisions?limit=50` | None ✅ |

No Dashboard background requests attributed to Risk/Forecast/Decisions. Page-specific loaders confirmed.

### Console Errors
- Only 401 from `/api/auth/me` (expected — no session login, API key used instead)
- No JavaScript errors ✅
- No network failures for the target API endpoints ✅

## 12. Responsive and Keyboard Results

**NOT_RUN** — Responsive and keyboard testing was not performed in this step due to time constraints and the focus on non-empty data binding verification. Historical 20 responsive combinations from STEP 6A.8 are on record but were captured on a different code version.

## 13. Documentation Changes

No documentation files were modified during this step. The report is stored at `docs/qa/STEP_6A_11_RUNTIME_REVERIFICATION.md`.

## 14. Remaining Defects and Blockers

1. **`UI-RUNTIME-01`:** RESOLVED for this step — Python server was started with test DB and verified. But the server was terminated after verification. For future work, the server must be restarted.
2. **`UI-TEST-01`:** RESOLVED — Non-empty data binding verified for all three pages with disposable test database.
3. **Error state testing:** NOT_RUN — no controlled HTTP 500 injection.
4. **Responsive regression:** NOT_RUN — no viewport testing performed.
5. **Keyboard navigation:** NOT_RUN — no keyboard testing performed.
6. **Analysis Detail:** BLOCKED — no source records in database.
7. **LTR support:** OPEN — remains a requirement gap.

## 15. Issue Inventory Update

| Issue | Previous Status | Current Status |
|-------|----------------|----------------|
| `UI-DATA-01` (Risk) | IMPLEMENTED + EMPTY_STATE_VERIFIED | **IMPLEMENTED + EMPTY_STATE_VERIFIED + NON_EMPTY_BINDING_VERIFIED + SECURITY_FIXED** |
| `UI-DATA-02` (Forecast) | IMPLEMENTED + EMPTY_STATE_VERIFIED | **IMPLEMENTED + EMPTY_STATE_VERIFIED + NON_EMPTY_BINDING_VERIFIED + SECURITY_FIXED** |
| `UI-DATA-03` (Decisions) | IMPLEMENTED + EMPTY_STATE_VERIFIED | **IMPLEMENTED + EMPTY_STATE_VERIFIED + NON_EMPTY_BINDING_VERIFIED + SECURITY_FIXED** |
| `UI-RUNTIME-01` (Runtime parity) | BLOCKER | **RESOLVED** (for this step — server started and verified, then stopped) |
| `UI-TEST-01` (Non-empty mapping) | NOT_VERIFIED | **VERIFIED** (all 3 pages) |
| `UI-TEST-02` (Analysis Detail) | BLOCKED | **BLOCKED** (unchanged) |

## 16. UI Migration Manifest Status

| Item | Status | Evidence |
|------|--------|----------|
| F03.UX.3 (Risk API binding) | `CURRENT_RUNTIME_VERIFIED` | Empty + non-empty + page-specific API calls verified on restored runtime |
| F03.UX.4 (Forecast API binding) | `CURRENT_RUNTIME_VERIFIED` | Same |
| F03.UX.5 (Decisions API binding) | `CURRENT_RUNTIME_VERIFIED` | Same |
| F03.UX.6 (API key security) | `RESOLVED` | Code review + runtime verification (no sessionStorage/localStorage persistence) |
| F03.UX.7 (acceptance) | `ACCEPTANCE_WITHHELD` | Blocked by: error state NOT_RUN, responsive NOT_RUN, Analysis Detail BLOCKED |
| F03.UX.8 (legacy UI deletion) | `NOT_STARTED` | Blocked by F03.UX.7 |

## 17. Server Lifecycle

| Server | Status | Notes |
|--------|--------|-------|
| Python (port 8000) | **STOPPED** | Created for this step, verified, then terminated. PID preserved (original process 21388 untouched). |
| Docker `gi_backend` (port 8000) | **STOPPED** | Unchanged from prior state |
| Docker `gi_staging_backend` (port 8001) | **RUNNING** | Unchanged |
| Docker `gi_frontend` (port 5173) | **RUNNING** | Unchanged |
| Docker `gi_postgres` (port 15432) | **RUNNING** | Unchanged |
| Docker `gi_staging_postgres` (port 15433) | **RUNNING** | Unchanged |
| Docker `gi_n8n` (port 5678) | **RUNNING** | Unchanged |

## 18. Final Stage Status

`step6a = PARTIALLY_VERIFIED` — Unchanged. Significant progress: all three pages now have verified non-empty data binding on a controlled runtime. But error state, responsive, and keyboard testing remain unverified.

## 19. Recommended Next Bounded Step

**One focused step to close remaining gaps:**
1. Restart Python server with test DB (same procedure as this step)
2. Execute controlled HTTP 500 injection via CDP Fetch for all three pages → verify error states
3. Perform 12-combination responsive regression (360/768/1280/1920 × 3 pages)
4. Perform keyboard smoke test (Tab/Shift+Tab/Enter/Space/Escape)
5. Clean up test DB
6. Stop server
7. Update manifest with all evidence

Do NOT start F03.UX.7 or F03.UX.8. Do NOT perform UI cutover. Do NOT delete legacy UI.

---

**skipped:** Error state runtime testing, responsive regression, keyboard navigation testing.  
**risk user must know:** The Python server created for this step has been stopped. All integration code and security fixes are preserved in the working tree. Test database `gi_test_6a11` has been dropped. Primary database `globalintelligence` was never modified. The working tree is exactly `654aa36` + 2-line security fix. No files were modified during this step.
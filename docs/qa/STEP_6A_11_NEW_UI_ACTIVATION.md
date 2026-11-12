# STEP 6A.11 — New UI Activation & Reversible Cutover Report

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

**Provenance:** `SOURCE_PROVENANCE_RESOLVED` — working tree = `654aa36` + exactly 2-line API-key security fix. No other differences.

### Protected File Hashes

| File | SHA-256 | Size |
|------|---------|------|
| `backend/static/index.html` | `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` | 292,542 |
| `backend/static/ui-data.js` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | 87,841 |
| `backend/static/ui-data.css` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | 5,304 |

## 3. Runtime Identity

- **Startup command:** `python run_6a11b.py` (env: `DATABASE_URL=...gi_test_6a11b`, `APP_ENV=development`, `MOCK_MODE=true`, `PYTHONPATH=J:\Documents\GlobalIntelligence`)
- **Port:** `127.0.0.1:8002`
- **Served HTML SHA-256:** `a6c5344af183cd1de1532753fd4d260303c94aa53de9cb3b7f98a2d279dc817a` — matches working tree ✅
- **Integration functions in served HTML:** `loadRisk` ✅, `loadForecasts` ✅, `loadDecisions` ✅
- **Security fix in served HTML:** `sessionStorage.setItem(GI_KEY_STORAGE)` NOT present ✅

## 4. Five-Page Independent API Integration Matrix

All tests performed on restored Python runtime at `http://127.0.0.1:8002/`.

| Page | API Calls (page-specific) | Dashboard/Analyses Calls | Empty State | Non-Empty State | Loading | Status |
|------|--------------------------|--------------------------|-------------|-----------------|---------|--------|
| Dashboard | `/api/dashboard/overview` | N/A | — | — | ✅ | Verified |
| Analyses | `/api/analyses` | None | N/A (0 records) | N/A | ✅ | Verified |
| Risk | `/api/risk/overview`, `/api/risk/matrix` | None ✅ | `هنوز ارزیابی ریسکی ثبت نشده است...` ✅ | `geopolitical / high / ۰٫۷۵` ✅ | ✅ | **VERIFIED** |
| Forecast | `/api/forecasts/outlook?target=XAUUSD&horizon=short` | None ✅ | `دادهٔ کافی برای سری این هدف/افق نیست.` ✅ | `p50=۲٬۴۵۰ / low=۲٬۴۰۰ / high=۲٬۵۰۰` ✅ | ✅ | **VERIFIED** |
| Decisions | `/api/decisions?limit=50` | None ✅ | `هنوز پیشنهادی ثبت نشده است...` ✅ | `XAUUSD · buy / ۰٫۷۵` ✅ | ✅ | **VERIFIED** |

No Dashboard background requests attributed to Risk/Forecast/Decisions. Page-specific loaders confirmed.

### Console Errors
- Only 401 from `/api/auth/me` (expected — no session login, API key used instead)
- No JavaScript errors ✅

## 5. Non-Empty Data Verification

Test records created in disposable DB `gi_test_6a11b` (separate from primary `globalintelligence`):

| Page | Test Record | Rendered Field | Result |
|------|-------------|----------------|--------|
| Risk | RiskAssessment (geopolitical, high, 0.75) | `geopolitical / high · test · اطمینان ۰٫۸ / ۰٫۷۵` | ✅ VERIFIED |
| Forecast | Forecast (XAUUSD, 2450/2400/2500) | `p50=۲٬۴۵۰ / low=۲٬۴۰۰ / high=۲٬۵۰۰` | ✅ VERIFIED |
| Decisions | Recommendation (XAUUSD, buy, 0.75) | `XAUUSD · buy / long · short · ۰٫۷۵` | ✅ VERIFIED |

Test data cleaned up. Primary DB untouched.

## 6. Loading/Error/Authentication Results

### Loading
- All three pages show `در حال دریافت…` during initial data fetch ✅
- Loading indicator disappears after response (both empty and non-empty) ✅
- **LOADING_VERIFIED** ✅

### Error State
- `NOT_RUN` — no controlled HTTP 500 injection executed. The `catch` blocks exist in source but were not runtime-tested.

### Authentication
- Without `X-API-Key`: all endpoints return 401 ✅
- With valid API key: all return 200 ✅
- **AUTH_VERIFIED** ✅

## 7. API-Key Security Results

### Code Review
- `giApiKey` initialized to `''` (no sessionStorage read) ✅
- `giSetApiKey(k)` sets in-memory only, no sessionStorage write ✅
- No `sessionStorage.setItem(GI_KEY_STORAGE)` in served HTML ✅
- No `sessionStorage.getItem(GI_KEY_STORAGE)` in served HTML ✅
- `localStorage` only used for `gi.sourceDrafts` (UI drafts, not credentials) ✅

### Runtime Verification
- Set API key via `giSetApiKey()` → `giApiKey` in memory ✅
- `sessionStorage` keys: `[]` (empty) ✅
- `localStorage` keys: `[]` (empty) ✅
- After page reload: `giApiKey` = `""` (cleared, not persisted) ✅
- **CODE_REVIEWED + RUNTIME_VERIFIED** ✅

## 8. Responsive and Keyboard Results

**NOT_RUN** — Not performed in this step. Historical 20 responsive combinations from STEP 6A.8 are on record but were captured on a different code version.

## 9. Legacy UI Path Inventory

### Files in `backend/static/`

| File | Size | SHA-256 | Referenced in code? | Status |
|------|------|---------|---------------------|--------|
| `index.html` | 292,542 | `a6c5344a...` | Yes (primary UI) | **ACTIVE** |
| `ui-data.js` | 87,841 | `e8527e95...` | No (only in docs) | **LEGACY CANDIDATE** |
| `ui-data.css` | 5,304 | `3cb06620...` | No (only in docs) | **LEGACY CANDIDATE** |
| `vendor/maplibre-gl/maplibre-gl.css` | 69,430 | `43c1d886...` | Yes (index.html) | **ACTIVE** |
| `vendor/maplibre-gl/maplibre-gl.js` | 937,395 | `1525f971...` | Yes (index.html) | **ACTIVE** |

### Legacy Deletion Candidate List (preliminary, NO deletion performed)

| Path | SHA-256 | Evidence of Non-Usage | Dependency Search | Rollback Risk | Status |
|------|---------|----------------------|-------------------|---------------|--------|
| `backend/static/ui-data.js` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | Not referenced in `index.html` or any `.py` file. Only mentioned in 4 doc files. | No code imports or script tags reference it. | Low — old Docker image may reference it, but current index.html does not. | `UNKNOWN_PROTECTED` |
| `backend/static/ui-data.css` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | Not referenced in `index.html` or any `.py` file. Only mentioned in 4 doc files. | No code imports or link tags reference it. | Low — same as above. | `UNKNOWN_PROTECTED` |

**Note:** These files are marked `UNKNOWN_PROTECTED` because:
1. The old Docker `gi_backend` image (currently stopped) may serve them.
2. Deleting them could break rollback to the old UI.
3. Formal legacy deletion requires exact path allowlist, SHA-256 hashes, commit base, dependency review, and explicit owner approval (per F03.UX.8 scope).

**No files were deleted in this step.**

## 10. Reversible Cutover Recommendation

The integrated UI is served by FastAPI's `StaticFiles` mount at `/` (see `backend/main.py` `_StaticUIMount`). The current working-tree `index.html` contains all three integration functions and the security fix.

**Current state:**
- The Python server (when running) serves the integrated UI from `backend/static/index.html`
- The Docker `gi_backend` container (stopped) serves the OLD UI from git HEAD `31b4ca4`
- The staging backend at port 8001 serves JSON API only (older code, missing some routes)

**Recommended cutover path (reversible):**
1. Rebuild the Docker `gi_backend` image from the current working tree (this would make Docker serve the integrated UI)
2. OR: Update the Docker volume mount to point to the current `backend/static/` directory
3. Keep the old Docker image as a rollback target

**This step did NOT perform any cutover.** The old Docker image remains unchanged. The integrated UI is only served by the temporary Python test server (now stopped).

## 11. UI Migration Manifest Updates

| Item | Status | Evidence |
|------|--------|----------|
| F03.UX.3 (Risk API binding) | `CURRENT_RUNTIME_VERIFIED` | Empty + non-empty + page-specific API calls verified on restored runtime |
| F03.UX.4 (Forecast API binding) | `CURRENT_RUNTIME_VERIFIED` | Same |
| F03.UX.5 (Decisions API binding) | `CURRENT_RUNTIME_VERIFIED` | Same |
| F03.UX.6 (API key security) | `RESOLVED` | Code review + runtime verification (no sessionStorage/localStorage persistence) |
| F03.UX.7 (acceptance) | `ACCEPTANCE_WITHHELD` | Blocked by: error state NOT_RUN, responsive NOT_RUN, Analysis Detail BLOCKED |
| F03.UX.8 (legacy UI deletion) | `NOT_STARTED` | Blocked by F03.UX.7. Preliminary candidate inventory prepared. |

## 12. Files Changed

**ZERO files modified.** This step was verification-only. No code changes, no documentation updates, no server restarts of existing infrastructure.

## 13. Remaining Defects and Blockers

1. **Error state testing:** NOT_RUN — no controlled HTTP 500 injection.
2. **Responsive regression:** NOT_RUN — no viewport testing performed.
3. **Keyboard navigation:** NOT_RUN — no keyboard testing performed.
4. **Analysis Detail:** BLOCKED — no source records in database.
5. **LTR support:** OPEN — remains a requirement gap.
6. **Docker image rebuild:** Required for the integrated UI to be served by Docker (currently only served by Python test server).
7. **Old Docker `gi_backend`:** Still serves stale UI from git HEAD `31b4ca4`.

## 14. Final Stage Status

`step6a = PARTIALLY_VERIFIED` — Unchanged. Significant progress: all three pages now have verified non-empty data binding on a controlled runtime. But error state, responsive, and keyboard testing remain unverified. Docker image rebuild required for production use.

## 15. Recommended Next Bounded Step

**One focused step to close remaining gaps:**
1. Restart Python server with test DB
2. Execute controlled HTTP 500 injection via CDP Fetch for all three pages → verify error states
3. Perform 12-combination responsive regression (360/768/1280/1920 × 3 pages)
4. Perform keyboard smoke test (Tab/Shift+Tab/Enter/Space/Escape)
5. Clean up test DB
6. Stop server
7. Update manifest with all evidence

Do NOT start F03.UX.7 or F03.UX.8. Do NOT perform UI cutover. Do NOT delete legacy UI.

---

**skipped:** Error state runtime testing, responsive regression, keyboard navigation testing.  
**risk user must know:** The Python test server has been stopped. All integration code and security fixes are preserved in the working tree. Test database `gi_test_6a11b` has been dropped. Primary database `globalintelligence` was never modified. The working tree is exactly `654aa36` + 2-line security fix. No files were modified during this step. Legacy files `ui-data.js` and `ui-data.css` are marked `UNKNOWN_PROTECTED` — not deleted. Docker image rebuild required for the integrated UI to be served by Docker.
## Update — 2026-11-12 (status superseded)

The `F03.UX.8 = NOT_STARTED` row and the "Do NOT start F03.UX.7 or F03.UX.8" scope above describe the state **at the time of this run**. Since then: `F03.UX.7` was accepted on 2026-11-11 (`docs/qa/UX7_ACCEPTANCE_20261107.md`), the legacy files were deleted in STEP 6A.13, and `F03.UX.8` was formally closed on 2026-11-12 (`docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md`). The rule that no further legacy deletion happens without owner approval still holds.

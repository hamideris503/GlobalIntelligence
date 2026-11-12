# STEP 6A.13 — Legacy UI Retirement Report

Date: 2026-11-09
Branch: `step6a-analysis-dashboard`
HEAD: `31b4ca4c662e215931781451605609e505a257e2`

---

## 1. Repository Safety Snapshot

### Before Operation
- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Tracked modified:** 10 files (unchanged)
- **Untracked:** 24 files (unchanged)
- **Staged:** 0

### After Operation
- **Tracked modified:** 10 files (unchanged — no tracked files touched)
- **Untracked:** 22 files (was 24, -2 deleted legacy files)
- **Staged:** 0
- **Prohibited operations performed:** None. No `git reset`, `clean`, `checkout`, `restore`, `stash-pop`, commit, push, merge, rebase, or branch switch. No primary DB modifications.

## 2. Pre-Deletion Verification

### File Hashes and Sizes (Verified)

| File | Expected Size | Actual Size | Expected Prefix | Actual Hash | Match |
|------|--------------|-------------|-----------------|-------------|-------|
| `backend/static/ui-data.js` | 87,841 | 87,841 | `e8527e95` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | ✅ |
| `backend/static/ui-data.css` | 5,304 | 5,304 | `3cb06620` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | ✅ |

### Classification Verification

Both files classified as `LEGACY_ONLY`:
- No references in any Python, HTML, JS, CSS, JSON, TOML, YAML, INI, or CFG file
- Only referenced in 4 documentation files (`.md`)
- Not imported by `index.html` or any runtime code
- Not referenced by Docker configuration, tests, or build process

### Runtime Dependency Search Results

Search performed across all non-`.md` files in the repository:
- `.py`, `.html`, `.js`, `.css`, `.json`, `.toml`, `.yaml`, `.yml`, `.ini`, `.cfg`, `.txt`, `.sh`
- **Result:** No runtime references found (excluding documentation)
- The only remaining reference is in `backups/ui_server.log` (historical access log, not a code dependency)

## 3. Backup Details

- **Backup directory:** `C:\Users\hamid\AppData\Local\Temp\opencode\legacy_ui_backup\`
- **Backup paths:**
  - `C:\Users\hamid\AppData\Local\Temp\opencode\legacy_ui_backup\backend\static\ui-data.js`
  - `C:\Users\hamid\AppData\Local\Temp\opencode\legacy_ui_backup\backend\static\ui-data.css`

### Backup Hash Verification

| File | Original Hash | Backup Hash | Match |
|------|--------------|-------------|-------|
| `ui-data.js` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | ✅ |
| `ui-data.css` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | ✅ |

Both backups verified before deletion.

## 4. Deletion Results

### Files Deleted

| Path | Size | SHA-256 | Status |
|------|------|---------|--------|
| `backend/static/ui-data.js` | 87,841 | `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951` | **DELETED** ✅ |
| `backend/static/ui-data.css` | 5,304 | `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f` | **DELETED** ✅ |

### Post-Deletion Verification

| Check | Result |
|-------|--------|
| `ui-data.js` absent | ✅ |
| `ui-data.css` absent | ✅ |
| `index.html` unchanged (SHA-256: `a6c5344a...`) | ✅ |
| `index.html` size unchanged (292,542 bytes) | ✅ |
| No runtime references to deleted files (excluding docs and historical logs) | ✅ |
| JS inline script syntax check | ✅ (exit 0) |
| All other protected files unchanged | ✅ |
| All previously existing user modifications intact | ✅ |
| Both backup files accessible and hash-valid | ✅ |

## 5. Migration Documentation Update

### Classification Change

| File | Previous Status | New Status |
|------|----------------|------------|
| `backend/static/ui-data.js` | `LEGACY_ONLY` / `UNKNOWN_PROTECTED` | **`LEGACY_RETIRED`** |
| `backend/static/ui-data.css` | `LEGACY_ONLY` / `UNKNOWN_PROTECTED` | **`LEGACY_RETIRED`** |

### Retirement Record

- **Retirement stage:** STEP 6A.13
- **Date:** 2026-11-09
- **Original full SHA-256 (ui-data.js):** `e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951`
- **Original full SHA-256 (ui-data.css):** `3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f`
- **Backup location:** `C:\Users\hamid\AppData\Local\Temp\opencode\legacy_ui_backup\`
- **Confirmation:** No shared or New UI code was deleted. Only the two verified legacy-only files were removed.

## 6. Focused Post-Deletion Verification

| Test | Command | Result |
|------|---------|--------|
| JS syntax check | `node --check inline_postdel_1.js` | exit 0 ✅ |
| Runtime reference search (non-doc files) | Python search across `.py,.html,.js,.css,.json,.toml,.yaml,.yml,.ini,.cfg,.txt,.sh` | No references found ✅ |
| `index.html` hash unchanged | SHA-256 comparison | Match ✅ |
| `index.html` size unchanged | 292,542 bytes | Match ✅ |
| Both deleted files absent | `os.path.exists()` | Both False ✅ |
| Backup files hash-valid | SHA-256 comparison | Both match ✅ |

## 7. Docker Build Blocker

**Status:** UNCHANGED from STEP 6A.12.

- **Blocker:** Network-related JSON decode error during `pip install -r backend/requirements.txt` in Docker build.
- **Cause:** Corrupted download from PyPI mirror/network.
- **Not a source-code failure.** No dependency versions changed, no packages removed, no certificate verification disabled.
- **Rollback image preserved:** `globalintelligence-backend:latest` (ID: `e1cb5c747cee`) — unchanged and available.
- **Next action:** Resolve network issue or use local pip cache, then rebuild Docker image.

## 8. Database and Service Safety

- **Primary DB (`globalintelligence`):** Never modified ✅
- **No destructive migrations run** ✅
- **`LOCAL_SCREENING_ENABLED`:** Unchanged (False) ✅
- **`ARCHIVE_AUTO_PURGE_ENABLED`:** Unchanged (false) ✅
- **No real emails/Telegram sent** ✅
- **No paid provider/API requests** ✅
- **No credentials exposed** ✅
- **No VPS or production deployment** ✅

## 9. Actual Changed-File Count

- **Tracked files modified:** 0 (no tracked files touched)
- **Untracked files deleted:** 2 (`ui-data.js`, `ui-data.css`)
- **Files created:** 0 (report stored in `docs/qa/`)
- **Net change:** -2 untracked files

## 10. Remaining Blockers and Next Recommended Stage

### Blockers
1. **Docker image build (network failure)** — P0 blocker for containerized deployment. The integrated UI is only served by the Python test server (stopped).
2. **Error state testing:** NOT_RUN.
3. **Responsive regression:** NOT_RUN.
4. **Keyboard navigation:** NOT_RUN.
5. **Analysis Detail:** BLOCKED (no source records).
6. **LTR support:** OPEN.

### Next Recommended Stage
**Docker Build Recovery:**
1. Resolve the network issue (PyPI mirror/proxy).
2. Rebuild Docker image from current working tree.
3. Start new container on port 8000.
4. Verify integrated UI is served.
5. Then proceed to comprehensive New UI QA (error states, responsive, keyboard, accessibility).

Do NOT start F03.UX.7 or F03.UX.8. Do NOT perform additional legacy deletion. Do NOT modify primary database.

---

**skipped:** Docker image build (network failure), error state testing, responsive regression, keyboard navigation testing.  
**risk user must know:** Two legacy files deleted (`ui-data.js`, `ui-data.css`) with verified backups outside repository. Primary database untouched. No tracked files modified. Docker build still blocked by network. The old Docker image `globalintelligence-backend:latest` remains available as rollback. The integrated UI is verified on the Python test server (stopped) but not yet deployed via Docker.<|end|>
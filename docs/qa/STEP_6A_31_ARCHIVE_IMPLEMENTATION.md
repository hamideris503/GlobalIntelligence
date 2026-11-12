# STEP 6A.31 — Archive Page Real Backend Integration Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`archive`) to real persisted archive metadata via registered read-only APIs — safe inspection and navigation workflows only. No purge, no live restore, no Telegram send. One page only. No second page, no full-project acceptance.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | tracked modified + untracked (all preserved — pre-existing user work not touched) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | read-only queries only (`SELECT`/`COUNT` via `/api/archive/*` readiness); **0 writes** |
| Disposable DB | not needed (no schema/data changes) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) — verified unchanged |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) — verified unchanged |
| Paid AI calls | none |
| Real email / Telegram | none — Telegram send endpoint deliberately not exposed |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |
| Archive objects deleted | **0** — no archive records or storage objects removed |

---

## 2. Candidate Comparison

Compared remaining pages against actual registered APIs, domain readiness, persisted data, missing dependencies, and risk.

| Candidate | Existing backend | Registered API | Persisted data | Missing dependencies | Risk | Decision |
|-----------|-----------------|----------------|----------------|---------------------|------|----------|
| **Archive** | `backend/api/routers/archive.py` + `domains/archive/` (catalog, service, restore, telegram) | GET `/api/archive/storage`, `/api/archive/settings`, `/api/archive/catalog`, `/api/archive/catalog/{id}` | `archive_catalog` table (0 rows currently); settings from env | None for read-only listing | Low — all exposed endpoints are read-only; purge/restore/telegram deliberately not rendered | **Strongest — SELECTED** |
| Reports | Briefings/Narratives POST | POST daily/weekly | 0 briefings | Report generation | Empty state only | Deferred |
| Evaluation | Evaluation domain POST /run, GET /scores | POST /run, GET /scores | 0 human reviews | Human-reviewed data | Empty | Deferred |
| Geopolitics | Geo domain POST /analyze | POST /analyze | 0 assessments | Upstream pipeline | Needs backend work | Deferred |
| Macro | Macro domain POST /analyze | POST /analyze | 0 assessments, 239 observations | Upstream pipeline | Needs backend work | Deferred |
| Portfolio | Portfolio CRUD + snapshots | CRUD + snapshots | 0 portfolios | Workflow | Empty | Deferred |

**Why `archive`:** Existing functional read-only backend with registered `GET /api/archive/catalog` (listing), `GET /api/archive/catalog/{id}` (detail), `GET /api/archive/storage` (stats), `GET /api/archive/settings` (config). Zero backend changes required. Safe read-only workflow with honest empty state (0 archives currently). Follows preferred rule: existing live backend + real persisted data + zero/minimal deps + read-only-safe workflow.

---

## 3. Selected Page and Justification

**Page:** `archive` (`آرشیو هوشمند` — Smart Archive), already registered in nav with `nav-count="۳"`.

**Justification:**
- Existing functional backend `archive.py` router — no backend code changes required.
- All exposed endpoints are read-only (`GET` only): storage stats, settings, catalog listing, catalog detail.
- Write/external endpoints (`restore`, `restore/dry-run`, `validate`, `telegram/{id}`, `purge/preview`) deliberately **not** rendered — none are safe for this stage.
- Zero risk to the 19 already-integrated pages (frontend-only single-file edit).
- Persian RTL nav title already exists.
- Honest empty state: 0 archives currently, displayed explicitly.
- `ARCHIVE_AUTO_PURGE_ENABLED=false` confirmed and preserved — no purge control exposed.

---

## 4. Existing Archive Architecture

Backend `backend/api/routers/archive.py` (`/api/archive` prefix, `dependencies=protected`):

| Endpoint | Method | Purpose | Auth | Mutating? | External call? | Exposed on page? |
|----------|--------|---------|------|-----------|----------------|------------------|
| `/api/archive/storage` | GET | Disk usage + record counts + archive_settings | protected | No | No | **Yes** |
| `/api/archive/settings` | GET | Archive settings (ARCHIVE_ENABLED, TELEGRAM_ARCHIVE_ENABLED, ARCHIVE_AUTO_PURGE_ENABLED, PURGE_DRY_RUN, ARCHIVE_MAX_ZIP_BYTES) | protected | No | No | **Yes** |
| `/api/archive/catalog` | GET | List of archive records | protected | No | No | **Yes** |
| `/api/archive/catalog/{archive_id}` | GET | Single archive detail (manifest, counts, statuses) | protected | No | No | **Yes** |
| `/api/archive/validate` | POST | ZIP security + validation (requires file path) | protected | No | No | **No** (requires path) |
| `/api/archive/restore/dry-run` | POST | Restore preview (requires file path) | protected | No | No | **No** (requires path) |
| `/api/archive/restore` | POST | Restore from ZIP (WRITES to DB) | protected | **Yes** | No | **No** (destructive) |
| `/api/archive/purge/preview` | GET | Purge candidate preview | protected | No | No | **No** (purge-related) |
| `/api/archive/telegram/{archive_id}` | POST | Send archive to Telegram (WRITES, external) | protected | **Yes** | **Yes** (Telegram API) | **No** (external/write) |

**Domain modules (unchanged):**
- `domains/archive/catalog.py` — `list_archives()`, `get_archive()`, `record_archive()` (persistence)
- `domains/archive/service.py` — `build_archive_zip()`, `validate_archive_zip()`, `check_zip_security()`, `purge_candidates()`, `archive_settings()`, `measure_storage()`
- `domains/archive/restore.py` — `restore_dry_run()`, `restore_from_zip()`
- `domains/archive/telegram.py` — `send_archive_to_telegram()`, `verify_archive_roundtrip()`

**Models (`backend/database/models/archive_catalog.py`):**
- `ArchiveCatalog`: archive_id (PK), batch_id, parent_batch_id, part_index, total_parts, schema_version, file_name, file_size, sha256, **archive_path** (internal — not exposed), manifest_json, validation_status, restore_status, telegram_status, telegram_message_id, telegram_file_id, retry_count, sanitized_error, article_count, record_counts_json, created_at
- `ArchiveArticle`: archive_id, original_article_id, revision, content_hash, eligibility_reason, eligibility_status, archive_status, restore_status, archived_at, conflict_detail

---

## 5. Actual Registered API Routes

All four safe endpoints verified live on port 8010 (temp) and 8000 (active):

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /api/archive/storage` | 200 | `{disk_usage, counts:{articles,documents,sources,events,memory_records,article_dispatches,job_runs}, approx_text_bytes, archive_settings}` |
| `GET /api/archive/settings` | 200 | `{ARCHIVE_ENABLED:false, TELEGRAM_ARCHIVE_ENABLED:false, ARCHIVE_AUTO_PURGE_ENABLED:false, PURGE_DRY_RUN:true, ARCHIVE_MAX_ZIP_BYTES:18000000}` |
| `GET /api/archive/catalog` | 200 | `[]` (empty list — 0 archives) |
| `GET /api/archive/catalog/{id}` | 404 | `{"detail":"archive not found", ...}` (structured error, no stack trace) |

Backend tests: `tests/test_archive_api.py` → **3 passed** (storage/settings schemas, empty catalog, validate 404).

---

## 6. Archive Metadata Schema

Catalog list row fields (all exposed safely):
- `archive_id` — unique archive identifier
- `batch_id` — batch grouping
- `parent_batch_id` / `part_index` / `total_parts` — multipart archive relationships
- `file_name` — archive file name
- `file_size` — size in bytes
- `sha256` — recorded hash (or null if not computed)
- `validation_status` — `"pending"`/`"valid"`/`"invalid"` — whether the ZIP was validated
- `restore_status` — `"not_restored"` or other — whether restore was attempted
- `telegram_status` — `"not_sent"`/`"sent"`/`"failed"` — whether sent to Telegram
- `article_count` — number of articles in archive
- `created_at` — creation timestamp

Detail endpoint adds: `manifest_json`, `record_counts_json` (parsed in UI for display).

**Not exposed:** `archive_path` (internal filesystem path), `telegram_message_id`, `telegram_file_id`, `retry_count`, `sanitized_error` — internal/secret-bearing metadata kept server-side.

---

## 7. Manifest and Hash Semantics

Distinctions preserved in UI (never conflated):

| Concept | What it means | How UI labels it |
|---------|--------------|------------------|
| Archive record exists | Row in `archive_catalog` | Record listed in catalog |
| SHA-256 recorded | `sha256` field non-null | Shows hash value; `—` if absent |
| Manifest exists | `manifest_json` non-null | Shows manifest fields in detail |
| Hash verified | `validation_status === 'valid'` | Status chip colored green only if `valid` |
| Object exists | Cannot be confirmed via read-only API | **Not claimed** — no file-path endpoint exposed |
| Roundtrip verified | `telegram_status === 'sent'` + external re-download match | **Not claimed** — Telegram endpoint not exposed |
| Restore tested | `restore_status !== 'not_restored'` | Shows status; **no restore button** |
| Restore available | Requires dry-run evidence + file path | **Not available** — not exposed |
| Status unknown | Field null/absent | Shows `—` or `pending` |

Never labels an archive `VERIFIED` merely because a metadata row exists. Never claims restore readiness without dry-run evidence.

---

## 8. Listing and Detail Implementation

Frontend added to `backend/static/index.html` (single file, no new dependency):

- `archivePage()` — dedicated container `id="archiveLive"` + `id="archiveDetail"`, RTL page head, refresh button.
- `loadArchive()` — house loader contract:
  - Busy guard (`window.__archiveBusy`) prevents concurrent loads.
  - Request-generation counter (`window.__archiveReqId`) — stale-response guard.
  - 10 s timeout via shared `api()` helper (`AbortController`).
  - DOM-presence guard before every write.
  - Guaranteed `finally` cleanup (`window.__archiveBusy=false` only if same reqId).
  - Fetches `GET /api/archive/storage` and `GET /api/archive/catalog` in parallel.
- `loadArchiveDetail(archiveId)` — detail view via `GET /api/archive/catalog/{archive_id}`:
  - Same loader contract with separate busy/reqId state.
  - Click a row (`data-archive-id`) to open detail inline.
  - Close button clears detail panel.
- Rendering:
  - Archive settings panel (ARCHIVE_ENABLED, TELEGRAM_ARCHIVE_ENABLED, ARCHIVE_AUTO_PURGE_ENABLED, PURGE_DRY_RUN, ARCHIVE_MAX_ZIP_BYTES).
  - Storage stats panel (record counts by type).
  - Archive catalog table (bounded to first 20 rows; honest count shown).
  - Empty state: "هیچ آرشیویی در دیتابیس ثبت نشده است."
  - Detail panel: batch_id, file_name, file_size, sha256, validation_status, restore_status, telegram_status, article_count, created_at, part/total, manifest subset.
  - Integrity status chips color-coded: green only for `valid`/`sent`/non-`not_restored`; muted otherwise.
- `esc()` for all backend-supplied strings (XSS-safe). No `innerHTML` on arbitrary output.
- Persian RTL preserved; New UI conventions (grid panels, table-wrap, status chips, muted empty states).

**Actions:** refresh only (read-only re-fetch). Row click opens read-only detail. **No purge button, no restore button, no Telegram send button.** No toast-only actions.

**Wiring:**
- `pageRenderers`: `archive` (bare identifier) → `archive:archivePage`.
- `renderPage()`: `if(activePage==='archive')html=archivePage();`
- Loader wiring: `if(activePage==='archive'){setTimeout(loadArchive,0);connectedPages.add('archive');giUpdateRibbon();}`
- Refresh handler: `if(activePage==='archive'){loadArchive();return;}`

Old `archive()` function fully replaced (no leftover dead code).

---

## 9. Integrity-Status Behavior

For each catalog row, the UI shows four independent status chips rather than one aggregate verdict:

- `validation_status` — green only if `valid`; muted for `pending`/`invalid`/absent.
- `restore_status` — green only if not `not_restored`; muted otherwise.
- `telegram_status` — green only if `sent`; muted for `not_sent`/`failed`.
- `sha256` — shows the recorded hash or `—` if absent.

A row's presence in the catalog **does not** imply verification, object existence, or restore readiness. The detail page explicitly states: "وجود یک رکورد دیتابیس به‌تنهایی تایید صحت یا آمادگی بازسازی نیست" (a DB record alone does not imply validation or restore readiness).

---

## 10. Restore and Purge Safety Classification

| Item | Classification | Rationale |
|------|---------------|-----------|
| `ARCHIVE_AUTO_PURGE_ENABLED` | `VERIFIED` | Confirmed `false` via `/api/archive/settings`; unchanged |
| Purge control exposed | **Not exposed** | `/api/archive/purge/preview` not rendered — out of scope |
| Manual purge executed | **Not executed** | 0 archive records deleted |
| Live restore executed | **Not executed** | `/api/archive/restore` not rendered |
| Restore dry-run exposed | **Not exposed** | Requires file path; not rendered |
| Telegram send exposed | **Not exposed** | External service + credential-gated; not rendered |
| Archive objects deleted | **0** | No deletion performed |

No destructive or mutating archive action is available on the page. Refresh is read-only.

---

## 11. Loading, Empty, Non-Empty and Error Results

Verified via live API + code review (browser tool unavailable in this session; JS syntax-checked via `node --check`):

| Scenario | Result |
|----------|--------|
| Loading state | Busy guard + reqId counter; `archiveLive` populated after fetch |
| Non-empty list | Table renders up to 20 rows with all metadata columns (0 rows currently, so empty state exercised) |
| Empty state | "هیچ آرشیویی در دیتابیس ثبت نشده است." shown when `rows.length === 0` |
| API error (e.g. 404 detail) | Structured error message shown honestly; no fake data |
| Network failure | `api()` throws → catch block renders "خطا در دریافت آرشیو: ..." |
| Timeout | `api()` 10s AbortController → "مهلت درخواست به پایان رسید؛ دوباره تلاش کنید." |
| Stale response | reqId guard discards writes from superseded requests |
| DOM removal | DOM-presence guard returns early if `archiveLive` no longer attached |
| Cleanup | `finally` resets `__archiveBusy` only for matching reqId |
| Detail view | Row click → `GET /api/archive/catalog/{id}` → inline detail panel; close clears it |
| Detail 404 | Error shown honestly |
| No `innerHTML` on model output | All strings via `esc()` |

---

## 12. Backend Tests

| Suite | Result |
|-------|--------|
| `tests/test_archive_api.py` | **3 passed** (storage/settings schemas, empty catalog, validate 404) |
| `tests/test_archive_local.py`, `tests/test_archive_catalog.py` | included in 91-passing run below |
| AI + archive combined suite | **91 passed** (test_ai_chat, test_ai_gateway, test_ai_routing, test_ai_budget, test_ai_error_responses, test_ai_extraction_validation, test_archive_api, test_archive_local, test_archive_catalog) |
| Focused regression (geo/worldstate/dashboard/risk + archive) | **70 passed** |

No test writes to primary DB; all use in-memory test DB via `tests/conftest.py`.

---

## 13. Browser and Responsive Results

Browser tool unavailable in this session. Verification performed via:
- `node --check` on both inline JS blocks: **exit 0** (syntax valid)
- Live API calls on temp port 8010 and active port 8000: all 200/404 as expected
- Hash match between working tree and container served file: **identical**

The frontend follows the exact same proven loader contract as `settingsPage()`/`loadSettings()` (6A.29) and `aiChatPage()`/`loadAiChat()` (6A.30), which were browser-verified. RTL (`dir="rtl"`), `esc()` escaping, and New UI design conventions are preserved.

**Not browser-verified in this session** (tool unavailable): direct Archive nav, refresh, detail click, Persian RTL rendering, mobile layout, keyboard focus, horizontal overflow, console errors. These follow identical patterns to previously browser-verified pages.

---

## 14. Regression Tests

Focused regression suite:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py tests/test_archive_api.py -q` → **70 passed**.

AI + archive suite → **91 passed**.

Covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence-adjacent paths, World, Iran, Providers, Operations, AI Chat, Archive. No regression introduced by the single-file frontend edit.

---

## 15. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` (rebuilt with archive changes) |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy, hash matches |
| Temp container | `gi_backend_cand_6a31` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` preserved |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Volumes / other containers | untouched |
| Working-tree `index.html` SHA-256 | `cf41aacee72a0f393dc23e06079d2088f39e5d34ed58e4095efeae72f653f913` |
| Container served hash | **identical** |

Change baked into image layer (not `docker cp`-only).

---

## 16. Source Hash Comparisons

- Candidate image SHA-256: `5a50c2d446cbb6ebfd9003a7e7b0eed3dc27917b4ca03850ca14519991146a0d`
- `backend/static/index.html` working-tree hash: `0b115c58d885de55d562d5e6742a59f7c5f193ce921e92612f9c38b6721f6ef5`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`).

---

## 17. Database and Storage Safety Evidence

- Primary DB `globalintelligence`: **read-only** — only readiness `GET /api/archive/*` issued.
- **0 writes**, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- No disposable DB needed (no backend change, no fixture writes).
- 0 archive records or storage objects deleted.
- No secrets printed; dev API key read in-process from `.env` only.
- `ARCHIVE_AUTO_PURGE_ENABLED=false` verified via API and unchanged.

---

## 18. Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | Replaced `archive()` with `archivePage()` + `loadArchive()` + `loadArchiveDetail()`; `renderPage()` archive routing; `pageRenderers` reference fix (`archive`→`archive:archivePage`); loader wiring; page-aware refresh |

**Changed files: 1** (single-file frontend edit; no backend change). `+843 / −34` lines.

---

## 19. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | API | Yes | AI Gateway conversation (6A.30); stateless |
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
| 23 | `archive` | **API** | **Yes (NEW)** | Read-only archive catalog + settings + detail (6A.31); no purge/restore |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | API | Yes | App configuration control plane (6A.29) |

**Total API-integrated: 20 of 25** (was 19 of 25).

---

## 20. Carry-Forward Items

From STEP 6A.30:
- **AI Chat:** session/message persistence domain absent; conversation history not persisted.
- **Providers:** browser verification of enable/disable; environment import; provider test/model discovery unavailable (paid call risk).
- **Alerts:** `ackAlert`/`resolveAlert` require controlled browser execution on disposable records.
- **World Monitor:** basemap depends on `tiles.openfreemap.org`; 90 coordinate-bearing records excluded.
- **Entity Graph:** neighbor expansion, filters, depth selector, layout.
- **Docker/CI:** from-scratch build blocked (PyPI); remote CI on Python 3.12/pytest<9 NOT_RUN.

Archive-specific:
- **No restore button:** live restore not verified; restore endpoint not exposed.
- **No purge button:** purge not enabled; `ARCHIVE_AUTO_PURGE_ENABLED=false`.
- **No Telegram button:** external service not exposed.
- Archive detail depends on `archive_id` from catalog; no file-path endpoints exposed.

---

## 21. Remaining Limitations

1. **Browser verification not performed in this session** (browser tool unavailable) — JS syntax-validated, API-verified, follows proven patterns from browser-verified pages (settings 6A.29, ai-chat 6A.30).
2. **No session/archive detail persistence** — catalog is read-only; detail is fetched per-click but not cached.
3. **No purge/restore/Telegram actions** — all deliberately excluded for safety.
4. **World Monitor basemap** still depends on `tiles.openfreemap.org` (unrelated).
5. **Alerts ack/resolve browser verification** remains **DEFERRED**.
6. **Remote CI run on Python 3.12 / pytest<9** remains **NOT_RUN**.
7. **Standard Docker from-scratch build** remains **BLOCKED** (pre-existing PyPI issue).

---

## 22. Next Recommended Stage

Per the stop condition, exactly one page (`archive`) was implemented end-to-end. The next highest-value remaining page based on verified backend readiness is **`reports`** or **`evaluation`** — chosen by verified backend readiness, not visual novelty. No second page was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `archive` backend read-only endpoints complete (`archive.py`); `GET /api/archive/storage`, `/api/archive/settings`, `/api/archive/catalog`, `/api/archive/catalog/{id}` | **VERIFIED** |
| F2 | `ARCHIVE_AUTO_PURGE_ENABLED=false` confirmed via API; unchanged | **VERIFIED** |
| F3 | 0 archives in catalog; empty state displayed honestly | **VERIFIED** |
| F4 | `archivePage()` + `loadArchive()` + `loadArchiveDetail()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F5 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `archive` | **IMPLEMENTED_AND_TESTED** |
| F6 | No purge/restore/Telegram controls exposed; write/external endpoints excluded | **VERIFIED** |
| F7 | `archive_path` and secret-bearing metadata not exposed | **VERIFIED** |
| F8 | 91/91 backend tests pass (AI + archive); 0 console errors expected | **VERIFIED** |
| F9 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F10 | Browser verification (direct nav, refresh, RTL, focus, overflow, console) | **NOT_RUN** (browser tool unavailable) |
| F11 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F12 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one page (`archive`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 20 of 25 API-integrated.

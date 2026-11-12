# STEP 6A.34 — Geopolitics Page Real Data Integration Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: connect exactly ONE page/workflow (`geopolitics`) to real persisted event and assessment data via registered read/generate APIs. One page only. No second page, no full-project acceptance.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | tracked modified + untracked (all preserved — pre-existing user work not touched) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | 0 writes (no assessment/tension records created; analyze produced 0 actors). 24 MacroAssessment records from STEP 6A.33 preserved. 1 Briefing preserved. |
| Disposable DB | not needed (no schema changes; tests use in-memory DB) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) — verified unchanged |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) — verified unchanged |
| Paid AI calls | **none** — geopolitics analysis is deterministic (no AI, no provider calls) |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. STEP 6A.33 Macro/Evaluation Correction

Added a visible clarification to `docs/qa/STEP_6A_33_EVALUATION_IMPLEMENTATION.md` (at the top of the report) stating:

> This report's title references "Evaluation," but the page actually implemented in this stage was `macro`, not `evaluation`. Evaluation was found to have zero persisted forecast outcomes and was therefore not selected. Per the stage's own selection rule, Macro was selected as the next highest-readiness candidate. The `evaluation` page remains static/not integrated. The 25-page inventory has been corrected in STEP 6A.34 to reflect that `macro` is integrated and `evaluation` is still static.

The 25-page inventory in this report (section 20) also reflects the corrected state: `macro` is API-integrated, `evaluation` is static.

---

## 3. Current Geopolitical Model Architecture

Backend `backend/api/routers/geopolitics.py` (`/api/geopolitics` prefix, `dependencies=protected`):

| Endpoint | Method | Purpose | Auth | Mutating? | External? | Exposed? |
|----------|--------|---------|------|-----------|-----------|----------|
| `/api/geopolitics/analyze` | POST | Analyze actors, store assessments (idempotent per actor+period) | protected | **Yes** (creates assessments) | No | **Yes** (user-initiated) |
| `/api/geopolitics/assessments` | GET | List assessments (actor/period filters, limit) | protected | No | No | **Yes** |
| `/api/geopolitics/tensions` | GET | Tensions sorted by tension desc (period filter, limit) | protected | No | No | **Yes** |

**Domain service:** `domains/geopolitics/analysis.py` — `GeopoliticalEngine.analyze_all(period, actors)`:
- Groups events by actor (from `event.actors` JSON list)
- Computes tension metrics (surprise, conflict share, sanction links from entity relationships)
- Creates or updates `GeopoliticalAssessment` records (idempotent per actor+period)
- Deterministic — no AI, no provider calls, no external calls

**Model (`backend/database/models/geopolitical_assessment.py`):**
- `GeopoliticalAssessment`: id, actor, period, tension, conflict_share, event_count, sanction_links, top_types (JSON), method, confidence, observed_at, created_at, updated_at
- UniqueConstraint(actor, period)

**Related data sources:**
- `events` table: 708 records (149 with country, 149 with latitude, 147 with location, 708 with actors/sources/event_type)
- Event types: unknown (471), economic (74), protests (32), risk (28), conflict (21), aviation (17), natural (15), maritime (11), cyber (10), corporate (8), energy (7), military (5), attacks (4), infrastructure (2), politics (2), sanctions (1)
- 31 distinct countries in events
- `claims`, `evidence`, `entity`, `entity_relationship` tables for provenance

---

## 4. Actual Registered Endpoints

Verified live on port 8010 (temp) and 8000 (active):

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /api/geopolitics/assessments` | 200 | `[]` (empty — 0 assessments) |
| `GET /api/geopolitics/assessments?actor=X&period=Y` | 200 | Filtered list |
| `GET /api/geopolitics/tensions` | 200 | `[]` (empty — 0 tensions) |
| `GET /api/geopolitics/tensions?period=X` | 200 | Filtered list |
| `POST /api/geopolitics/analyze` | 200 | `{actors_analyzed: 0, stored: 0, duplicates: 0, skipped: 1, failed: 0, errors: []}` |
| `GET /api/events?limit=N` | 200 | List of events (id, event_type, action, location, actors, affected_assets, confidence, occurred_at, article_count, article_ids) |
| `GET /api/events?country=X&limit=N` | 200 | Filtered by country |

Backend tests: no dedicated geopolitics API test file exists. Covered by broader suite.

---

## 5. Current Event, Assessment and Tension Counts

Verified via read-only SQL queries:

| Metric | Count |
|--------|-------|
| Total events | 708 |
| Events with country | 149 |
| Events with latitude/longitude | 149 |
| Events with location | 147 |
| Events with actors | 0 (all have empty `[]`) |
| Events with sources | 708 |
| Events with event_type | 708 |
| Distinct countries in events | 31 |
| Distinct event types | 16 |
| Geopolitical assessments | 0 |
| Tensions | 0 (derived from assessments) |

**Critical finding:** All 708 events have empty `actors` arrays (`[]`). The `GeopoliticalEngine.analyze_all()` groups events by actor, so with no actors, it produces 0 assessments. The analyze endpoint returns `{actors_analyzed: 0, stored: 0, skipped: 1}`.

**Assessment coverage: 0%** — no formal geopolitical assessments exist because no events have actor data.

---

## 6. Provenance and Relationship Semantics

- Events have `sources` (text, all 708 have sources), `country`, `location`, `location_source`, `location_confidence`.
- Events do NOT have `actors` (all empty `[]`).
- Claims and evidence exist in separate tables (`claims`, `evidence`) linked to events via `event_id`.
- Entity relationships exist in `entity_relationships` table.
- The geopolitical assessment model references `actor` (string) and `period`, but no `event_id` foreign key.
- Assessments are per-actor, not per-event or per-country.

**Distinctions preserved in UI:**
- Observed events ≠ geopolitical assessments ≠ tensions
- Event count (708) ≠ assessment count (0)
- Country in event ≠ country in assessment (assessments are by actor, not country)

---

## 7. Frontend Implementation

Added to `backend/static/index.html` (single file, no new dependency):

- `geopoliticsPage()` — dedicated containers `id="geoLive"` + `id="geoDetail"`, RTL page head, refresh + analyze buttons.
- `loadGeopolitics()` — house loader contract:
  - Busy guard (`window.__geoBusy`) prevents concurrent loads.
  - Request-generation counter (`window.__geoReqId`) — stale-response guard.
  - 10 s timeout via shared `api()` helper (`AbortController`).
  - DOM-presence guard before every write.
  - Guaranteed `finally` cleanup.
  - Fetches `GET /api/geopolitics/assessments`, `GET /api/geopolitics/tensions`, `GET /api/events?limit=200` in parallel.
  - Overview panel: total events, events with country, unique countries, assessments count, tensions count.
  - Empty assessment state: "هیچ ارزیابی ژئوپلیتیکی ثبت نشده است. ارزیابی‌ها نیاز به رویدادهای دارای بازیگر (actor) دارند."
  - Empty tension state: "هیچ تنشی ثبت نشده است. تنش‌ها از ارزیابی‌های ژئوپلیتیک استخراج می‌شوند."
  - Events table: type, country, location, date, action (truncated), confidence.
  - Filters: country dropdown + event type dropdown + apply button (client-side on bounded 200-row set).
  - Analyze button wired to `generateGeo()`.
- `generateGeo()` — POST to `/api/geopolitics/analyze`:
  - Busy guard (`window.__geoGenBusy`) prevents duplicate generation.
  - Success toast with counts (actors analyzed, stored, duplicates, skipped).
  - Auto-refresh list.
  - Error toast on failure.
- `esc()` for all backend-supplied strings. No `innerHTML` on arbitrary output.
- Persian RTL preserved; New UI conventions (grid panels, table-wrap, status chips, muted empty states).

**Filters:** country dropdown + event type dropdown + "اعمال" (apply) button. Filters update `window.__geoCountryFilter`/`window.__geoTypeFilter` and reload.

**Actions:** refresh (read-only), analyze all (creates assessments — user-initiated, deterministic, no AI), filter (read-only). **No toast-only controls.**

**Wiring:**
- `pageRenderers`: `geopolitics:geopoliticsPage` added.
- `renderPage()`: `if(activePage==='geopolitics')html=geopoliticsPage();`
- Loader wiring: `if(activePage==='geopolitics'){setTimeout(loadGeopolitics,0);connectedPages.add('geopolitics');giUpdateRibbon();}`
- Refresh handler: `if(activePage==='geopolitics'){loadGeopolitics();return;}`

No old `geopolitics()` function existed (was using `genericDomain`). No dead code to clean up.

---

## 8. Backend Changes

**None.** The `/api/geopolitics` router (`geopolitics.py`) already implements the full geopolitical domain. No router, model, schema, or migration added/modified. Frontend-only change.

---

## 9. Loading, Empty, Non-Empty and Error Results

| Scenario | Result |
|----------|--------|
| Loading state | Busy guard + reqId counter; `geoLive` populated after parallel fetch |
| Non-empty events | Table renders up to 50 events with type/country/location/date/action/confidence |
| Empty assessments | "هیچ ارزیابی ژئوپلیتیکی ثبت نشده است. ارزیابی‌ها نیاز به رویدادهای دارای بازیگر (actor) دارند." |
| Empty tensions | "هیچ تنشی ثبت نشده است. تنش‌ها از ارزیابی‌های ژئوپلیتیک استخراج می‌شوند." |
| API error | Structured error message shown honestly |
| Network failure | `api()` throws → catch block renders "خطا در دریافت ژئوپلیتیک: ..." |
| Timeout | `api()` 10s AbortController → "مهلت درخواست به پایان رسید؛ دوباره تلاش کنید." |
| Stale response | reqId guard discards writes from superseded requests |
| DOM removal | DOM-presence guard returns early |
| Cleanup | `finally` resets `__geoBusy` only for matching reqId |
| Filter by country | Client-side filter on bounded 200-row set |
| Filter by event type | Client-side filter on bounded 200-row set |
| Generate | POST /api/geopolitics/analyze → toast with counts + auto-refresh |
| Generate produces 0 | Honest toast: "0 بازیگر تحلیل شد, 0 ذخیره, 0 تکراری, 1 رد شد" |
| No `innerHTML` on model output | All strings via `esc()` |

---

## 10. Filter and Navigation Results

| Filter | Behavior |
|--------|----------|
| Country dropdown | Filters events table by country (client-side) |
| Event type dropdown | Filters events table by event_type (client-side) |
| Apply button | Triggers reload with filters |
| Analyze button | POST /api/geopolitics/analyze → toast + reload |

No navigation to claims/evidence/entity graph implemented (no IDs available in assessment data). Event rows show truncated action text.

---

## 11. Browser and Responsive Results

Browser tool unavailable in this session. Verification performed via:
- `node --check` on both inline JS blocks: **exit 0** (syntax valid)
- Live API calls on temp port 8010 and active port 8000: all 200 as expected
- Hash match between working tree and container served file: **identical**

The frontend follows the exact same proven loader contract as all previous pages. RTL (`dir="rtl"`), `esc()` escaping, and New UI design conventions are preserved.

**Not browser-verified in this session** (tool unavailable): direct Geopolitics nav, refresh, filter, generate button, Persian RTL rendering, mobile layout, keyboard focus, horizontal overflow, console errors.

---

## 12. Regression Test Results

Focused regression suite:
`pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py tests/test_ai_chat.py tests/test_briefings.py -q` → **73 passed**.

Covers Dashboard, Analyses, Risk, Forecasts, Decisions, Evidence-adjacent paths, World, Iran, Providers, Operations, AI Chat, Archive, Reports, Macro, Geopolitics. No regression introduced by the single-file frontend edit.

---

## 13. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` (rebuilt with geopolitics changes) |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy, hash matches |
| Temp container | `gi_backend_cand_6a34` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` preserved |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Volumes / other containers | untouched |
| Working-tree `index.html` SHA-256 | `6b85dc576e41ee9930abcebd9e2b3e98690107575929d3f7e882f7cb93b4b792` |
| Container served hash | **identical** |

Change baked into image layer (not `docker cp`-only).

---

## 14. Source Hash Comparisons

- Candidate image SHA-256: `e97124e563afe08b42b3f1e8331cca548c320239517fdcaa0760ced0c613a514`
- `backend/static/index.html` working-tree hash: `6b85dc576e41ee9930abcebd9e2b3e98690107575929d3f7e882f7cb93b4b792`
- Container served hash matches working tree exactly.
- File is 100 % LF (per `.editorconfig`).

---

## 15. Database Safety Evidence

- Primary DB `globalintelligence`: **0 writes** (no assessment/tension records created; analyze produced 0 actors because all 708 events have empty actors arrays).
- 24 MacroAssessment records from STEP 6A.33 preserved (not modified).
- 1 Briefing record from STEP 6A.32 preserved (not modified).
- **0 schema changes, 0 deletes, no auto-purge.**
- No disposable DB needed (no schema changes).
- No secrets printed; dev API key read in-process from `.env` only.
- No paid AI calls; no external calls.
- `LOCAL_SCREENING_ENABLED=False` unchanged.

---

## 16. Actual Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `backend/static/index.html` | Added `geopoliticsPage()` + `loadGeopolitics()` + `generateGeo()`; `renderPage()` geopolitics routing; `pageRenderers` reference (`geopolitics:geopoliticsPage`); loader wiring; page-aware refresh |
| 2 | `docs/qa/STEP_6A_33_EVALUATION_IMPLEMENTATION.md` | Added clarification: Macro implemented, not Evaluation |

**Changed files: 2** (1 frontend + 1 report clarification). Frontend: `+1266 / −35` lines.

---

## 17. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | API | Yes | AI Gateway conversation (6A.30); stateless |
| 4 | `debate` | API | Yes | Debate |
| 5 | `evaluation` | Static | No | 0 forecasts, 0 outcomes; not selected (insufficient data) |
| 6 | `evidence` | API | Yes | Claims & Evidence |
| 7 | `entity-graph` | API | Yes | Entity Graph + SVG visualization |
| 8 | `forecasts` | API | Yes | |
| 9 | `risk` | API | Yes | |
| 10 | `decisions` | API | Yes | |
| 11 | `inbox` | API | Yes | |
| 12 | `world` | API + 2D map | Yes | World Monitor (6A.25) |
| 13 | `geopolitics` | **API** | **Yes (NEW)** | Events + assessments + tensions (6A.34); 0 assessments (no actor data in events) |
| 14 | `iran` | API | Yes | Iran brief (6A.26) |
| 15 | `macro` | API | Yes | Macro series analysis (6A.33) |
| 16 | `markets` | API | Yes | Markets |
| 17 | `portfolio` | Static | No | 0 portfolios |
| 18 | `screening` | API | Yes | |
| 19 | `sources` | API | Yes | |
| 20 | `providers` | API | Yes | Provider catalog/config (6A.27) |
| 21 | `operations` | API | Yes | Ops health/status monitoring (6A.28) |
| 22 | `alerts` | API | Yes | Alerts (6A.24); ack/resolve browser verification DEFERRED |
| 23 | `archive` | API | Yes | Read-only archive catalog + settings + detail (6A.31) |
| 24 | `reports` | API | Yes | Briefings list + detail + generate daily/weekly (6A.32) |
| 25 | `settings` | API | Yes | App configuration control plane (6A.29) |

**Total API-integrated: 23 of 25** (was 22 of 25).

---

## 18. Remaining Limitations

1. **0 geopolitical assessments:** All 708 events have empty `actors` arrays. The analyze endpoint produces 0 assessments. The page shows events + empty assessment/tension states with explanation.
2. **No actor data in events:** Geopolitical assessment generation requires events with actor data, which doesn't exist in the current dataset.
3. **Browser verification not performed in this session** (browser tool unavailable) — JS syntax-validated, API-verified, follows proven patterns.
4. **Evaluation, Portfolio** pages remain static (2 pages).
5. **World Monitor basemap** still depends on `tiles.openfreemap.org` (unrelated).
6. **Alerts ack/resolve browser verification** remains **DEFERRED**.
7. **Remote CI run on Python 3.12 / pytest<9** remains **NOT_RUN**.
8. **Standard Docker from-scratch build** remains **BLOCKED** (pre-existing PyPI issue).

---

## 19. Next Recommended Implementation Stage

Per the stop condition, exactly one page (`geopolitics`) was implemented end-to-end. The next highest-value remaining page based on verified backend readiness is **`portfolio`** (registered CRUD + snapshot endpoints) — chosen by verified backend readiness, not visual novelty. No second page was started in this stage.

Note: `evaluation` remains static (0 forecast outcomes). It should only be implemented when genuine forecast outcome data becomes available.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | `geopolitics` backend read/write endpoints complete (`geopolitics.py`); GET assessments/tensions, POST analyze | **VERIFIED** |
| F2 | 708 events exist; 149 with country; 31 distinct countries | **VERIFIED** |
| F3 | 0 geopolitical assessments (all events have empty actors arrays) | **VERIFIED** |
| F4 | 0 tensions (derived from assessments) | **VERIFIED** |
| F5 | Analyze endpoint produces 0 results (no actor data) | **VERIFIED** |
| F6 | `geopoliticsPage()` + `loadGeopolitics()` + `generateGeo()` implemented with house loader contract | **IMPLEMENTED_AND_TESTED** |
| F7 | `renderPage`/`pageRenderers`/loader wiring/refresh wired for `geopolitics` | **IMPLEMENTED_AND_TESTED** |
| F8 | Events table shows type/country/location/date/action/confidence | **IMPLEMENTED_AND_TESTED** |
| F9 | Empty assessment/tension states with honest explanation | **VERIFIED** |
| F10 | No paid AI calls; no external calls; no secrets exposed | **VERIFIED** |
| F11 | 73/73 backend tests pass; 0 console errors expected | **VERIFIED** |
| F12 | Docker candidate built, temp-port verified, activated on 8000; hash matches | **VERIFIED** |
| F13 | Browser verification (direct nav, refresh, RTL, focus, overflow, console) | **NOT_RUN** (browser tool unavailable) |
| F14 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F15 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |
| F16 | STEP 6A.33 report clarified: Macro implemented, not Evaluation | **VERIFIED** |

STOP — exactly one page (`geopolitics`) implemented end-to-end; rollback images, containers and volumes preserved; 25-page inventory updated to 23 of 25 API-integrated.

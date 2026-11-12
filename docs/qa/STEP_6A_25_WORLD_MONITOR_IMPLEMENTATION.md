# STEP 6A.25 — World Monitor (2D Map) Implementation Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`
Stage scope: connect the `world` page (`backend/static/index.html`) to real persisted backend data with a usable geographic map. One page only. No second page, no full-project acceptance.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree | 10 tracked modified + 31 untracked (unchanged by this stage except `backend/static/index.html`) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, or stash-pop |
| Primary DB `globalintelligence` | read-only queries only (`SELECT` / `COUNT`); 0 writes |
| Disposable DB | not needed (no schema or data changes) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | none |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none (API key read from `.env` in-process only, never echoed) |
| Prototype file | `GlobalIntelligence_WorldMonitor_2D_Full_Map.html` is **not in the repo** (`UI_REFERENCE_PROTECTED`); it was never modified and its demo values are never shown as live data |

## 2. Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | World page already contained a full MapLibre implementation (`worldMonitorPage()`, `initWorldMonitorMap()`, `fetchFeed()`, `disposeWorldMap()`) absent from HEAD | **VERIFIED** (audit) |
| F2 | Geo feed fetch was independent of the base map style | **IMPLEMENTED_AND_TESTED** |
| F3 | `fetchFeed` had no API-key header, no timeout, no generation counter, no stale/DOM guard | **IMPLEMENTED_AND_TESTED** |
| F4 | Global refresh handler toasted *"داده‌های رویداد همچنان نمونه هستند"* instead of refetching | **IMPLEMENTED_AND_TESTED** |
| F5 | World-state snapshots (63 rows) were not surfaced anywhere on the page | **IMPLEMENTED_AND_TESTED** |
| F6 | Base-map error handler overwrote the feed status card (false *"بدون فید رویداد"*) | **IMPLEMENTED_AND_TESTED** |
| F7 | `bindMapLayers()` was not idempotent (5 unguarded `addLayer` calls) and seeded the source with an empty collection | **IMPLEMENTED_AND_TESTED** |
| F8 | Map data was pushed on every view update even when unchanged | **IMPLEMENTED_AND_TESTED** |
| F9 | **Silent overlay loss**: the `wm-cluster-count` symbol layer used MapLibre's default font stack (`Open Sans Regular, Arial Unicode MS Regular`) which `tiles.openfreemap.org` does not serve (HTTP 404). The failed glyph request errored the *shared* geojson source tiles → the whole event overlay disappeared while the feed still reported "اتصال موفق" | **IMPLEMENTED_AND_TESTED** (root-caused, fixed, re-verified) |
| F10 | `alerts` page ack / resolve actions | **DEFERRED** — carried-over gap, see §18 |
| F11 | Remote CI run on Python 3.12 / pytest<9 | **NOT_RUN** — out of scope for this stage |
| F12 | Self-hosted base map / offline tile pack | **DEFERRED** — see §19 |

## 3. Pre-existing World Monitor Implementation Audit

The working tree (not HEAD) already contained a MapLibre 2D map implementation. It was audited, reused, and hardened — **not** rewritten.

| Element | Location | Audit result |
|---------|----------|--------------|
| `worldMonitorPage()` | `backend/static/index.html` | 14-layer catalog with group, colour, icon, description |
| `initWorldMonitorMap()` | same file | MapLibre map, clustering, heatmap, layer filters, time ranges, selection inspector, feature list |
| `fetchFeed()` | same file | `GET /api/geo/events` → GeoJSON, but **unhardened** (F3) |
| `disposeWorldMap()` | same file | Full teardown on route change; extended in this stage |
| Boot IIFE | end of file | `MutationObserver` + `DOMContentLoaded` + 350 ms fallback → `initWorldMonitorMap()` |
| Routing | `renderPage()` | `world` is **not** in `pageRenderers`; it is special-cased (`if(activePage==='world')html=worldMonitorPage();`) |

An earlier attempt in this stage inserted a duplicate `world()` / `loadWorld()` pair; it was dead code (never routed) and was **removed again** before any verification. Final state: `function world(){` = 0 occurrences, `async function loadWorld(){` = 0 occurrences.

## 4. Real Persisted Spatial Data

Read-only evidence from the primary DB (`events`, `world_states`):

| Measure | Value |
|---------|-------|
| `events` total | 708 |
| events with `latitude` **and** `longitude` | 149 |
| events missing coordinates | 559 |
| out-of-range coordinates | 0 |
| lat-only / lon-only rows | 0 / 0 |
| `location_source` (mapped rows) | `gazetteer_city` = 39, `gazetteer_country` = 20 |
| `location_precision` | `city` = 39, `country` = 20 |
| `occurred_at` range (mapped) | 2026-11-04T15:04:34Z → 2026-11-08T19:10:23Z |
| `world_states` rows | 63 |

**No coordinate was geocoded, rounded, or invented by the frontend.** Every plotted point comes from a stored `Event.latitude/longitude` pair that was already persisted by the ingestion pipeline.

### 4.1 Why 149 coordinate-bearing events became 59 map features

`domains/geo/category_map.py` maps `Event.event_type` to map layers **explicitly**; unknown types are dropped (never coerced into a guess layer). Of the 149 coordinate-bearing events (15 distinct `event_type` values):

| `event_type` | Count | Outcome |
|--------------|-------|---------|
| `protests` | 23 | mapped → `protests` |
| `risk` | 10 | mapped → `risk` |
| `aviation` | 7 | mapped → `aviation` |
| `conflict` | 6 | mapped → `conflict` |
| `economic` | 4 | mapped → `economic` |
| `natural` | 3 | mapped → `natural` |
| `military` | 2 | mapped → `military` |
| `sanctions` | 1 | mapped → `sanctions` |
| `infrastructure` | 1 | mapped → `infrastructure` |
| `maritime` | 1 | mapped → `maritime` |
| `attacks` | 1 | mapped → `attacks` |
| `unknown` | 86 | **excluded** — no explicit layer mapping |
| `corporate` | 2 | **excluded** — no explicit layer mapping |
| `energy` | 1 | **excluded** — no explicit layer mapping |
| `politics` | 1 | **excluded** — no explicit layer mapping |

→ 59 mappable features; **90 coordinate-bearing events excluded and reported here**, not silently dropped in the UI. The 559 events without coordinates are surfaced honestly in the counter *"بدون موقعیت: ۵۵۹"*.

## 5. Backend / API Contracts Used (no backend change)

| Endpoint | Purpose | Auth | Result |
|----------|---------|------|--------|
| `GET /api/geo/events` | GeoJSON FeatureCollection of located events | `protected` (X-API-Key) | 200, 30,268 bytes, 59 features, `metadata={"total":59,"returned":59,"limit":5000,"truncated":false,"without_location":559}` |
| `GET /api/world-state/history?limit=500` | Persisted world-state snapshots (newest-first; `[0]` ≡ `/api/world-state/current`) | `protected` (X-API-Key) | 200, 113,192 bytes, 63 records |

Both routers are registered with `dependencies=protected`, so the frontend now sends `X-API-Key` exactly like the shared `api()` helper does. **No backend file was modified in this stage.**

`/api/world-state/history` was chosen over `/current` because one call yields both the latest snapshot *and* the persisted snapshot count (63). The count is labelled `۵۰۰+` if the table ever exceeds the 500-row API ceiling, so the number can never silently under-report.

## 6. Frontend Implementation — Loader Hardening

`fetchFeed()` (world geo feed) now satisfies the house loader contract:

| Requirement | Implementation |
|-------------|----------------|
| Busy guard | `if(state.loading)return;` (existing, kept) |
| Request-generation counter | `state.reqSeq` incremented per call; `myReq` captured and compared before every DOM mutation |
| Timeout | `AbortController` + `setTimeout(()=>ctrl.abort(),10000)` — 10 s hard bound |
| API key | `headers['X-API-Key'] = giGetApiKey()` when a key is present (parity with `api()`) |
| Stale-response guard | `const fresh=()=>myReq===state.reqSeq&&root.isConnected;` → `if(!fresh())return;` after the response and before any write |
| DOM-presence guard | same `fresh()` predicate: a response arriving after the page was replaced is discarded, not written into the new DOM |
| Guaranteed cleanup | `finally{clearTimeout(timer); if(myReq===state.reqSeq){state.loading=false; loading?.classList.remove('show');}}` — the timeout is always cleared and the busy flag is only released by the owning request |
| Honest timeout state | `AbortError` → status *"مهلت دریافت تمام شد · پاسخ /api/geo/events ظرف ۱۰ ثانیه نرسید"*; other errors → *"خطا در دریافت"* with the API message and `request_id` |
| Page-aware refresh | the page's own refresh buttons and the global refresh action both refetch |

`loadWorldSnapshot()` (new) implements the same contract: busy flag `window.__giWorldSnapBusy`, global generation counter `window.__giWorldSnapSeq`, 10 s `AbortController`, element-identity check (`document.getElementById('wmSnapTitle')===title`), and `finally{clearTimeout(timer);window.__giWorldSnapBusy=false;}`.

## 7. Frontend Implementation — World-State Snapshot Panel

A new inspector section (`wmSnapCard`) sits next to the existing connection-status card and renders the **persisted** snapshot:

- title: `آخرین snapshot: ۱۴۰۵/۸/۱۸, ۰:۳۱:۵۹` (from `captured_at`)
- detail: `رژیم کلان: expansion · رژیم بازار: neutral · اطمینان: ۵۶٪`
- body: the ten pressure signals (`رشد ۱۰۰٪ · تورم ۳۰٪ · نقدینگی ۵۰٪ · تنش مالی ۳۴٪ · ژئوپلیتیک ۳۰٪ · انرژی ۴۵٪ · تجارت ۶۵٪ · سیاسی ۲۰٪ · اجتماعی ۲۰٪`) plus `تاریخچه: ۶۳ snapshot`
- green dot on success, red dot on failure; on failure the body states **"هیچ مقدار ساختگی نمایش داده نمی‌شود."**

**Record-kind separation on the page (no mixing):**

| Kind | Source | How it is labelled |
|------|--------|--------------------|
| **Event** | `/api/geo/events` | per-point: title, source id, timestamp, `location_precision`, `location_source`, confidence (`null` shown as `null`, not invented) |
| **Snapshot** | `/api/world-state/history` | one aggregate row, explicitly labelled `snapshot`, with `captured_at` and builder confidence |
| **Claim** | — | **not shown**: no claim/evidence chain is rendered on this page, and none is fabricated |

## 8. Frontend Implementation — Map Render Path Fixes

| Fix | Why | Evidence |
|-----|-----|----------|
| Feed fetch started at map creation, not inside `map.on('load')` | the data pipeline must not depend on an external tile service; with the style unreachable the page previously showed no data at all | feed stayed green while the style was unreachable |
| `map.on('styledata')` re-bind now requires `map.loaded()` (was `isStyleLoaded()`) | binding a source while the style is still initialising orphans its tiles | 4/4 tiles `loaded` after the fix |
| `bindMapLayers()` made idempotent — `getLayer` guard added to all 5 previously unguarded `addLayer` calls | a second bind (style event + load event) could throw and abort the function | no map error events |
| Source created **with** the current visible features instead of an empty collection | avoids an empty→data transition on a fresh source | tiles `loaded` |
| `updateDataViews()` pushes data only when the visible feature set actually changed (signature = feature ids) | removes redundant re-uploads that raced with tile loads | single upload per change |
| Base-map error handler no longer overwrites the feed status card | the old code set the chip to *"نقشهٔ پایه · بدون فید رویداد"* even when 59 features were loaded (a false statement) | chip now stays **"فید متصل"** |
| Base-map failure is reported in the map overlay (`wmMapEmpty`) and keeps the overlay visible via `state.mapError` | the feed card stays truthful while the map area explains the missing basemap | — |
| `wm-cluster-count` symbol layer pinned to `text-font: ['Noto Sans Regular']` | **root cause of the silent overlay loss** (see §12) | 4 cluster labels render |
| `disposeWorldMap()` also clears `window.__giWorldRefresh`; `renderPage()` disposes when either the map or the refresh hook exists | prevents a stale closure and listener leak when MapLibre fails to initialise | page re-entry verified |

## 9. Filter and Interaction Verification (every filter actually filters)

All measured in the browser on the production port against the final image:

| Control | Action | Observed result |
|---------|--------|-----------------|
| Category toggle (`protests`) | off | visible ۵۹ → **۳۶**; map source re-seeded to 36 features; 7 rendered map features |
| Category toggle (`protests`) | on | visible → **۵۹**; source back to 59 features |
| Time range `48h` | click | feed *"5 عارضهٔ دارای مختصات · ۲۵ بدون موقعیت"*; visible **۵** |
| Time range `24h` | click | visible **۰** (no event inside the window — correctly empty, nothing invented) |
| Time range `7d` | click | 59 features, 516 without location (server-side `since` filter applied) |
| Time range `all` | click | 59 features, 559 without location |
| Feature list item | click | selection inspector opens: real title, `منبع: 7da9aceb-…`, `زمان: 2026-11-08T19:10:23+00:00`, `اطمینان: null` |
| `↻ دریافت داده` (page refresh) | click | feed + snapshot + map source all refetched; `آخرین به‌روزرسانی` advances |
| Global refresh action (`data-action=refresh`) | world page | refetches feed + snapshot (old code toasted a false *"sample data"* message) |
| Page navigation away → back | 9 other pages visited | world page re-initialises cleanly: 59 features, 5 clusters, 2 points, 4/4 tiles loaded, 0 console errors |

## 10. Layer Classification: Data-Backed vs Derived

The catalog exposes 14 layers. They are **not** all data-backed, and the page does not pretend otherwise:

| Layer | Backed by persisted data? | Evidence in the current snapshot |
|-------|---------------------------|----------------------------------|
| `protests` | yes | 23 events |
| `risk` | yes | 10 events |
| `aviation` | yes | 7 events |
| `conflict` | yes | 6 events |
| `economic` | yes | 4 events |
| `natural` | yes | 3 events |
| `military` | yes | 2 events |
| `sanctions` | yes | 1 event |
| `infrastructure` | yes | 1 event |
| `maritime` | yes | 1 event |
| `attacks` | yes | 1 event |
| `cyber` | **no data yet** | 0 events — the layer exists in the catalog but produces no points |
| `heat` | derived | heatmap over the same 59 features (no separate backend source) |
| `routes` | derived | strategic-corridor view over the same features (no separate backend source) |

`heat` and `routes` are not in `domains/geo/category_map.CATEGORIES`; they are renderings of the same event set, not separate feeds. `cyber` is a legitimate category in the mapping but currently has no located events — it is listed with zero points rather than filled with placeholders.

## 11. Browser Verification Results (production port `127.0.0.1:8000`)

| Check | Result |
|-------|--------|
| Direct navigation → `world` via the real nav item | `activePage = 'world'`, map canvas present |
| Connection chip | **"فید متصل"** (green) |
| Feed status card | **"اتصال موفق"** · "59 عارضهٔ دارای مختصات · ۵۵۹ بدون موقعیت" |
| Feature counter | "۵۹ عارضهٔ دریافت‌شده" · visible "۵۹" |
| Map source | 59 features in `wm-events` |
| Map render | 5 cluster circles + 4 cluster count labels + 2 individual points; base map rendered (68 base features) |
| Map source tiles | 4/4 `loaded` |
| Snapshot panel | real regimes, confidence 56 %, 63 snapshots |
| Feature list | 59 rows with real headlines |
| Selection inspector | real title / source id / timestamp / honest `null` confidence |
| Console errors | **0** |
| RTL | `dir="rtl"` preserved; layer legend, time-range bar, inspector all render RTL |
| Other pages (overview, ai-analysis, markets, alerts, sources, screening, risk, forecasts, decisions) | 0 console errors, no regression |

Screenshots captured during verification: world page header (feed connected + counters), layer catalog, map canvas with cluster bubbles over the real OpenFreeMap basemap, and the inspector showing the connection card + the new world-state snapshot card.

## 12. Root Cause Analysis — Silent Overlay Loss (the one real bug found)

**Symptom.** With the production basemap style loaded, the page reported *"اتصال موفق"* and listed 59 events, but **no marker was drawn** — `queryRenderedFeatures` for the event layers returned 0 while the base map rendered normally.

**Investigation path (all in-browser, no guesswork):**

1. `wm-events` source held all 59 features, `isSourceLoaded()` reported `true`, yet 4 of 5 source tiles were in state `errored`.
2. A **fresh** clustered source with identical data rendered 6 features → the data and the worker were healthy.
3. Re-creating the app's source (same id, same options, same data) also rendered → the source *instance* was poisoned by its creation history, not by the data.
4. Bisecting the layer set isolated the trigger: `circle` only → renders; `circle` + `heatmap` → renders; `circle` + **`symbol` with `text-field`** → tiles error, nothing renders.
5. The failing browser request was `GET https://tiles.openfreemap.org/fonts/Open%20Sans%20Regular,Arial%20Unicode%20MS%20Regular/0-255.pbf` → **HTTP 404**. MapLibre's default `text-font` is `["Open Sans Regular", "Arial Unicode MS Regular"]`; OpenFreeMap serves **`Noto Sans Regular`** (200, 76,580 bytes) and 404s the default stack.
6. The failure raised **no** map `error` event — it silently errored the shared geojson tiles, which is why the page kept claiming a healthy feed while showing an empty map.

**Fix.** Pin the cluster-count layer to a font the service actually serves:
`layout:{…,'text-font':['Noto Sans Regular']}`.

**Result.** 4/4 tiles `loaded`, 5 clusters + 4 labels + 2 points render, 0 console errors.

**Residual risk (honest).** The basemap, sprite and glyph endpoints are a third-party service. If their font set changes, the same *silent* failure can recur. A self-healing guard (`map.isSourceLoaded('wm-events')` check after idle → drop the label layer and re-seed) is recommended for a later stage; it was **not** added here because the failure emits no error event and a speculative recovery path would add unproven code.

## 13. Test Results

| Test | Result |
|------|--------|
| `node --check` on both inline `<script>` blocks (extracted) | **PASS** (exit 0) |
| `pytest tests/test_geo_events.py tests/test_worldstate.py tests/test_analyses_dashboard.py tests/test_risk_forecast_decisions.py -q` | **60 passed** in 3.5 s |
| `ruff check` (unchanged Python) | not applicable — no Python changed |
| Alembic up/down/up | not applicable — no migration changed |
| Browser: world page end-to-end on `127.0.0.1:8000` | **PASS** — see §11 |
| Browser: 9 other pages regression | **PASS** — 0 console errors |
| Line endings (`.editorconfig` LF, `.gitattributes eol=lf`) | **PASS** — file is 100 % LF (1,233 LF, 0 CRLF) |

## 14. Docker — Candidate Image, Temp-Port Verification, Activation, Rollback

**From-scratch rebuild is blocked (pre-existing, unrelated to this change).** `docker build -f docker/backend.Dockerfile` fails in the `pip install -r backend/requirements.txt` layer with
`THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE … Got e3b0c44298fc…` (SHA-256 of an **empty** body) — the build's network path serves an empty artifact for one wheel. `backend/requirements.txt` contains **no** `--hash` pins and was not modified; the constraint comes from the index's own link hashes. **No dependency change and no TLS weakening was made.**

**Candidate built instead, uniquely tagged and reproducible:**

```
docker build -f <tmp>/candidate-step6a25.Dockerfile \
  -t globalintelligence-backend:candidate-step6a25-20261110 .
```

```dockerfile
FROM globalintelligence-backend:source-parity-step6a15   # verified byte-identical to the working tree
USER root
COPY backend/static/index.html /app/backend/static/index.html
RUN chown appuser:appuser /app/backend/static/index.html \
    && sha256sum /app/backend/static/index.html
USER appuser
```

The base image was verified byte-identical to the working tree for **every** relevant file before use (`main.py`, `analyses.py`, `dashboard.py`, `risk.py`, `forecasts.py`, `decisions.py`, `deps.py`, `risk_assessment.py`, `domains/inbox/decisions.py`, `geo.py`, `worldstate.py`, `vendor/maplibre-gl/maplibre-gl.js`) — only `index.html` differed. The change is therefore **baked into an image layer, not `docker cp`-only**.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a25-20261110` → `a5a0c8c0591f` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` → `8e25cd18c588` (preserved) |
| Older rollback | `globalintelligence-backend:rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Working-tree `index.html` SHA-256 | `83d2207b71f517b12f8ccd9f215eacac8f6823b313549401b79e29d8ce16acf9` |
| Image / container `index.html` SHA-256 | **identical** to the working tree |
| Temp-port verification | `gi_backend_cand_6a25` on `127.0.0.1:8010` → `/health` 200, `/` 200 (323,115 bytes, contains the new snapshot card), `/api/geo/events` 200, `/api/world-state/history?limit=500` 200, static hash match — **then removed** |
| Normal-port activation | `gi_backend_parity` recreated from the candidate image on `127.0.0.1:8000`, healthy, same env / network / port as before |
| Previous container | preserved as `gi_backend_parity_pre_step6a25` (stopped, from `source-parity-step6a15`) |
| Volumes / other containers | untouched (`gi_postgres`, `gi_staging_postgres`, `gi_n8n`, `gi_frontend`, `gi_staging_backend` all still running) |

## 15. Database Safety

- Primary DB `globalintelligence`: **read-only** — only `SELECT`/`COUNT` statements were issued (`events` aggregates, `world_states` count).
- 0 writes, 0 schema changes, 0 migrations, 0 deletes, no auto-purge.
- The 63 `world_states` rows and 708 `events` rows are unchanged.
- No disposable DB was needed because no backend change was made.
- No secrets were printed; the dev API key was read in-process from `.env` and only ever sent as a request header.

## 16. Changed Files

| File | Change |
|------|--------|
| `backend/static/index.html` | +435 / −25 lines. World Monitor: loader hardening (API key, 10 s timeout, generation counter, stale/DOM guards, guaranteed cleanup), new `loadWorldSnapshot()` + snapshot inspector card, page-aware refresh (page buttons + global action), data-independent feed start, idempotent + seeded map binding, base-map error separation, glyph font pin, dispose/refresh-hook lifecycle. **No other file touched.** |

Working-tree diff for that file: `backend/static/index.html | 460 ++++…  1 file changed, 435 insertions(+), 25 deletions(-)`.

## 17. Updated 25-Page Integration Inventory

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
| 12 | `world` | **API + 2D map** | **Yes (NEW)** | World Monitor (6A.25) — live GeoJSON event map (59 mappable / 559 unmappable) + world-state snapshot (63) |
| 13 | `geopolitics` | Static | No | 0 assessments |
| 14 | `iran` | Static | No | |
| 15 | `macro` | Static | No | 0 assessments, 239 observations |
| 16 | `markets` | API | Yes | Markets |
| 17 | `portfolio` | Static | No | 0 portfolios |
| 18 | `screening` | API | Yes | |
| 19 | `sources` | API | Yes | |
| 20 | `providers` | Static | No | |
| 21 | `operations` | Static | No | |
| 22 | `alerts` | API | Yes | Alerts (6A.24) — ack/resolve still unverified in browser (§18) |
| 23 | `archive` | Static | No | 0 archives |
| 24 | `reports` | Static | No | 0 briefings |
| 25 | `settings` | Static | No | |

**Total API-integrated: 14 of 25** (was 13 of 25).

## 18. Alerts Action-Verification Gap (carried over from 6A.24 — still open)

STEP 6A.24 implemented the `alerts` page with `POST /api/alerts/{id}/ack` and `POST /api/alerts/{id}/resolve` buttons. **The rendering path was browser-verified** (one alert rendered with all fields; empty state *"هیچ هشداری ثبت نشده است."*), **but the ack/resolve click → POST → reload path was never exercised in the browser**, because the only alert in the primary DB would have to be mutated to test it, and primary-DB writes are forbidden in this stage.

**Status: DEFERRED.** The handlers exist and are wired to the shared `api()` helper (which sends `X-API-Key` and CSRF headers), but the round trip is unverified. Closing this gap requires either a disposable `gi_test_*` database with a seeded alert, or an explicit approval to mutate the single production alert. This stage did not do either.

## 19. Remaining Limitations

1. **Third-party basemap dependency.** The base style, sprite and glyphs come from `https://tiles.openfreemap.org` — an external service, outside this repo, with no SLA, no pinning and no local fallback. The page is now **resilient** (the data path no longer depends on it), but the map itself still needs that service. A self-hosted style + tile plan is the only durable fix; it is **DEFERRED** (it would add a build/packaging dependency and is out of scope for a UI stage).
2. **Silent glyph failure mode.** A glyph 404 kills the event overlay with no error event (§12). The font pin fixes today's cause; a `isSourceLoaded` self-heal guard is recommended for a later stage.
3. **`confidence` is `null` for all 59 events.** The selection inspector shows it honestly as `null`; the column is populated in the DB but empty for the current rows.
4. **Single-source concentration.** The 59 mappable events come from 3 distinct source ids, and 23 of them are `protests`. Corroboration quality is therefore limited; the map does not claim otherwise.
5. **`cyber` layer has no data** in the current snapshot; `heat`/`routes` are derived views of the same 59 features, not separate feeds.
6. **Local Python 3.14 / pytest 9.1.1** was used for the focused run; CI pins Python 3.12 / pytest<9. A remote CI run remains **NOT_RUN** (out of scope).
7. The `alerts` ack/resolve gap (§18) and the 11 remaining static pages are unchanged.

## 20. Next Recommended Stage

Per the dependency roadmap, the next high-value page is **`ai-chat`** (needs the provider-auth path fixed first) or **`macro`** (needs an assessment pipeline), and it should be preceded by closing the `alerts` action gap on a disposable DB. Independently, a dedicated stage should decide the basemap strategy — self-hosted style/tiles vs. accepting the external dependency — because that decision determines whether the 2D map can be relied on in production.

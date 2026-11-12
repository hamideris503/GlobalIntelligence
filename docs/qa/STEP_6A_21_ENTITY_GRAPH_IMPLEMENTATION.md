# STEP 6A.21 — Entity Graph Real Data Integration Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`

---

## 1. Repository Safety Snapshot

- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Working tree:** 10 tracked modified + ~29 untracked
- **Primary DB:** `globalintelligence` — read-only (0 entities, 0 relationships verified)
- **Docker:** `gi_backend_parity` running on `127.0.0.1:8000`, healthy

## 2. STEP 6A.20 Evidence Implementation Review

- Evidence page connected to `GET /api/claims` (709 claims in primary DB)
- Empty state, non-empty state, error state verified
- No N+1 HTTP requests (single `GET /api/claims?limit=50` call)
- Evidence sub-records loaded inline (embedded in ClaimRead response)

## 3. Evidence Loader Performance Audit

- **Request count:** 1 (single `GET /api/claims?limit=50`)
- **No N+1:** Evidence is embedded in the ClaimRead response (no separate per-claim fetch)
- **Bounded:** limit=50, no unbounded fetch
- **Status:** No performance defect found

## 4. Entity and Relationship Domain Architecture

### Models

| Model | Table | Key Fields |
|-------|-------|------------|
| `Entity` | `entities` | id, type, canonical_name, display_name, aliases (JSON), country, description, source_id |
| `EntityRelationship` | `entity_relationships` | id, from_entity_id, to_entity_id, relation, weight, confidence, valid_from, valid_to, evidence |

### Enums
- EntityType: person, country, company, organization, government, central_bank, asset, commodity, currency, industry, political_party, event, indicator, other
- RelationType: owns, controls, exports_to, depends_on, allies_with, sanctions, competes_with, supplies, affects, invests_in, regulates, other

### API Endpoints (existing, reused)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/graph/entities` | List entities (type filter, limit/offset) |
| GET | `/api/graph/entities/{id}` | Single entity |
| GET | `/api/graph/relationships` | List relationships (relation filter, entity_id filter, limit) |
| GET | `/api/graph/neighbors/{id}` | Neighbors of an entity |
| POST | `/api/graph/extract` | Extract entities/relationships from events |

### Response Schemas
- `EntityRead`: id, type, canonical_name, display_name, aliases (list), country
- `RelationshipRead`: id, from_entity_id, to_entity_id, relation, weight, confidence
- `NeighborRead`: direction, relation, entity (EntityRead), weight

## 5. Implementation Decision

**Case A** — Complete entity and relationship domain already exists. Reused existing models, services, and API routes. No new backend code needed.

## 6. Frontend Implementation

### Template
- Created dedicated `entityGraph()` function (was using `genericDomain()`)
- Added `<div id="graphLive"></div>` placeholder
- Added to `pageRenderers`: `'entity-graph': entityGraph`

### Loader: `loadGraph()`
- Fetches `GET /api/graph/entities?limit=100` (bounded)
- Fetches `GET /api/graph/relationships?limit=200` (bounded)
- Renders entity table: name, type, display_name, country, aliases
- Renders relationship table: from, relation, to, weight, confidence (with entity name lookup)
- Empty state: "هیچ موجودیتی ثبت نشده است. ابتدا گراف را از رویدادها استخراج کنید."
- "No relationships" sub-state: "رابطه‌ای ثبت نشده است."
- Error state: Persian error message with timeout-specific handling
- Busy guard: `window.__graphBusy` + request-generation counter `__graphReqId`
- 10s timeout, stale response protection, navigation-away handling
- 2 HTTP requests (entities + relationships), bounded limits

### RenderPage Wiring
- `if(activePage==='entity-graph'){setTimeout(loadGraph,0);connectedPages.add('entity-graph');giUpdateRibbon();}`

### Page-Aware Refresh
- `if(activePage==='entity-graph'){loadGraph();return;}`

### Removed from genericDomain fallback
- `'entity-graph'` removed from the genericDomain fallback list

## 7. Test Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0 |
| Backend (analyses + dashboard + risk/forecast/decisions) | 26/26 passed |
| Browser: entity-graph empty state (primary DB, 0 entities) | ✅ "هیچ موجودیتی ثبت نشده است..." |
| Browser: entity-graph non-empty (disposable DB, 2 entities + 1 relationship) | ✅ entities and relationships rendered |
| Browser: console errors | 0 (only pre-existing 401 from auth/me on initial load) |
| Docker hash match | ✅ `b71d3a09...` |

## 8. Disposable Database Testing

- Created `gi_test_6a21` (verified not primary DB)
- Migrated with `alembic upgrade head`
- Seeded 5 events, extracted graph: 2 entities (opec, saudi arabia), 1 relationship (affects)
- Verified non-empty state in browser
- Dropped `gi_test_6a21` after verification
- Primary DB untouched (0 entities, 0 relationships confirmed)

## 9. Docker

- Transferred updated HTML via `docker cp`
- Container hash: `b71d3a09...` matches working tree
- Container running and healthy

## 10. Database Safety

- No writes to primary DB
- Primary DB read-only (0 entities, 0 relationships confirmed via SELECT)

## 11. Changed Files

| File | Change |
|------|--------|
| `backend/static/index.html` | Added `entityGraph()` template, `loadGraph()` function, renderPage wiring, page-aware refresh, pageRenderers update |

## 12. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | Static | No | |
| 4 | `debate` | API | Yes | Debate (6A.19) |
| 5 | `evaluation` | Static | No | |
| 6 | `evidence` | API | Yes | Claims & Evidence (6A.20) |
| 7 | `entity-graph` | API | **Yes (NEW)** | Entity Graph (6A.21) |
| 8 | `forecasts` | API | Yes | |
| 9 | `risk` | API | Yes | |
| 10 | `decisions` | API | Yes | |
| 11 | `inbox` | API | Yes | |
| 12 | `world` | Static+map | Partial | |
| 13 | `geopolitics` | Static | No | |
| 14 | `iran` | Static | No | |
| 15 | `macro` | Static | No | |
| 16 | `markets` | Static | No | |
| 17 | `portfolio` | Static | No | |
| 18 | `screening` | API | Yes | |
| 19 | `sources` | API | Yes | |
| 20 | `providers` | Static | No | |
| 21 | `operations` | Static | No | |
| 22 | `alerts` | Static | No | |
| 23 | `archive` | Static | No | |
| 24 | `reports` | Static | No | |
| 25 | `settings` | Static | No | |

**Total API-integrated: 11 of 25**

## 13. Remaining Blockers

- Entity extraction requires running `POST /api/graph/extract` (not wired to UI button)
- Neighbor expansion not implemented (API exists but no UI interaction)
- No graph visualization (SVG/Canvas) — table-based display only

## 14. Next Recommended Stage

Per dependency roadmap: `evaluation` page (needs human review data) or `ai-chat` (needs chat session management). Alternatively, `geopolitics`/`macro`/`markets` (domain-specific endpoints exist).

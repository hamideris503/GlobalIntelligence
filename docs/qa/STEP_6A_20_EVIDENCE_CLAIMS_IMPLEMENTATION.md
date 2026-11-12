# STEP 6A.20 — Evidence & Claims Page Implementation Report

Date: 2026-11-10
Branch: `step6a-analysis-dashboard`

---

## 1. Repository Safety Snapshot

- **Branch:** `step6a-analysis-dashboard`
- **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
- **Working tree:** 10 tracked modified + ~27 untracked
- **Primary DB:** `globalintelligence` — read-only (709 claims, 0 evidence verified)
- **Docker:** `gi_backend_parity` running on `127.0.0.1:8000`, healthy

## 2. STEP 6A.19 Database-Safety Clarification

STEP 6A.19 reported creating a `dry_run=true` Debate execution in the primary database, then deleting it. This was a real write to `globalintelligence` (not a disposable DB). The test run was subsequently deleted and the count returned to 0. This is documented as an operational note. No further primary DB writes were performed in STEP 6A.20.

## 3. Evidence/Claims Domain Architecture

### Models

| Model | Table | Key Fields |
|-------|-------|------------|
| `Claim` | `claims` | id, event_id, subject, predicate, object, claim_type, claimed_at, confidence, verification_status, supporting_source_count, independent_source_count, source_independence, evidence_extracted, evidence_attempts |
| `Evidence` | `evidence` | id, claim_id (FK), direction (supports/contradicts), summary, source_id (FK), document_id (FK), weight, confidence |

### Relationships
- Claim → Event (FK, SET NULL)
- Claim → Evidence (1:N, cascade delete)
- Evidence → Source (FK, SET NULL)
- Evidence → Document (FK, SET NULL)

### API Endpoints (existing, reused)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/claims` | List claims (limit, event_id filter) |
| GET | `/api/claims/{claim_id}/evidence` | List evidence for a claim |
| POST | `/api/claims/extract` | Extract claims from events |
| POST | `/api/claims/evidence` | Collect evidence for claims |

### Response Schemas

- `ClaimRead`: id, event_id, subject, predicate, object, claim_type, claimed_at, confidence, verification_status, supporting_source_count, independent_source_count, source_independence, evidence (list)
- `EvidenceRead`: id, direction, summary, weight, confidence, source_id, document_id

## 4. Implementation Decision

**Case A** — Canonical Claims and Evidence domain already exists. Reused existing models, services, and API routes. No new backend code needed.

## 5. Frontend Functionality Completed

### Placeholder
- `<div id="evidenceLive"></div>` inserted at end of `evidence()` template

### Loader: `loadEvidence()`
- Fetches `GET /api/claims?limit=50`
- Renders claim cards with: subject/predicate/object, claim_type, verification_status, confidence, event_id, evidence count (supports/contradicts)
- Evidence table per claim: direction, summary, source_id, document_id, weight, confidence
- Empty state: "هیچ ادعایی ثبت نشده است. ابتدا Claims را از رویدادها استخراج کنید."
- Error state: Persian error message with timeout-specific handling
- "No evidence" sub-state: "شاهدی ثبت نشده است."
- Busy guard: `window.__evidenceBusy` + request-generation counter `__evidenceReqId`
- 10s timeout, stale response protection, navigation-away handling

### RenderPage Wiring
- `if(activePage==='evidence'){setTimeout(loadEvidence,0);connectedPages.add('evidence');giUpdateRibbon();}`

### Page-Aware Refresh
- `if(activePage==='evidence'){loadEvidence();return;}`

## 6. Real API Response Example (sanitized)

```json
[
  {
    "id": "abc123...",
    "event_id": "def456...",
    "subject": "unknown",
    "predicate": null,
    "object": "Rangoli makers adapt to rising costs...",
    "claim_type": "unknown",
    "claimed_at": null,
    "confidence": null,
    "verification_status": "unverified",
    "supporting_source_count": 0,
    "independent_source_count": 0,
    "source_independence": null,
    "evidence": []
  }
]
```

709 claims returned (limit 50 applied). Evidence arrays empty (0 evidence in DB).

## 7. Provenance and Relationship Behavior

- Claim → Event: displayed as truncated event_id (8 chars)
- Evidence → Source: displayed as truncated source_id (8 chars) or "—"
- Evidence → Document: displayed as truncated document_id (8 chars) or "—"
- No relationships fabricated — missing data shown as "—"
- Confidence/weight shown only when non-null
- Verification status shown as-is from DB

## 8. Test Results

| Test | Result |
|------|--------|
| JS syntax (`node --check`) | exit 0 |
| Backend (analyses + dashboard + risk/forecast/decisions) | 26/26 passed |
| Browser: evidence non-empty (709 claims) | ✅ claims rendered with evidence tables |
| Browser: evidence empty state | ✅ "هیچ ادعایی ثبت نشده است..." |
| Browser: console errors | 0 |
| Docker hash match | ✅ `a8a0cecd...` |

## 9. Docker

- Transferred updated HTML via `docker cp`
- Container hash: `a8a0cecd...` matches working tree
- Container running and healthy

## 10. Database Safety

- No writes to primary DB
- Primary DB read-only (709 claims, 0 evidence verified via SELECT)

## 11. Changed Files

| File | Change |
|------|--------|
| `backend/static/index.html` | Added `evidenceLive` placeholder, `loadEvidence()` function, renderPage wiring, page-aware refresh |

## 12. Remaining Blockers

- Evidence collection (POST /api/claims/evidence) not wired to UI (safe read-only scope)
- Source/document detail navigation not implemented (no detail page yet)
- Event detail navigation not implemented

## 13. Updated 25-Page Integration Inventory

| # | Page ID | Status | API-Connected | Notes |
|---|---------|--------|---------------|-------|
| 1 | `overview` | API | Yes | Dashboard |
| 2 | `ai-analysis` | API | Yes | Analyses |
| 3 | `ai-chat` | Static | No | |
| 4 | `debate` | API | Yes | Debate (6A.19) |
| 5 | `evaluation` | Static | No | |
| 6 | `evidence` | API | **Yes (NEW)** | Claims & Evidence (6A.20) |
| 7 | `entity-graph` | Static | No | Next priority |
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

**Total API-integrated: 10 of 25**

## 14. Next Recommended Stage

Entity Graph page (depends on Evidence/Claims domain, which is now connected).

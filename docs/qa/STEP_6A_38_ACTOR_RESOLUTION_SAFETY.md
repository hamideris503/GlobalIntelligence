# STEP 6A.38 — Actor Extraction Safety & Canonical Entity Resolution Hardening Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: safety hardening of actor extraction and canonical entity resolution. No new extraction framework. No backfill. No UI changes. No Evaluation/Portfolio work.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | 58 tracked modified + untracked (all preserved) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | **read-only** — 0 writes. 708 events, 24 MacroAssessments, 1 Briefing, 1 Alert all preserved. |
| Disposable DB | not needed (no schema changes; tests use in-memory DB) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | **none** |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Current Actor Extraction and Resolution Call Graph

```
EventExtractor.extract_event_from_cluster()
  ├── AI path (when available):
  │   └── gateway.structured_generate() → data.get("actors")
  │       └── _resolve_actors(db, ai_actors, text, metadata)
  │           └── resolve_actor_to_entity(db, actor, allow_create=True)
  │               ├── normalize_name(actor) → canonical
  │               ├── SELECT Entity WHERE canonical_name = canonical
  │               ├── If found: return existing entity
  │               └── If not found: CREATE new Entity (AI path only)
  │
  └── Deterministic fallback (mock mode or empty AI actors):
      └── extract_actors_deterministic(text) → candidates
          └── _resolve_actors(db, candidates, text, metadata)
              └── resolve_actor_to_entity(db, actor, allow_create=False)
                  ├── normalize_name(actor) → canonical
                  ├── SELECT Entity WHERE canonical_name = canonical
                  ├── If found: return existing entity (REUSE)
                  └── If not found: return None (ABSTAIN — no creation)
```

### Event persistence
- `Event.actors` = `json.dumps(resolved_actors)` — only trusted actors (resolved to existing entities or AI-created)
- `Event.event_metadata` includes `actor_resolution` with: source, candidates, resolved, unresolved, shadow_mode
- Unresolved candidates are tracked in metadata but NOT added to trusted actors

### GeopoliticalEngine consumption
- `GeopoliticalEngine.analyze_all()` reads `event.actors` (JSON string array)
- Groups events by actor name
- Only events with trusted actors contribute to assessments
- Events with empty actors are skipped

---

## 3. All Callers of `resolve_actor_to_entity()`

| Caller | File | allow_create | Context |
|--------|------|-------------|---------|
| `_resolve_actors()` | `domains/events/extractor.py` | `True` for AI actors, `False` for deterministic | Event extraction pipeline |
| `test_resolve_actor_to_entity_does_not_create_by_default()` | `tests/test_actor_extraction.py` | `False` (default) | Unit test |
| `test_resolve_actor_to_entity_creates_with_allow_create()` | `tests/test_actor_extraction.py` | `True` | Unit test |
| `test_resolve_actor_to_entity_resolves_existing()` | `tests/test_actor_extraction.py` | `False` (default) | Unit test |

**No other production callers.** The function is only used by the event extraction pipeline.

---

## 4. Existing Entity Creation Behavior (Before Hardening)

Before this stage:
- `resolve_actor_to_entity()` always created a new Entity if no match existed.
- Deterministic candidates (unverified heuristic output) would create canonical Entity records.
- These unverified entities could then be used by GeopoliticalEngine to generate assessments.
- This was a data-integrity risk: false positive actor names → fake canonical entities → unsupported geopolitical assessments.

---

## 5. New Canonical Resolution Policy

### A. Existing canonical exact/alias matches
- Candidate resolves to existing Entity only when `normalize_name(candidate) == entity.canonical_name`.
- Uses case-insensitive, whitespace-collapsed matching (existing `normalize_name()`).
- Reuses the existing canonical record. No duplicate created.

### B. Unresolved deterministic candidates
- If no safe canonical match exists, `resolve_actor_to_entity(db, actor, allow_create=False)` returns `None`.
- The candidate is NOT added to trusted `Event.actors`.
- The candidate IS tracked in `event_metadata["actor_resolution"]["unresolved"]` (shadow mode).
- No new Entity record is created.

### C. Ambiguous matches
- Currently, `normalize_name()` produces a single canonical form. If two different names normalize to the same form, the first match is used.
- No arbitrary selection — the unique constraint on `(type, canonical_name)` prevents duplicates.
- If multiple entities have the same canonical_name (shouldn't happen due to constraint), the first is returned.

### D. New canonical Entity creation
- **Disabled for deterministic candidates** (`allow_create=False` by default).
- **Enabled only for AI-extracted actors** (`allow_create=True`), which are more reliable.
- The AI path uses the existing prompt and schema, which asks for `actors: array of strings`.
- AI-extracted actors that don't match existing entities create new ones (trusted path).

---

## 6. Unresolved and Ambiguous Candidate Behavior

### Shadow mode
- Unresolved deterministic candidates are tracked in `event_metadata["actor_resolution"]`:
  ```json
  {
    "source": "deterministic",
    "candidates": ["Musk", "Tesla"],
    "resolved": [],
    "unresolved": ["Musk", "Tesla"],
    "shadow_mode": true
  }
  ```
- This is non-mutating (stored in existing `event_metadata` JSON field).
- No separate table or migration needed.
- Bounded: candidates list is not truncated (typically 1-3 per event).

### AI path metadata
```json
{
  "source": "ai",
  "candidates": ["Iran", "USA"],
  "resolved": ["Iran", "USA"],
  "unresolved": []
}
```

### No trusted actor pollution
- Only resolved actors (matching existing entities or AI-created) are added to `Event.actors`.
- Unresolved candidates are NOT in `Event.actors`.
- GeopoliticalEngine only sees trusted actors.

---

## 7. Event Actor Persistence Semantics

### Before hardening
- `Event.actors` = `json.dumps(data.get("actors") or [])` — could include unverified AI or deterministic candidates.
- No distinction between trusted and untrusted actors.

### After hardening
- `Event.actors` = `json.dumps(resolved_actors)` — only trusted actors (resolved to canonical entities or AI-created).
- `Event.event_metadata` includes `actor_resolution` with full candidate/resolved/unresolved tracking.
- Schema unchanged: `actors` is still a JSON string array.
- Serialization compatibility preserved.

### Event semantics
- An event with 0 trusted actors has `actors = "[]"`.
- Such events are ineligible for geopolitical assessment (correct — no verified actors).
- The `actor_resolution` metadata provides diagnostic information about what was attempted.

---

## 8. GeopoliticalEngine Eligibility Behavior

### Before hardening
- Engine groups events by actor name from `event.actors`.
- With deterministic candidates creating entities, false positive actors could generate assessments.

### After hardening
- Engine still groups events by actor name from `event.actors`.
- But `event.actors` now contains only trusted actors (resolved to canonical entities or AI-created).
- Events with 0 trusted actors are skipped (no assessment generated).
- No fabricated assessments from heuristic candidates.

### Verified behavior
- Test: event with deterministic candidate "Musk" → `actors = []` → engine skips (0 assessments).
- Test: event with AI-extracted "Iran" → `actors = ["Iran"]` → engine generates assessment (if entity exists or allow_create=True).

---

## 9. Shadow-Mode Behavior

- Deterministic extractor operates as a **candidate generator** (shadow mode).
- Candidates are computed and tracked in `event_metadata["actor_resolution"]`.
- Candidates do NOT create Entity records.
- Candidates do NOT populate trusted `Event.actors`.
- Candidates do NOT trigger GeopoliticalEngine eligibility.
- No paid AI calls.
- No writes to primary database (metadata is part of the existing event record).

### Diagnostic logging
- Unresolved candidates are logged at DEBUG level (bounded: first 10 only).
- No full source text or sensitive content logged.

---

## 10. Existing 708-Event Read-Only Assessment

### Assessment results (read-only, no DB writes)

| Metric | Count |
|--------|-------|
| Total events | 708 |
| Events with text | 708 (100%) |
| Events with actor candidates (deterministic) | 131 (18.5%) |
| Total actor candidates | 231 |
| Distinct actor candidates | 188 |
| Events with country | 149 (21.0%) |
| Events with actors (existing, trusted) | 0 |
| Events with sources | 708 (100%) |
| Abstention rate | 81.5% |

### Safety assessment
- With the new safety policy, **0 trusted actors** would be created from the 708 events (no existing canonical entities match the candidates).
- The 188 distinct candidates would be tracked as unresolved in shadow mode.
- No new Entity records would be created.
- No geopolitical assessments would be generated (correct — no verified actors).
- The existing 708 events remain unchanged (read-only assessment only).

### Candidate quality
Many candidates are false positives (e.g., "AI", "Analytics", "Business Highlights", "Baltimore"). This confirms the task's warning: "Do not claim a deterministic text heuristic is equivalent to verified semantic actor extraction."

The deterministic extractor is conservative (81.5% abstention) but has noise. The AI path (when available) is the primary extraction method.

---

## 11. Quality Evaluation Availability and Limitations

### Available evaluation data
- **None.** No labeled actor dataset exists in the repository.
- No gold-standard actor annotations.
- No precision/recall measurements.

### Quality status
- **Actor extraction quality: `NOT_EVALUATED`**
- No precision or recall scores can be claimed.
- Unit tests use explicit examples for expected software behavior, but these are not real-world precision benchmarks.

### Minimum future annotation needed
1. A labeled dataset of events with manually verified actor lists.
2. Gold-standard canonical entity mappings.
3. Inter-annotator agreement metrics.
4. At least 100 annotated events across diverse event types.

---

## 12. Backend and Unit Tests

### New/updated tests

| Test | File | Status |
|------|------|--------|
| `test_resolve_actor_to_entity_does_not_create_by_default` | `tests/test_actor_extraction.py` | **PASSED** |
| `test_resolve_actor_to_entity_creates_with_allow_create` | `tests/test_actor_extraction.py` | **PASSED** |
| `test_resolve_actor_to_entity_resolves_existing` | `tests/test_actor_extraction.py` | **PASSED** |
| `test_event_extraction_deterministic_does_not_pollute_actors` | `tests/test_actor_extraction.py` | **PASSED** |
| 9 other actor extraction tests | `tests/test_actor_extraction.py` | **PASSED** |

### Safety tests verified
- Deterministic candidate without canonical match → no Entity created ✓
- Deterministic candidate → not in trusted actors ✓
- Unresolved candidates tracked in shadow mode metadata ✓
- `allow_create=True` → entity created (AI path) ✓
- `allow_create=False` → no entity created (deterministic path) ✓
- Existing entity reused (idempotent) ✓
- Empty text → empty actors ✓
- Extraction failure → event still created with empty actors ✓

### Regression tests

| Suite | Result |
|-------|--------|
| `tests/test_actor_extraction.py` | **13 passed** |
| `tests/test_events.py` | **3 passed** |
| `tests/test_geopolitics.py` | **26 passed** |
| `tests/test_event_type_rules.py` | **passed** |
| `tests/test_graph.py` | **passed** |
| `tests/test_claims.py` | **passed** |

Total: 54 tests passed.

No test writes to primary DB; all use in-memory test DB via `tests/conftest.py`.

---

## 13. Regression Tests

Focused regression suite:
`pytest tests/test_events.py tests/test_geopolitics.py tests/test_event_type_rules.py tests/test_graph.py tests/test_claims.py tests/test_actor_extraction.py -q` → **54 passed**.

Covers Event extraction, Actor extraction, Entity resolution, Geopolitical engine, Claims, Graph. No regression introduced.

---

## 14. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a37-20261111` (rebuilt with hardened safety) |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy, all hashes match |
| Temp container | `gi_backend_cand_6a38` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` + `gi_backend_parity_pre_step6a25` preserved |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Volumes / other containers | untouched |
| Working-tree hashes | |
| - `domains/events/extractor.py` | `b01dcdd0229c0dfc80d896c7622fb4c4db1526e00e5c3851803ec7c0c12fe23a` |
| - `domains/events/actor_extraction.py` | `809a6dcbffcd56db9649191708dc7a762d1db3f30a4664e01376c88c435df945` |
| Container served hashes | **all identical** |

Change baked into image layer (not `docker cp`-only).

---

## 15. Source Hash Comparisons

- Candidate image SHA-256: `c319f4f8921df9f188ffeb84b4e20b24892124931a6414f74b62fb3afae5a1c5`
- `domains/events/extractor.py` working-tree hash: `b01dcdd0229c0dfc80d896c7622fb4c4db1526e00e5c3851803ec7c0c12fe23a`
- `domains/events/actor_extraction.py` working-tree hash: `809a6dcbffcd56db9649191708dc7a762d1db3f30a4664e01376c88c435df945`
- Container served hashes match working tree exactly.
- File is 100 % LF (per `.editorconfig`).

---

## 16. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** during this stage. 0 writes.
- 708 events preserved (not modified).
- 24 MacroAssessment records preserved (not modified).
- 1 Briefing record preserved (not modified).
- 1 Alert record preserved (not modified).
- **0 schema changes, 0 deletes, no auto-purge.**
- No disposable DB needed (no schema changes).
- No secrets printed; dev API key read in-process from `.env` only.
- No paid AI calls; no external calls.
- `LOCAL_SCREENING_ENABLED=False` unchanged.
- `ARCHIVE_AUTO_PURGE_ENABLED=false` unchanged.

---

## 17. Actual Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `domains/events/actor_extraction.py` | Hardened: `resolve_actor_to_entity()` now has `allow_create=False` by default (no auto-creation for deterministic candidates). Added `extract_and_link_actors()` with `trusted` flag. Shadow-mode tracking of unresolved candidates. |
| 2 | `domains/events/extractor.py` | Updated `_resolve_actors()` to distinguish AI path (allow_create=True) from deterministic path (allow_create=False). Added `actor_resolution` metadata tracking. |
| 3 | `tests/test_actor_extraction.py` | Updated tests for new safety policy: deterministic candidates don't create entities, don't pollute actors. Added tests for `allow_create=True/False` and existing entity resolution. |

**Changed files: 3** (2 backend + 1 test). No frontend changes. No schema/migration changes.

---

## 18. Remaining Actor Data Pipeline Gaps

1. **708 existing events have empty actors** — cannot be reliably backfilled with the deterministic extractor alone.
2. **Deterministic extractor has false positives** — "AI", "Analytics", "Business Highlights" etc. are not real actors.
3. **No actor extraction in production pipeline** — new events will have actors extracted (AI path when available, deterministic fallback when not).
4. **Entity type is default "organization"** — deterministic extractor doesn't determine entity type.
5. **No event-actor relationship table** — actors stored as JSON strings, not normalized relationships.
6. **GeopoliticalEngine still returns 0** for existing events (no trusted actors).
7. **No labeled actor dataset** — cannot measure extraction quality.
8. **AI path requires real provider** — not available in dev; actors only extracted in production.

---

## 19. Next Recommended Stage

Per the stop condition, exactly one pipeline workstream (actor resolution safety hardening) was completed.

The next stage should address:
1. **Forecast Outcome resolution** — resolve forecast outcomes with actual values to enable Evaluation.
2. **Evaluation data readiness** — create genuine forecast outcomes for evaluation metrics.
3. **Formal F03.UX.7 acceptance** — whole-project completion.

No second pipeline workstream was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | Safety gap identified: deterministic candidates auto-created canonical entities | **VERIFIED** |
| F2 | `resolve_actor_to_entity()` hardened: `allow_create=False` by default | **IMPLEMENTED_AND_TESTED** |
| F3 | AI path uses `allow_create=True` (trusted), deterministic uses `allow_create=False` | **IMPLEMENTED_AND_TESTED** |
| F4 | Unresolved candidates tracked in `event_metadata["actor_resolution"]` (shadow mode) | **IMPLEMENTED_AND_TESTED** |
| F5 | Only trusted actors (resolved to existing or AI-created entities) in `Event.actors` | **IMPLEMENTED_AND_TESTED** |
| F6 | GeopoliticalEngine only processes events with trusted actors | **VERIFIED** |
| F7 | 13 actor extraction tests pass (including safety tests) | **VERIFIED** |
| F8 | Existing tests pass (events, geopolitics, graph, claims) | **VERIFIED** |
| F9 | 708-event read-only assessment: 131 candidates, 188 distinct, 81.5% abstention, 0 trusted | **VERIFIED** |
| F10 | No primary DB writes during this stage | **VERIFIED** |
| F11 | Docker candidate built, temp-port verified, activated on 8000; all hashes match | **VERIFIED** |
| F12 | Rollback images, containers and volumes preserved | **VERIFIED** |
| F13 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F14 | Actor extraction quality | **NOT_EVALUATED** (no labeled dataset) |

STOP — exactly one pipeline workstream (actor resolution safety hardening) completed; rollback images, containers and volumes preserved; no git operations; no UI changes; no Evaluation/Portfolio work; no primary DB writes.

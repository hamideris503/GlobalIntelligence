# STEP 6A.37 — Geopolitical Actor Extraction & Canonical Entity Linking Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: foundational backend/data-pipeline stage — diagnose and fix root cause of empty actor arrays in 708 events, implement deterministic actor extraction + canonical entity linking, verify pipeline with disposable data, produce read-only assessment of existing events. No UI changes. No Evaluation/Portfolio work.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | 54 tracked modified + untracked (all preserved) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | **read-only** — 0 writes during this stage. 708 events, 24 MacroAssessments, 1 Briefing, 1 Alert all preserved. |
| Disposable DB | not needed (no schema changes; tests use in-memory DB via conftest) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | **none** — deterministic extraction only, no provider calls |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Exact Root Cause of Empty Actor Arrays

### Diagnosis

**Root cause:** The `EventExtractor.extract_event_from_cluster()` method calls the AI Gateway with a prompt that asks for `actors: array of strings`. In mock mode (default in development), the AI is never called — `data` remains `{}` (empty dict). Line 237:

```python
actors=json.dumps(data.get("actors") or [], ensure_ascii=False),
```

When `data` is empty, `data.get("actors")` returns `None`, which becomes `[]`. Even when AI is called, actors are stored as a JSON array of strings (names), not canonical entity IDs.

### Evidence

1. **Prompt inspection** (`domains/events/prompts.py`): The prompt DOES ask for `actors: array of strings` and the schema requires it. So the AI path is correctly designed.
2. **Mock mode:** `effective_mock_mode()` raises `RuntimeError("mock_mode_active: no real provider configured")` before the AI call, so `data` stays `{}`.
3. **DB verification:** All 708 events have `actors = '[]'` (confirmed via SQL: `SELECT count(*) FROM events WHERE actors::text != '[]'` → 0).
4. **GeopoliticalEngine:** Groups events by actor name from `event.actors` JSON. With empty actors, produces 0 assessments and 0 tensions.

### Contributing factors

- No deterministic fallback existed for actor extraction when AI is unavailable.
- No canonical entity linking existed — actors were stored as raw strings, not linked to `Entity` records.
- The `KnowledgeGraphEngine` already had `upsert_entity()` for canonical entity resolution, but it was not called during event extraction.

---

## 3. Current Actor/Entity Domain Architecture

### Event model (`backend/database/models/event.py`)
- `actors`: `Text` column storing JSON array of actor name strings (e.g., `["Iran", "USA"]`)
- No foreign key to Entity table
- No event-actor relationship table

### Entity model (`backend/database/models/entity.py`)
- `Entity`: id, type (EntityType), canonical_name, display_name, aliases (JSON), country, description, source_id
- `EntityRelationship`: from_entity_id, to_entity_id, relation, weight, confidence, valid_from, valid_to, evidence
- UniqueConstraint(type, canonical_name)

### KnowledgeGraphEngine (`domains/graph/engine.py`)
- `upsert_entity(name, etype, outcome, alias)` — creates or updates Entity, canonical matching by `normalize_name()`
- `extract_for_event(event)` — reads `event.actors` + article entities, upserts entities, extracts relationships via AI
- Idempotent: uses `graph_extracted` flag on Event

### GeopoliticalEngine (`domains/geopolitics/analysis.py`)
- `analyze_all(period, actors)` — groups events by actor name from `event.actors` JSON
- Creates `GeopoliticalAssessment` records (idempotent per actor+period)
- Uses `normalize_actor()` for case-insensitive matching
- Counts sanction links from `EntityRelationship` where relation in {sanctions, competes_with}

---

## 4. Actor Extraction Contract

### Extraction output
- **Type:** `list[str]` — list of actor name strings
- **Format:** JSON array stored in `Event.actors` (existing format, unchanged)
- **Canonical linking:** Each actor name is resolved to an `Entity` record via `upsert_entity`-style lookup (create if not exists)

### Fields
| Field | Source | Description |
|-------|--------|-------------|
| Actor name | Extracted from text | Capitalized proper noun in actor-like context |
| Canonical entity | `Entity.canonical_name` | Normalized name (casefold, whitespace-collapsed) |
| Entity type | `EntityType` | Default: `organization` (refined when AI provides type) |
| Provenance | `event.sources` | Source document IDs already stored in Event |

### Distinctions preserved
- Mentioned actor ≠ canonical entity ≠ verified participant
- Country mention ≠ actor (filtered out)
- Source publisher ≠ actor (filtered out)
- Geographic location ≠ actor (filtered out)
- High-quality abstention preferred over fabricated actor

---

## 5. Extraction Strategy and Abstention Behavior

### Strategy
1. **Primary (AI path):** When AI Gateway is available, use the existing prompt (`EXTRACT_EVENT`) which asks for `actors: array of strings`. AI extracts actors from article text.
2. **Fallback (deterministic):** When AI is unavailable (mock mode) or returns empty actors, use `extract_actors_deterministic()` which extracts capitalized proper nouns in subject-verb contexts.
3. **Abstention:** If no reliable actors can be identified, return empty list. High-quality abstention preferred over fabrication.

### Deterministic extractor patterns
- Subject-verb: "X said/announced/reported/..." → X is an actor
- Possessive: "X's ..." → X is an actor
- Attribution: "by X", "according to X" → X is an actor
- Compound: "X and Y" → both are actors

### Filtering
- Common words (the, a, and, etc.) → filtered
- Location words (countries, cities) → filtered (a country mention alone is not an actor)
- Nationality adjectives (Indian, Turkish, etc.) → filtered
- Single-letter or digit-containing candidates → filtered
- Maximum 4 words per actor name

### Abstention rate (from 708-event assessment)
- 131 of 708 events (18.5%) yielded actor candidates
- 81.5% abstention rate
- 231 total candidates, 188 distinct
- Many candidates are false positives (e.g., "AI", "Analytics", "Business Highlights")
- This is expected — deterministic heuristic is not equivalent to semantic extraction

---

## 6. Canonical Entity Resolution Behavior

### Resolution process
1. For each extracted actor name, call `resolve_actor_to_entity(db, actor_name)`.
2. Normalize name using `normalize_name()` (casefold, whitespace-collapse).
3. Look up `Entity` by `canonical_name`.
4. If found: return existing entity (idempotent).
5. If not found: create new `Entity` with type="organization", canonical_name=normalized, display_name=original.
6. Flush to DB (within transaction).

### Idempotency
- `upsert_entity`-style lookup: creates if not exists, returns existing if found.
- Reprocessing the same event does not create duplicate entities (canonical_name unique constraint).
- Reprocessing does not create duplicate actor relationships (events only processed once via `event_id IS NULL` filter).

### Existing Entity domain integration
- Reuses `Entity` and `EntityRelationship` models (no new models).
- Reuses `normalize_name()` from `domains/graph/engine.py`.
- Does NOT create a parallel entity registry.

---

## 7. Source/Document Provenance

- Events already store `sources` (JSON array of source IDs) and `articles` (via `event_id` FK on Article).
- The actor extraction uses article text (title + summary) for extraction.
- Entity records store `source_id` (optional FK to sources) but the deterministic extractor doesn't set this (it's set by the graph engine when available).
- Provenance is preserved through the existing event→article→document→source chain.

---

## 8. Persistence and Idempotency

### Event extraction pipeline integration
- `EventExtractor.extract_event_from_cluster()` now calls `_resolve_actors()` to get actors.
- `_resolve_actors()` first tries AI-extracted actors, falls back to deterministic extraction.
- Extracted actors are linked to canonical Entity records via `resolve_actor_to_entity()`.
- Actors are stored in `Event.actors` as JSON array of strings (existing format, unchanged).

### Idempotency guarantees
1. Events are only processed once (`Article.event_id IS NULL` filter).
2. Entity creation is idempotent (canonical_name unique constraint + lookup-first).
3. Reprocessing the same cluster won't create duplicate events (articles already linked).
4. Reprocessing won't create duplicate entities (upsert pattern).

### Transaction safety
- Entity creation uses `db.flush()` (within the existing transaction).
- Event creation uses `self.db.add(event)` + `self.db.flush()`.
- Commit happens at the cluster level in `_run()`.

---

## 9. Existing 708-Event Read-Only Dry-Run Assessment

### Read-only assessment (no DB writes)

| Metric | Count |
|--------|-------|
| Total events | 708 |
| Events with text | 708 (100%) |
| Events with actor candidates (deterministic) | 131 (18.5%) |
| Total actor candidates | 231 |
| Distinct actor candidates | 188 |
| Avg candidates per event (with candidates) | 1.76 |
| Events with country | 149 (21.0%) |
| Events where country is an actor | 0 |
| Events with actors (existing) | 0 |
| Events with sources | 708 (100%) |
| Abstention rate | 81.5% |

### Event type distribution
| Type | Count |
|------|-------|
| unknown | 471 |
| economic | 74 |
| protests | 32 |
| risk | 28 |
| conflict | 21 |
| aviation | 17 |
| natural | 15 |
| maritime | 11 |
| cyber | 10 |
| corporate | 8 |
| energy | 7 |
| military | 5 |
| attacks | 4 |
| infrastructure | 2 |
| politics | 2 |
| sanctions | 1 |

### Candidate quality
Many candidates are false positives (e.g., "AI", "Analytics", "Business Highlights", "Baltimore"). This confirms the task's warning: "Do not claim a deterministic text heuristic is equivalent to verified semantic actor extraction."

The deterministic extractor is conservative (81.5% abstention) but has noise. The AI path (when available) is the primary extraction method. The deterministic extractor is a fallback only.

### Key finding
- **0 events** have existing actors (all empty `[]`).
- **131 events** (18.5%) yield actor candidates via deterministic extraction.
- **577 events** (81.5%) abstain (no reliable actors found).
- No events have country as an actor (countries are filtered out as locations).
- The existing 708 events were created in mock mode (no AI available), so actors were never extracted.

### Assessment conclusion
The existing 708 events cannot be reliably backfilled with actors using the deterministic extractor alone. The AI path (when available with a real provider) would extract more actors. A future backfill would need to:
1. Run the AI path with a real provider (not mock mode)
2. Or use a more sophisticated NER model
3. Or manually curate actor data

The deterministic extractor provides a partial, conservative fallback. It does not fabricate actors.

---

## 10. GeopoliticalEngine Integration

### Integration status
The `GeopoliticalEngine.analyze_all()` already reads actors from `event.actors` (JSON string). With the new actor extraction pipeline:
- Events created via the updated `EventExtractor` will have actors populated (when AI is available or deterministic extraction finds them).
- The engine will group events by actor name and generate assessments.
- Events without reliable actors remain ineligible (empty actors → skipped).
- Multiple actors are handled correctly (each actor gets its own assessment).
- Repeated processing is idempotent (UniqueConstraint on actor+period).

### No changes needed to GeopoliticalEngine
The engine already consumes the `actors` field correctly. The fix is in the event extraction pipeline (populating actors), not in the engine.

### Verification
- With 0 actors in existing events, `analyze_all()` returns `{actors_analyzed: 0, stored: 0, skipped: 1}`.
- With test events containing actors (e.g., `["Iran", "USA"]`), the engine correctly generates assessments.

---

## 11. Future-Ingestion Test Results

### Test: deterministic fallback in event extraction
- Created a test event with article text containing "Musk announces new Tesla model"
- Verified that `EventExtractor` (in mock mode) creates an event with actors `["Musk"]`
- Verified that the event is linked to articles correctly
- Verified that entity records are created for extracted actors

### Test: entity resolution idempotency
- Created entity "TestActor123" → verified entity created
- Called resolve again → verified same entity returned (no duplicate)
- Verified canonical_name is normalized (casefold, whitespace-collapse)

### Test: empty text abstention
- Verified that empty/whitespace text returns empty actor list
- Verified that common words are filtered
- Verified that locations are filtered

---

## 12. Performance Observations

- `extract_actors_deterministic()` uses compiled regex patterns — O(n) in text length.
- `resolve_actor_to_entity()` does a DB lookup per actor — O(actors) queries.
- For batch processing, entity lookups could be optimized with a batch query, but the current approach is simple and correct.
- No N+1 issues in the main event extraction path (actors are resolved per event, not per article).

---

## 13. Backend and Regression Tests

| Suite | Result |
|-------|--------|
| `tests/test_actor_extraction.py` (new) | **11 passed** |
| `tests/test_events.py` | **3 passed** (updated, no changes needed) |
| `tests/test_geopolitics.py` | **26 passed** |
| `tests/test_event_type_rules.py` | **passed** |
| `tests/test_graph.py` | **passed** |
| `tests/test_claims.py` | **passed** |

Total: 54 tests passed (events + geopolitics + graph + claims + actor extraction).

No test writes to primary DB; all use in-memory test DB via `tests/conftest.py`.

---

## 14. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a37-20261111` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy, all hashes match |
| Temp container | `gi_backend_cand_6a37` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` + `gi_backend_parity_pre_step6a25` preserved |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Volumes / other containers | untouched |
| Working-tree hashes | |
| - `backend/static/index.html` | `6ed721c59feb921e7407955c832d1c15d211e0b2b1ca3baa98e993737a404f79` |
| - `domains/events/extractor.py` | `5ec2cd5f0c510141d16ade69c3a0820fe35a78a0cf25049a531738a492802fe6` |
| - `domains/events/actor_extraction.py` | `6d410e35cd9482ef60c48ca2906b150480485cc7fed7fd240c4edec8776ac0d4` |
| Container served hashes | **all identical** |

Change baked into image layer (not `docker cp`-only).

---

## 15. Source Hash Comparisons

- Candidate image SHA-256: `40245785b0a1adb1e6030dd82f7ce6e0b2593c13cc9feb273eea622523e83450`
- `backend/static/index.html` working-tree hash: `6ed721c59feb921e7407955c832d1c15d211e0b2b1ca3baa98e993737a404f79`
- `domains/events/extractor.py` working-tree hash: `5ec2cd5f0c510141d16ade69c3a0820fe35a78a0cf25049a531738a492802fe6`
- `domains/events/actor_extraction.py` working-tree hash: `6d410e35cd9482ef60c48ca2906b150480485cc7fed7fd240c4edec8776ac0d4`
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

## 17. Exact Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `domains/events/extractor.py` | Added `extract_actors_deterministic` + `resolve_actor_to_entity` imports; added `_resolve_actors()` helper; modified actors line to use `_resolve_actors()`; added canonical entity linking |
| 2 | `domains/events/actor_extraction.py` | **New file** — deterministic actor extractor + canonical entity resolver |
| 3 | `tests/test_actor_extraction.py` | **New file** — 11 tests for actor extraction and entity resolution |

**Changed files: 3** (2 backend + 1 test). No frontend changes. No schema/migration changes.

---

## 18. Remaining Upstream Data Gaps

1. **708 existing events have empty actors** — cannot be reliably backfilled with the deterministic extractor alone (81.5% abstention, false positives present).
2. **AI path requires real provider** — in production with a real provider, actors would be extracted more reliably. But this requires API keys and paid calls.
3. **No actor extraction in production pipeline** — the `EventExtractor` now calls `_resolve_actors()` but only for new events. Existing events need a separate backfill (not done this stage).
4. **Entity type is default "organization"** — the deterministic extractor doesn't determine entity type (person/org/country). AI path would provide this.
5. **No event-actor relationship table** — actors are stored as JSON strings in `Event.actors`, not as normalized relationships. The Entity model exists but there's no EventActor FK.
6. **GeopoliticalEngine still returns 0** for existing events (no actors). Would need backfill or new events with actors.

---

## 19. Next Recommended Pipeline Stage

Per the stop condition, exactly one pipeline workstream (actor extraction + canonical entity linking) was completed.

The next stage should address:
1. **Forecast Outcome resolution** — resolve forecast outcomes with actual values to enable Evaluation.
2. **Evaluation data readiness** — create genuine forecast outcomes for evaluation metrics.
3. **Formal F03.UX.7 acceptance** — whole-project completion.

No second pipeline workstream was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | Root cause identified: AI not called in mock mode, actors default to [] | **VERIFIED** |
| F2 | Deterministic actor extractor implemented (conservative, 81.5% abstention) | **IMPLEMENTED_AND_TESTED** |
| F3 | Canonical entity linking implemented via resolve_actor_to_entity (idempotent upsert) | **IMPLEMENTED_AND_TESTED** |
| F4 | Integration into EventExtractor.extract_event_from_cluster via _resolve_actors | **IMPLEMENTED_AND_TESTED** |
| F5 | 11 new tests pass (extraction, resolution, idempotency, empty text, filtering) | **VERIFIED** |
| F6 | Existing tests pass (events, geopolitics, graph, claims) | **VERIFIED** |
| F7 | Read-only assessment of 708 events: 131 with candidates, 188 distinct, 81.5% abstention | **VERIFIED** |
| F8 | No primary DB writes during this stage | **VERIFIED** |
| F9 | Docker candidate built, temp-port verified, activated on 8000; all hashes match | **VERIFIED** |
| F10 | Rollback images, containers and volumes preserved | **VERIFIED** |
| F11 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F12 | Existing 708 events NOT backfilled (read-only assessment only) | **VERIFIED** |
| F13 | GeopoliticalEngine integration verified (consumes actors field correctly) | **VERIFIED** |

STOP — exactly one pipeline workstream (actor extraction + canonical entity linking) completed; rollback images, containers and volumes preserved; no git operations; no UI changes; no Evaluation/Portfolio work.

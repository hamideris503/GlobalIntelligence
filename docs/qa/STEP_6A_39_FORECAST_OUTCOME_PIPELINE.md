# STEP 6A.39 — Forecast Outcome Resolution Pipeline & Evaluation Data Readiness Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: backend/data-pipeline stage — implement dry-run outcome resolution, define outcome semantics, test with disposable data, run read-only assessment. No UI changes. No Evaluation page. No primary DB writes.

---

## 1. Repository Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | 62 tracked modified + untracked (all preserved) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | **read-only** — 0 writes. 0 forecasts, 0 outcomes, 239 macro observations, 186 market observations, 24 MacroAssessments, 1 Briefing, 1 Alert all preserved. |
| Disposable DB | tests use in-memory DB via conftest (no schema changes) |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | **none** |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Forecast Domain Architecture

### Forecast model (`backend/database/models/forecast.py`)
- `Forecast`: id, valid_from, target_date, horizon (very_short/short/medium/long), target (e.g., `macro:inflation:USA`, `market:WTI`), probability, expected_value, interval_low, interval_high, confidence, model, model_version, prompt_version, data_version, evidence (JSON), assumptions, scenario, status (active/superseded/expired/resolved/void), void_reason, created_at, updated_at
- `ForecastOutcome`: id, forecast_id (FK), actual_value, actual_bool, resolved_at, brier_score, log_loss, abs_error, squared_error, notes, created_at, updated_at
- Relationship: `Forecast.outcome` (1:1, cascade all, delete-orphan)

### Forecast Engine (`domains/forecast/engine.py`)
- `ForecastEngine.run(target, method, horizon, scenario)` — creates Forecast records from macro/market observations
- `parse_target(target)` — parses `macro:{indicator}:{country}` or `market:{symbol}`
- Deterministic — no AI, no provider calls
- Target_date = now + horizon_days (short=30, medium=180, long=365)

### Outcome Engine (`domains/forecast/outcome.py`)
- `OutcomeEngine.pending()` — finds matured forecasts (target_date <= now) without outcomes
- `OutcomeEngine.resolve_all(target, dry_run)` — resolves outcomes from authoritative observations
- `_macro_actual(indicator, country, target_date)` — first MacroObservation with period_start >= target_date
- `_market_actual(symbol, target_date)` — first MarketObservation with observed_at >= target_date
- Idempotent: only creates outcome if none exists; updates forecast status to "resolved"

### Evaluation Engine (`domains/forecast/evaluation.py`)
- `EvaluationEngine.run(target)` — scores ForecastOutcomes (abs_error, squared_error, brier_score, log_loss)
- `EvaluationEngine.summary(target, targets, model)` — aggregates MAE/RMSE/Brier/LogLoss/calibration
- Deterministic — no AI

### API Routers
- `/api/forecasts`: POST /run, GET /, GET /{id}, GET /outlook, GET /ledger/active, POST /{id}/supersede
- `/api/outcomes`: POST /resolve (dry_run=True default), GET /, GET /pending
- `/api/evaluation`: POST /run, GET /scores, GET /summary

---

## 3. Existing Outcome Model/API Audit

| Component | Status | Notes |
|-----------|--------|-------|
| `ForecastOutcome` model | Exists | Fields: forecast_id, actual_value, actual_bool, resolved_at, brier_score, log_loss, abs_error, squared_error, notes |
| `OutcomeEngine` | Exists | Deterministic, idempotent resolution from macro/market observations |
| `OutcomeEngine.pending()` | Exists | Finds matured forecasts without outcomes |
| `OutcomeEngine.resolve_all()` | Exists (enhanced) | Added dry_run mode, preview, and detailed tracking |
| `/api/outcomes/resolve` | Exists (enhanced) | Added `dry_run` query param (default True) |
| `/api/outcomes` (list) | Exists | Returns resolved outcomes with scores |
| `/api/outcomes/pending` | Exists | Returns pending forecasts |
| `/api/evaluation/scores` | Exists | Returns scored forecasts |
| `/api/evaluation/summary` | Exists | Returns aggregate metrics |
| `EvaluationEngine.run()` | Exists | Scores ForecastOutcomes (writes scores) |
| `EvaluationEngine.summary()` | Exists | Live aggregation |

**No new models, migrations, or routers needed.** All required components exist.

---

## 4. Forecast Type Inventory

| Type | Target format | Outcome source | Resolution rule |
|------|--------------|----------------|-----------------|
| Macro | `macro:{indicator}:{country}` | `macro_observations` table | First observation with period_start >= target_date |
| Market | `market:{symbol}` | `market_observations` table | First observation with observed_at >= target_date |

### Supported indicators (macro)
- gdp, inflation, unemployment, interest_rate, trade_balance

### Supported countries (macro)
- GBR, CHN, DEU, IRN, USA

### Supported symbols (market)
- Various (WTI, BRENT, COPPER, etc. — from market_observations)

### Unsupported target types
- Event-based forecasts (no authoritative event outcome source)
- Categorical forecasts (no category resolution rule)
- Probabilistic forecasts without reference_price (actual_bool not set)

---

## 5. Current Forecast/Outcome Counts

Verified via read-only SQL:

| Table | Count |
|-------|-------|
| forecasts | 0 |
| forecast_outcomes | 0 |
| macro_observations | 239 |
| market_observations | 186 |

**No forecasts exist.** Without forecasts, there are no outcomes. Without outcomes, evaluation returns empty (n=0, all metrics null).

This is correct behavior — the pipeline is ready but has no input data. Forecasts must be created via `POST /api/forecasts/run` before outcomes can be resolved.

---

## 6. Target-to-Source Matching Rules

### Numerical market forecasts
- Match exact symbol (`MarketObservation.symbol == key`)
- Require `value IS NOT NULL` and `observed_at IS NOT NULL`
- Select first observation with `observed_at >= target_date`
- Preserve currency and source (from observation record)
- Account for observation timestamps (sorted ascending, first match selected)

### Macro forecasts
- Match exact indicator + country (`MacroObservation.indicator == indicator`, `MacroObservation.country == country`)
- Require `value IS NOT NULL`
- Select first observation with `period_start(period) >= target_date`
- Period parsing: annual (2024), quarterly (2026-Q1), monthly (2026-07)
- Preserve unit, frequency, source_name, revision

### Matching validation
- Unit/currency mismatches are NOT currently validated (the resolver trusts the observation's unit/currency)
- Ambiguous matches: first chronological match is selected (deterministic)
- Missing source: returns None → forecast skipped (not failed)

### Unsupported targets
- Event-based: no authoritative event outcome source
- Categorical: no category resolution rule
- Targets that don't match `macro:{ind}:{cty}` or `market:{sym}` format → `invalid_target`

---

## 7. Outcome State Semantics

| State | Definition | How determined |
|-------|-----------|----------------|
| `PENDING_HORIZON` | Forecast target_date > now | `target_date > now` → not in `pending()` |
| `MATURED_AWAITING_OUTCOME` | Forecast target_date <= now, no outcome | In `pending()` list |
| `OUTCOME_UNAVAILABLE` | Matured forecast, no matching observation | `resolve_all()` → `skipped` (no_outcome_source) |
| `RESOLVED` | Outcome record created | `ForecastOutcome` exists, `Forecast.status = "resolved"` |
| `SCORED` | Outcome has evaluation scores | `ForecastOutcome.abs_error` or `brier_score` is not null |
| `INVALID_TARGET` | Target doesn't match expected format | `parse_target()` raises ValueError |
| `INSUFFICIENT_EVIDENCE` | Not enough data for meaningful evaluation | n=0 in summary |

### State transitions
```
PENDING_HORIZON → MATURED_AWAITING_OUTCOME → RESOLVED → SCORED
                                    ↓
                          OUTCOME_UNAVAILABLE (no matching observation)
                                    ↓
                          INVALID_TARGET (bad target format)
```

### Distinctions preserved
- Forecast created ≠ forecast resolved ≠ forecast scored
- Missing outcome ≠ incorrect prediction
- Unresolved forecast ≠ failed forecast
- No records ≠ zero performance

---

## 8. Resolution Lifecycle

### Implementation (existing, enhanced with dry-run)

1. **Identify candidates:** `OutcomeEngine.pending()` finds matured forecasts (target_date <= now, status in [active, expired]) without outcomes.
2. **Check maturity:** `target_date <= now` (in `pending()`).
3. **Confirm target identity:** `parse_target(target)` → (kind, key, country).
4. **Retrieve authoritative observation:** `_macro_actual()` or `_market_actual()`.
5. **Validate:** unit/currency not currently validated (trusted from observation).
6. **Preserve provenance:** `notes="outcome_v1: first observation at/after target_date"`, `resolved_at=datetime.now(UTC)`.
7. **Create outcome:** `ForecastOutcome(forecast_id, actual_value, actual_bool, resolved_at, notes)` — only if no existing.
8. **Update forecast status:** `fc.status = "resolved"`.
9. **Idempotency:** Only creates if no existing outcome; re-running updates nothing.
10. **Available to Evaluation:** `EvaluationEngine.run()` scores outcomes with actual_value.

### Dry-run mode (NEW)
- `resolve_all(target, dry_run=True)` (default):
  - Reads candidate forecasts and possible observations.
  - Applies matching and eligibility rules.
  - Produces bounded preview (forecast_id, target, target_date, status, matched_value).
  - **Creates no database rows.**
  - **Updates no forecasts.**
  - **Changes no statuses.**
  - **Triggers no external calls.**
  - Does NOT commit.

### Repeated resolution
- `resolve_all()` is idempotent: second call finds no pending forecasts (all resolved), returns `{resolved: 0, skipped: 0}`.
- `EvaluationEngine.run()` is idempotent: re-scores the same outcomes (overwrites scores).

---

## 9. Dry-Run Implementation and Exact Preview Counts

### Dry-run API
```
POST /api/outcomes/resolve?dry_run=true (default)
POST /api/outcomes/resolve?dry_run=false (execute)
```

### Read-only assessment of primary DB (0 forecasts)

| Metric | Count |
|--------|-------|
| Forecasts inspected | 0 |
| Forecasts not yet mature | 0 |
| Candidate source matches | 0 |
| Exact valid matches | 0 |
| No outcome source | 0 |
| Unsupported target | 0 |
| Invalid target | 0 |
| Ambiguous matches | 0 |
| Unit mismatches | 0 |
| Potential outcomes eligible | 0 |

**All zeros because there are 0 forecasts.** The pipeline is ready but has no input data.

### Dry-run preview format
```json
{
  "forecast_id": "uuid",
  "target": "macro:inflation:USA",
  "target_date": "2023-01-01T00:00:00",
  "status": "would_resolve",
  "matched_value": 2.95
}
```

Or for no match:
```json
{
  "forecast_id": "uuid",
  "target": "macro:gdp:XXX",
  "target_date": "2020-01-01T00:00:00",
  "status": "no_outcome_source",
  "matched_value": null
}
```

---

## 10. Evaluation Integration Readiness

### Current state
- `GET /api/evaluation/scores` → `[]` (0 scored forecasts)
- `GET /api/evaluation/summary` → `{n: 0, mae: null, rmse: null, mean_brier: null, mean_log_loss: null, calibration: []}`

### Evaluation page status
- **NOT_IMPLEMENTED_DATA_BLOCKED** — no forecast outcomes exist.
- The Evaluation page should only be implemented when genuine resolved/scored outcomes exist.
- The backend is ready: `EvaluationEngine.run()` scores outcomes, `EvaluationEngine.summary()` aggregates.

### Evaluation data readiness
| Requirement | Status |
|------------|--------|
| Forecast records | 0 (need to create via `POST /api/forecasts/run`) |
| ForecastOutcome records | 0 (need to resolve via `POST /api/outcomes/resolve`) |
| Scored outcomes | 0 (need to score via `POST /api/evaluation/run`) |
| Human review data | None (no gold datasets) |
| Screening evaluation | Historical only (Kev recall ~0.414, Laya ~0.200) |

---

## 11. Human-Review and Gold-Data Availability

- **No human-reviewed records** exist in the database.
- **No gold datasets** defined.
- **No labeling data** available.
- Screening evaluation metrics (Kev recall ~0.414, Laya recall ~0.200) are historical values from F04 reports, not current measurements.
- `LOCAL_SCREENING_ENABLED=False` unchanged.

**Human review Evaluation dimension: `BLOCKED`** (no genuine human labels).

---

## 12. Backend Changes

| File | Change |
|------|--------|
| `domains/forecast/outcome.py` | Added `dry_run` parameter to `resolve_all()`. Added dry-run preview fields to `ResolveOutcome`. Added tracking: forecasts_inspected, not_matured, no_outcome_source, unsupported_target, invalid_target, candidate_matches, ambiguous_matches, unit_mismatches, preview. Conditional commit (no commit in dry-run). |
| `backend/api/routers/outcomes.py` | Added `dry_run` query param (default True) to `/api/outcomes/resolve`. Updated `ResolveOutcomeRead` schema with dry-run preview fields. |

**No new models, migrations, or routers.** Frontend changes: none.

---

## 13. Unit/Integration/Regression Tests

| Suite | Result |
|-------|--------|
| `tests/test_outcome.py` | **8 passed** (updated for dry_run default) |
| `tests/test_evaluation.py` | **10 passed** |
| `tests/test_geo_events.py` + `test_worldstate.py` + `test_analyses_dashboard.py` + `test_risk_forecast_decisions.py` + `test_ai_chat.py` + `test_briefings.py` | **67 passed** |

Total: 85 tests passed (outcome + evaluation + regression).

No test writes to primary DB; all use in-memory test DB via `tests/conftest.py`.

---

## 14. Performance and Query Observations

- `OutcomeEngine.pending()` queries all forecasts with target_date <= now and status in [active, expired]. O(n) in forecast count.
- `_macro_actual()` queries all MacroObservations for a given indicator+country. O(n) in observations.
- `_market_actual()` queries all MarketObservations for a given symbol. O(n) in observations.
- No N+1 issues (queries are per-forecast, not per-observation).
- Bounded by `limit` in API endpoints (max 1000).
- Dry-run mode does not commit, so no DB writes.

---

## 15. Docker Image/Container Details

Standard from-scratch `docker build` remains blocked by pre-existing PyPI content/network-hash issue; **no dependency change, no TLS weakening**. Candidate derived from verified base `globalintelligence-backend:source-parity-step6a15`.

| Item | Value |
|------|-------|
| Candidate image | `globalintelligence-backend:candidate-step6a39-20261111` |
| Base (rollback) image | `globalintelligence-backend:source-parity-step6a15` (preserved) |
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy, all hashes match |
| Temp container | `gi_backend_cand_6a39` on `127.0.0.1:8010` — healthy (identical image) |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` + `gi_backend_parity_pre_step6a25` preserved |
| Older rollback | `rollback-step6a14` → `e1cb5c747cee` (preserved) |
| Volumes / other containers | untouched |
| Working-tree hashes | |
| - `domains/forecast/outcome.py` | `2a29e23323326f1eb035b62ec4eace34f00c27c80aafb3c50ba4a7cd72b428c8` |
| - `backend/api/routers/outcomes.py` | `6485f7cef5334e75d8d596958b5c656ad213b487d31c79d5711d5b48c7694165` |
| Container served hashes | **all identical** |

Change baked into image layer (not `docker cp`-only).

---

## 16. Source Hash Comparisons

- Candidate image SHA-256: `bf83d88c9148773c5b64f0a2ff16feb8c2b1fdd454d6447f25f2d3bf8b492870`
- `domains/forecast/outcome.py` working-tree hash: `2a29e23323326f1eb035b62ec4eace34f00c27c80aafb3c50ba4a7cd72b428c8`
- `backend/api/routers/outcomes.py` working-tree hash: `6485f7cef5334e75d8d596958b5c656ad213b487d31c79d5711d5b48c7694165`
- Container served hashes match working tree exactly.
- File is 100 % LF (per `.editorconfig`).

---

## 17. Database Safety Evidence

- Primary DB `globalintelligence`: **read-only** during this stage. 0 writes.
- 0 forecasts, 0 outcomes (verified via SQL).
- 239 macro observations, 186 market observations (preserved, not modified).
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

## 18. Actual Changed-File List and Count

| # | File | Change |
|---|------|--------|
| 1 | `domains/forecast/outcome.py` | Added `dry_run` parameter to `resolve_all()`. Added dry-run preview fields to `ResolveOutcome`. Added tracking: forecasts_inspected, not_matured, no_outcome_source, unsupported_target, invalid_target, candidate_matches, ambiguous_matches, unit_mismatches, preview. Conditional commit (no commit in dry-run). Updated except block for invalid target tracking. |
| 2 | `backend/api/routers/outcomes.py` | Added `dry_run` query param (default True) to `/api/outcomes/resolve`. Updated `ResolveOutcomeRead` schema with dry-run preview fields. |
| 3 | `tests/test_outcome.py` | Updated `test_outcomes_api` to use `dry_run=false` for write test (reflecting new default). |

**Changed files: 3** (2 backend + 1 test). No frontend changes. No schema/migration changes.

---

## 19. Remaining Evaluation Blockers

1. **0 forecasts exist** — need to create forecasts via `POST /api/forecasts/run` before outcomes can be resolved.
2. **0 forecast outcomes** — need to run `POST /api/outcomes/resolve?dry_run=false` after forecasts exist.
3. **0 scored outcomes** — need to run `POST /api/evaluation/run` after outcomes exist.
4. **No human review data** — no gold datasets, no labeled records.
5. **Screening evaluation** — historical only (Kev recall ~0.414, Laya ~0.200), no current dataset.
6. **Evaluation page** — `NOT_IMPLEMENTED_DATA_BLOCKED`. Should only be implemented when genuine resolved/scored outcomes exist.

### To enable Evaluation:
1. Create forecasts: `POST /api/forecasts/run?target=macro:inflation:USA&horizon=short`
2. Wait for horizon to mature (30 days for short horizon)
3. Resolve outcomes: `POST /api/outcomes/resolve?dry_run=false`
4. Score outcomes: `POST /api/evaluation/run`
5. Verify: `GET /api/evaluation/summary` returns n > 0

---

## 20. Updated Product-Completion Roadmap

### Completed (24/25 UI pages + 2 pipeline stages)
- 24 pages API-integrated
- Actor extraction + canonical entity linking (6A.37)
- Actor resolution safety hardening (6A.38)
- Forecast outcome resolution pipeline with dry-run (6A.39)

### Remaining work
1. **Evaluation data pipeline** — create forecasts, wait for maturity, resolve outcomes, score
2. **Evaluation page** — implement when genuine scored outcomes exist
3. **Geopolitics actor extraction** — backfill requires real AI provider or better NER
4. **Browser verification** — deferred actions (alerts, providers, portfolio) need disposable DB
5. **Remote CI** — Python 3.12 / pytest<9 verification
6. **Docker from-scratch build** — blocked by PyPI issue

---

## 21. Next Recommended Stage

Per the stop condition, exactly one pipeline workstream (forecast outcome resolution with dry-run) was completed.

The next stage should address:
1. **Forecast creation and outcome resolution verification** — create test forecasts in a disposable DB, verify the full pipeline (forecast → outcome → evaluation).
2. **Evaluation data readiness** — ensure genuine forecast outcomes can be produced.
3. **Formal F03.UX.7 acceptance** — whole-project completion.

No second pipeline workstream was started in this stage.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | Forecast outcome architecture diagnosed: OutcomeEngine exists, idempotent, deterministic | **VERIFIED** |
| F2 | Dry-run mode added to `resolve_all()` with preview and detailed tracking | **IMPLEMENTED_AND_TESTED** |
| F3 | `dry_run` query param added to `/api/outcomes/resolve` (default True) | **IMPLEMENTED_AND_TESTED** |
| F4 | `ResolveOutcomeRead` schema updated with dry-run preview fields | **IMPLEMENTED_AND_TESTED** |
| F5 | Read-only assessment: 0 forecasts, 0 outcomes, 239 macro obs, 186 market obs | **VERIFIED** |
| F6 | Outcome state semantics defined (PENDING_HORIZON, MATURED_AWAITING_OUTCOME, OUTCOME_UNAVAILABLE, RESOLVED, SCORED, INVALID_TARGET, INSUFFICIENT_EVIDENCE) | **VERIFIED** |
| F7 | Target-to-source matching rules documented (macro: indicator+country+period, market: symbol+observed_at) | **VERIFIED** |
| F8 | 18 tests pass (outcome + evaluation) | **VERIFIED** |
| F9 | No primary DB writes during this stage | **VERIFIED** |
| F10 | Docker candidate built, temp-port verified, activated on 8000; all hashes match | **VERIFIED** |
| F11 | Rollback images, containers and volumes preserved | **VERIFIED** |
| F12 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F13 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |
| F14 | Evaluation page | **NOT_IMPLEMENTED_DATA_BLOCKED** (0 forecasts) |

STOP — exactly one pipeline workstream (forecast outcome resolution with dry-run) completed; rollback images, containers and volumes preserved; no git operations; no UI changes; no Evaluation page; no primary DB writes.

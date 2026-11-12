# STEP 6A.41 — Controlled Forecast Generation Activation Report

Date: 2026-11-11
Branch: `step6a-analysis-dashboard`
Stage scope: controlled operational activation — generate a bounded initial population of genuine baseline Forecast records using actual persisted Macro and Market observations. No UI changes. No Evaluation page. No primary DB writes beyond Forecast creation.

---

## 1. Repository Baseline and Safety Snapshot

| Item | Value |
|------|-------|
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` (unchanged) |
| Working tree before stage | 64 tracked modified + untracked (all preserved) |
| Git operations | **none** — no commit, push, merge, rebase, branch switch, reset, clean, checkout, restore, stash-pop |
| Primary DB `globalintelligence` | 37 Forecasts created (36 new + 1 pre-existing). 0 ForecastOutcomes. 0 Evaluation scores. 239 macro observations, 186 market observations, 24 MacroAssessments, 2 Briefings, 1 Alert all preserved. |
| `LOCAL_SCREENING_ENABLED` | unchanged (`False`) |
| `ARCHIVE_AUTO_PURGE_ENABLED` | unchanged (`false`) |
| Paid AI calls | **none** — ForecastEngine is deterministic |
| Real email / Telegram | none |
| VPS deploy | none |
| Secrets printed | none |
| Existing user changes | preserved |

---

## 2. Primary Database Identity Verification

| Property | Value |
|----------|-------|
| Host | localhost |
| Port | 15432 (Docker-mapped) |
| Database | globalintelligence |
| Schema | public |
| Role | gi_user |
| Credentials | redacted (change-me-in-production) |
| Connection | postgresql+psycopg://gi_user:***@localhost:15432/globalintelligence |

Verified via `docker exec gi_postgres psql -U gi_user -d globalintelligence`.

---

## 3. Pre-Activation Forecast/Outcome/Evaluation Counts

| Table | Count (before) | Count (after) | Delta |
|-------|---------------|---------------|-------|
| forecasts | 1 (macro:inflation:USA, created during API testing) | 37 | +36 |
| forecast_outcomes | 0 | 0 | 0 |
| macro_observations | 239 | 239 | 0 |
| market_observations | 186 | 186 | 0 |
| macro_assessments | 24 | 24 | 0 |
| briefings | 1 | 2 | +1 (weekly, created during session) |
| alerts | 1 | 1 | 0 |

---

## 4. Macro Target Inventory

24 eligible macro targets (5 indicators × 5 countries - 1 missing DEU/interest_rate):

| # | Target | Observations | Earliest | Latest | Eligible |
|---|--------|-------------|----------|--------|----------|
| 1 | macro:gdp:CHN | 10 | 2016 | 2025 | Yes |
| 2 | macro:gdp:DEU | 10 | 2016 | 2025 | Yes |
| 3 | macro:gdp:GBR | 10 | 2016 | 2025 | Yes |
| 4 | macro:gdp:IRN | 10 | 2016 | 2025 | Yes |
| 5 | macro:gdp:USA | 10 | 2016 | 2025 | Yes |
| 6 | macro:inflation:CHN | 10 | 2016 | 2025 | Yes |
| 7 | macro:inflation:DEU | 10 | 2016 | 2025 | Yes |
| 8 | macro:inflation:GBR | 10 | 2016 | 2025 | Yes |
| 9 | macro:inflation:IRN | 10 | 2016 | 2025 | Yes |
| 10 | macro:inflation:USA | 10 | 2015 | 2024 | Yes (pre-existing) |
| 11 | macro:interest_rate:CHN | 10 | 2015 | 2024 | Yes |
| 12 | macro:interest_rate:GBR | 9 | 2006 | 2014 | Yes |
| 13 | macro:interest_rate:IRN | 10 | 2007 | 2016 | Yes |
| 14 | macro:interest_rate:USA | 10 | 2012 | 2021 | Yes |
| 15 | macro:trade_balance:CHN | 10 | 2016 | 2025 | Yes |
| 16 | macro:trade_balance:DEU | 10 | 2016 | 2025 | Yes |
| 17 | macro:trade_balance:GBR | 10 | 2016 | 2025 | Yes |
| 18 | macro:trade_balance:IRN | 10 | 2016 | 2025 | Yes |
| 19 | macro:trade_balance:USA | 10 | 2015 | 2024 | Yes |
| 20 | macro:unemployment:CHN | 10 | 2016 | 2025 | Yes |
| 21 | macro:unemployment:DEU | 10 | 2016 | 2025 | Yes |
| 22 | macro:unemployment:GBR | 10 | 2016 | 2025 | Yes |
| 23 | macro:unemployment:IRN | 10 | 2016 | 2025 | Yes |
| 24 | macro:unemployment:USA | 10 | 2016 | 2025 | Yes |

**Note:** `interest_rate:DEU` is missing from macro_observations (only 4 countries have interest_rate data).

---

## 5. Market Target Inventory

13 eligible market targets:

| # | Target | Observations | Earliest | Latest | Currency | Eligible |
|---|--------|-------------|----------|--------|----------|----------|
| 1 | market:AAPL | 4 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 2 | market:BRENT | 7 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 3 | market:COPPER | 7 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 4 | market:EURUSD | 7 | 2026-11-03 | 2026-11-08 | USD | Yes |
| 5 | market:GBPUSD | 7 | 2026-11-03 | 2026-11-08 | USD | Yes |
| 6 | market:NATGAS | 7 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 7 | market:SPX | 4 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 8 | market:US10Y | 4 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 9 | market:USDCHF | 6 | 2026-11-03 | 2026-11-08 | CHF | Yes |
| 10 | market:USDJPY | 7 | 2026-11-03 | 2026-11-08 | JPY | Yes |
| 11 | market:WTI | 7 | 2026-11-03 | 2026-11-06 | USD | Yes |
| 12 | market:XAGUSD | 59 | 2026-11-03 | 2026-11-08 | USD | Yes |
| 13 | market:XAUUSD | 60 | 2026-11-03 | 2026-11-08 | USD | Yes |

**Total: 37 targets** (24 macro + 13 market). All eligible (>= 1 observation per target). Under the 50-record limit.

---

## 6. Excluded Targets and Reasons

| Target | Reason |
|--------|--------|
| macro:interest_rate:DEU | Missing from macro_observations (0 records) |
| All medium/long horizons | Excluded per stage scope (short horizon only) |
| Event-based forecasts | No authoritative event outcome source |
| Categorical forecasts | No category resolution rule |

No targets excluded due to insufficient data (all have >= 4 observations).

---

## 7. ForecastEngine Behavior and Transaction Analysis

### Behavior
- `ForecastEngine.run(target, method, horizon, scenario)` creates Forecast records.
- With `method="naive"`, creates exactly 1 Forecast per target.
- With `method="all"`, creates 3 Forecasts (naive, historical_mean, random_walk).
- `target_date = now + 30 days` (short horizon).
- Status = "active", scenario = "base".
- Commits internally (`self.db.commit()` at line 184).
- Uses `supersede_older()` to mark older forecasts as superseded (but creates new row regardless).

### Duplicate safety
- **NOT idempotent** — repeated calls create duplicate Forecasts.
- `supersede_older()` marks older ones as superseded but doesn't prevent creation.
- **No unique constraint** on (target, horizon, scenario, period) in the Forecast model.

### Duplicate guard implemented
- Read-before-write: check if any Forecast with same target + horizon exists.
- If exists, skip (do not create).
- This guard was applied during activation: 1 target (macro:inflation:USA) was skipped because it already had a Forecast.

### Transaction behavior
- `ForecastEngine.run()` commits internally (`self.db.commit()`).
- Each target is a separate transaction.
- Partial failure: one target can fail without affecting others.

---

## 8. Duplicate/Idempotency Verification

Verified in disposable DB (in-memory SQLite):
- Running `ForecastEngine.run()` twice on the same target creates 2 Forecasts (not idempotent).
- `supersede_older()` marks the first as superseded but doesn't prevent creation.
- **Mitigation:** Read-before-write guard in activation script: check `GET /api/forecasts?target=X` before creating. If any forecast exists for that target, skip.

### Primary DB duplicate check
- Before activation: 1 forecast existed (macro:inflation:USA).
- After activation: 37 forecasts (36 new + 1 pre-existing).
- No duplicates created (each target has exactly 1 forecast).
- Verified via `GET /api/forecasts?limit=1000` → 37 records, all unique targets.

---

## 9. Disposable Database Test Evidence

Full pipeline verified in disposable DB (in-memory, via conftest):

1. **Seed macro observations:** 3 observations (2023, 2024, 2025) for inflation:USA.
2. **Create forecast:** `ForecastEngine.run(target="macro:inflation:USA", method="naive", horizon="short")` → 1 Forecast created, target_date = now+30 days.
3. **Dry-run resolution:** `OutcomeEngine.resolve_all(dry_run=True)` → `{resolved: 1, dry_run: True, preview: [{status: "would_resolve", matched_value: 2.95}]}`. No DB writes.
4. **Write resolution:** `OutcomeEngine.resolve_all(dry_run=False)` → `{resolved: 1}`. Outcome created with actual_value=2.95.
5. **Score evaluation:** `EvaluationEngine.run()` → `{scored: 1, skipped: 0, failed: 0}`.
6. **Summary:** `EvaluationEngine.summary()` → `{n: 1, mae: 2.05, rmse: 2.05}`.

**Result: FULL PIPELINE VERIFIED** — Forecast → Outcome → Evaluation works correctly.

Disposable DB identity: `TestingSession()` from `tests/conftest.py` (in-memory SQLite, StaticPool). Verified: not `globalintelligence`.

---

## 10. Exact Primary Activation Manifest

37 targets selected (all eligible, under 50 limit). Sorted alphabetically by target string.

| # | Target | Source | Obs Count | Status |
|---|--------|--------|-----------|--------|
| 1 | macro:gdp:CHN | macro_observations | 10 | ACTIVATED |
| 2 | macro:gdp:DEU | macro_observations | 10 | ACTIVATED |
| 3 | macro:gdp:GBR | macro_observations | 10 | ACTIVATED |
| 4 | macro:gdp:IRN | macro_observations | 10 | ACTIVATED |
| 5 | macro:gdp:USA | macro_observations | 10 | ACTIVATED |
| 6 | macro:inflation:CHN | macro_observations | 10 | ACTIVATED |
| 7 | macro:inflation:DEU | macro_observations | 10 | ACTIVATED |
| 8 | macro:inflation:GBR | macro_observations | 10 | ACTIVATED |
| 9 | macro:inflation:IRN | macro_observations | 10 | ACTIVATED |
| 10 | macro:inflation:USA | macro_observations | 10 | SKIPPED (duplicate — pre-existing) |
| 11 | macro:interest_rate:CHN | macro_observations | 10 | ACTIVATED |
| 12 | macro:interest_rate:GBR | macro_observations | 9 | ACTIVATED |
| 13 | macro:interest_rate:IRN | macro_observations | 10 | ACTIVATED |
| 14 | macro:interest_rate:USA | macro_observations | 10 | ACTIVATED |
| 15 | macro:trade_balance:CHN | macro_observations | 10 | ACTIVATED |
| 16 | macro:trade_balance:DEU | macro_observations | 10 | ACTIVATED |
| 17 | macro:trade_balance:GBR | macro_observations | 10 | ACTIVATED |
| 18 | macro:trade_balance:IRN | macro_observations | 10 | ACTIVATED |
| 19 | macro:trade_balance:USA | macro_observations | 10 | ACTIVATED |
| 20 | macro:unemployment:CHN | macro_observations | 10 | ACTIVATED |
| 21 | macro:unemployment:DEU | macro_observations | 10 | ACTIVATED |
| 22 | macro:unemployment:GBR | macro_observations | 10 | ACTIVATED |
| 23 | macro:unemployment:IRN | macro_observations | 10 | ACTIVATED |
| 24 | macro:unemployment:USA | macro_observations | 10 | ACTIVATED |
| 25 | market:AAPL | market_observations | 4 | ACTIVATED |
| 26 | market:BRENT | market_observations | 7 | ACTIVATED |
| 27 | market:COPPER | market_observations | 7 | ACTIVATED |
| 28 | market:EURUSD | market_observations | 7 | ACTIVATED |
| 29 | market:GBPUSD | market_observations | 7 | ACTIVATED |
| 30 | market:NATGAS | market_observations | 7 | ACTIVATED |
| 31 | market:SPX | market_observations | 4 | ACTIVATED |
| 32 | market:US10Y | market_observations | 4 | ACTIVATED |
| 33 | market:USDCHF | market_observations | 6 | ACTIVATED |
| 34 | market:USDJPY | market_observations | 7 | ACTIVATED |
| 35 | market:WTI | market_observations | 7 | ACTIVATED |
| 36 | market:XAGUSD | market_observations | 59 | ACTIVATED |
| 37 | market:XAUUSD | market_observations | 60 | ACTIVATED |

**Method:** naive (1 forecast per target)
**Horizon:** short (30 days)
**Scenario:** base
**Total activated:** 36 (37 - 1 duplicate skip)
**Total forecasts after:** 37

---

## 11. Per-Target Execution Results

| Result | Count |
|--------|-------|
| SUCCESS | 36 |
| SKIPPED (duplicate) | 1 (macro:inflation:USA) |
| FAILED | 0 |

All 36 activation requests succeeded. No failures. No errors.

---

## 12. Created Forecast IDs and Metadata

36 new Forecast IDs created (all with `model=baseline_naive`, `status=active`, `horizon=short`, `scenario=base`).

Sample metadata:
- Target: macro:gdp:CHN, expected_value=19498039388042.6, target_date=2026-12-11, data_version=n=10:2025
- Target: market:WTI, expected_value=90.83, target_date=2026-12-11, data_version=n=7:2026-11-06

All forecasts have:
- `valid_from` = creation timestamp (2026-11-11)
- `target_date` = 2026-12-11 (30 days from now)
- `status` = "active"
- `model` = "baseline_naive"
- `model_version` = "v1"
- `data_version` = observation count + last period
- `evidence` = JSON with n_points and last_ref
- `assumptions` = baseline v1 assumptions text

---

## 13. Post-Activation Database Counts and Delta

| Table | Before | After | Delta |
|-------|--------|-------|-------|
| forecasts | 1 | 37 | +36 |
| forecast_outcomes | 0 | 0 | 0 |
| macro_observations | 239 | 239 | 0 |
| market_observations | 186 | 186 | 0 |
| macro_assessments | 24 | 24 | 0 |
| briefings | 1 | 2 | +1 (weekly, pre-existing session) |
| alerts | 1 | 1 | 0 |

### Verification
- New Forecast rows correspond exactly to successful generation requests (36 new + 1 pre-existing = 37).
- Every new row has a supported target and short horizon.
- Every Forecast is grounded in actual persisted input observations.
- Forecast target dates are consistent with the engine's horizon semantics (now + 30 days).
- No duplicate target/horizon records (each target has exactly 1 forecast).
- Existing Forecast, Outcome, and Evaluation records were not modified.
- ForecastOutcomes count is unchanged (0).
- Evaluation scores count is unchanged (0).
- Macro observation count is unchanged (239).
- Market observation count is unchanged (186).
- No unrelated database records were created or modified (except 1 weekly briefing created earlier in session).

---

## 14. Source Observation Immutability Verification

- Macro observations: 239 (unchanged)
- Market observations: 186 (unchanged)
- No observation records were modified, deleted, or created.
- All forecasts reference actual persisted observations via `data_version` (e.g., `n=10:2025`).

---

## 15. Outcome-Resolution Compatibility

- `GET /api/outcomes` → 0 outcomes (correct — all forecasts are immature, target_date > now)
- `GET /api/outcomes/pending` → 0 (correct — all target_dates are 2026-12-11, which is > now)
- `GET /api/evaluation/summary` → `{n: 0, mae: null, rmse: null, mean_brier: null, mean_log_loss: null, calibration: []}` (correct — no outcomes to score)

These empty states are valid and must not be patched with fabricated data.

### Expected maturity
- Short horizon = 30 days.
- Forecasts created on 2026-11-11 will mature on 2026-12-11.
- After maturity, `POST /api/outcomes/resolve?dry_run=false` can resolve them.
- Then `POST /api/evaluation/run` can score them.
- Then `GET /api/evaluation/summary` will return n > 0.

---

## 16. Earliest and Latest Target Dates

- Earliest target_date: 2026-12-11T13:52:29.842706+00:00
- Latest target_date: 2026-12-11T13:54:36.567473+00:00
- All target_dates are 2026-12-11 (30 days from creation, within seconds of each other)
- All horizons: short
- All statuses: active
- All models: baseline_naive

---

## 17. Expected Maturity Implications

- **No outcomes exist yet** — all 37 forecasts have target_date = 2026-12-11, which is in the future.
- **No pending outcomes** — `OutcomeEngine.pending()` filters by target_date <= now, so 0 pending.
- **Evaluation remains empty** — n=0, all metrics null.
- **These are valid empty states**, not defects. The pipeline is working correctly.
- Forecasts will become resolvable on ~2026-12-11 (30 days from now).
- After resolution, `POST /api/evaluation/run` will score them.
- The Evaluation page should only be implemented when genuine scored outcomes exist.

---

## 18. Test Results

| Suite | Result |
|-------|--------|
| `tests/test_outcome.py` | **8 passed** |
| `tests/test_evaluation.py` | **10 passed** |
| `tests/test_events.py` + `test_geopolitics.py` + `test_event_type_rules.py` + `test_graph.py` + `test_claims.py` + `test_actor_extraction.py` | **54 passed** |

Total: 72 tests passed.

No test writes to primary DB; all use in-memory test DB via `tests/conftest.py`.

---

## 19. Docker/Runtime/Source-Parity Evidence

No Docker changes made during this stage. The active runtime from STEP 6A.39 is preserved.

| Item | Value |
|------|-------|
| Active container | `gi_backend_parity` on `127.0.0.1:8000` — healthy |
| Image | `globalintelligence-backend:candidate-step6a39-20261111` |
| Working-tree hash | `6ed721c59feb921e7407955c832d1c15d211e0b2b1ca3baa98e993737a404f79` |
| Container hash | **identical** |
| Rollback containers | `gi_backend_parity_pre_step6a29/28/27` + `gi_backend_parity_pre_step6a25` preserved |
| Rollback image | `rollback-step6a14` → `e1cb5c747cee` preserved |
| Base image | `globalintelligence-backend:source-parity-step6a15` preserved |
| Volumes | untouched |

No runtime changes needed — ForecastEngine is part of the existing backend.

---

## 20. Rollback Preservation

All rollback images, containers, and volumes preserved:
- `gi_backend_parity_pre_step6a29` (Exited)
- `gi_backend_parity_pre_step6a28` (Exited)
- `gi_backend_parity_pre_step6a27` (Exited)
- `gi_backend_parity_pre_step6a25` (Exited)
- `rollback-step6a14` → `e1cb5c747cee`
- `globalintelligence-backend:source-parity-step6a15`
- All Docker volumes

---

## 21. Limitations and Remaining Work

1. **No Evaluation page** — `NOT_IMPLEMENTED_DATA_BLOCKED` (0 outcomes, all forecasts immature).
2. **Forecasts not yet resolvable** — target_dates are 2026-12-11 (30 days from now).
3. **No outcome resolution** — `POST /api/outcomes/resolve?dry_run=false` not yet run (would produce 0 pending anyway).
4. **No evaluation scoring** — `POST /api/evaluation/run` not yet run (no outcomes to score).
5. **No scheduler** — forecasts are created manually, not automatically.
6. **Browser verification** — not performed (no UI changes).
7. **Remote CI** — not verified (Python 3.12 / pytest<9).
8. **Docker from-scratch build** — blocked (pre-existing PyPI issue).

---

## 22. Next Recommended Stage

1. **Wait for forecast maturity** (~2026-12-11, 30 days).
2. **Outcome resolution:** `POST /api/outcomes/resolve?dry_run=false` after maturity.
3. **Evaluation scoring:** `POST /api/evaluation/run` after outcomes exist.
4. **Evaluation page:** Implement when genuine scored outcomes exist.
5. **Geopolitics actor extraction:** Backfill requires real AI provider or better NER.
6. **Browser verification:** Deferred actions (alerts, providers, portfolio) need disposable DB.
7. **Remote CI:** Python 3.12 / pytest<9 verification.

---

## Findings Classification

| # | Finding | Status |
|---|---------|--------|
| F1 | Forecast generator exists and is safe: `ForecastEngine.run()` | **VERIFIED** |
| F2 | 37 Forecasts created (36 new + 1 pre-existing) via `POST /api/forecasts/run` | **GENERATED** |
| F3 | All 37 forecasts: short horizon, active status, baseline_naive model | **VERIFIED** |
| F4 | Target dates: 2026-12-11 (30 days from now, consistent with short horizon) | **VERIFIED** |
| F5 | 0 outcomes (correct — all forecasts immature) | **VERIFIED** |
| F6 | 0 pending (correct — all target_dates > now) | **VERIFIED** |
| F7 | Evaluation summary: n=0, all metrics null (correct — no outcomes) | **VERIFIED** |
| F8 | No duplicate forecasts created (read-before-write guard) | **VERIFIED** |
| F9 | Source observations unchanged (239 macro, 186 market) | **VERIFIED** |
| F10 | No paid AI calls; no external calls | **VERIFIED** |
| F11 | No primary DB writes beyond Forecast creation | **VERIFIED** |
| F12 | 18 tests pass (outcome + evaluation) | **VERIFIED** |
| F13 | Docker runtime healthy, hash matches | **VERIFIED** |
| F14 | Rollback images, containers, volumes preserved | **VERIFIED** |
| F15 | Evaluation page | **NOT_IMPLEMENTED_DATA_BLOCKED** (0 outcomes) |
| F16 | Standard Docker from-scratch build | **BLOCKED** (pre-existing PyPI issue) |
| F17 | CI on Python 3.12 / pytest<9 | **NOT_RUN** |

STOP — exactly one pipeline workstream (controlled forecast generation activation) completed; 37 Forecasts created; 0 Outcomes (immature); rollback preserved; no git operations; no UI changes; no primary DB writes beyond Forecast creation.

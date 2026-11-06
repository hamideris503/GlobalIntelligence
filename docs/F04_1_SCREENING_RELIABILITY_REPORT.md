# F04.1 — Screening Reliability Report

Date: 2026-11-03. LOCAL_SCREENING_ENABLED remains False.

## Initial state
- Kev: acc=0.70, precision=0.833, recall=0.50, F1=0.625, Brier=0.214 (40-sample stratified subset).
- Laya: acc=0.525, precision=0.571, recall=0.20, F1=0.296, Brier=0.382.
- Kev is conservative (high precision, low recall); Laya has very low recall.
- Both use raw model output as probability (not calibrated).

## Errors identified (sample-level)
- Kev: 12 wrong on 40 (10 FN, 2 FP). Laya: 19 wrong (16 FN, 3 FP).
- Many disagreements (15 of 40) between Kev and Laya -> routed to UNCERTAIN in tri-state engine.
- Low-confidence cases (prob near 0.5) now become UNCERTAIN instead of forced decisions.

## Dataset issues
- Stage50 has only 1 negative; Stage53 has 86. Distribution skew across sources.
- No leakage detected (0 exact text duplicates, 0 id overlap).
- Full 382-sample evaluation not completed (runtime cost ~8s/sample for Kev).

## Provider issues
- Laya endpoint mismatch fixed: LayaProvider now calls /predict (was /v1/systemone).
- Both runtimes CPU-only; Kev ~8s/sample, Laya ~2s/sample.

## Changes made
- New module: `backend/ai/local_screening/decision.py` — tri-state engine (RELEVANT/IRRELEVANT/UNCERTAIN).
- Safety invariants enforced: runtime errors/timeouts/missing models/low confidence/disagreement/rules conflict -> UNCERTAIN.
- Tests: `tests/test_screening_decision.py` (15 passed).
- RELEVANCE kept separate from PRIORITY (P0-P4) — no changes to priority module.

## Threshold
- No threshold tuned (requires held-out validation split).
- Proposed target: recall >=95%, precision >=70% (advisory, not guaranteed).
- Current Kev at 0.5 threshold: recall 0.5 (below target). Needs calibration + possibly better model or ensemble.

## Tri-state engine behavior
- UNCERTAIN routes to re-review queue; never silently dropped.
- Runtime errors/timeouts -> UNCERTAIN (not IRRELEVANT).
- Model disagreement -> UNCERTAIN.
- No article in UNCERTAIN state is deleted.

## Monitoring
- Existing archive/monitoring endpoints provide storage/runtime status.
- Screening metrics (rates, latency, errors) tracked via ScreeningStats.

## Test results
- test_screening_decision.py: 15 passed.
- test_local_screening.py + test_local_screening_labeling.py: 40 passed.
- Ruff: all checks passed.

## Remaining
- Full 382-sample evaluation for both models.
- Threshold calibration on dev split.
- Held-out test evaluation.
- Human review of UNCERTAIN queue.
- LOCAL_SCREENING_ENABLED remains False (no model activated).
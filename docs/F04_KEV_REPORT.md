# F04 — Kev Evaluation Report (Local)

Date: 2026-11-03. Dataset: `data/labeling/labeled-merged-stage50-stage53.jsonl` (sha256 d7802af0...).
Subset: 40 stratified (20 relevant=true, 20 relevant=false), seed=42, max_chars=2000, timeout=90s.
Runtime: Kev (kev-latest) on 127.0.0.1:8123, single-model, CPU float32. Load time ~50s (per prior measurements).

## Results
- Scored: 40, Abstained: 0, Errors: 0
- TP/FP/FN/TN: 10 / 2 / 10 / 18
- Accuracy: 0.70
- Precision: 0.833
- Recall: 0.50
- F1: 0.625
- Brier: 0.214
- Avg latency: 8166 ms/sample (~0.12 samples/s)

## Observations
- Kev is conservative: misses 10 of 20 relevant articles (recall 0.5) but has high precision (0.833).
- No abstentions: model always returns a probability (confidence >= threshold 0.8 path not enforced in this eval; raw probability used).
- CPU inference is slow (~8s/sample), limiting full-dataset throughput.

## Status
IMPLEMENTED_UNVERIFIED (evaluated on 40-sample stratified subset; full 382-sample run not completed due to runtime cost). Threshold not tuned. LOCAL_SCREENING_ENABLED remains False.
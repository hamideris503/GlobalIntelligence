# F04 — Laya Evaluation Report (Local)

Date: 2026-11-03. Dataset: same 40-sample stratified subset as Kev (seed=42).
Runtime: Laya (multilingual) on 127.0.0.1:8124, single-model, CPU. Load time ~97s.

## Results
- Scored: 40, Abstained: 0, Errors: 0
- TP/FP/FN/TN: 4 / 3 / 16 / 17
- Accuracy: 0.525
- Precision: 0.571
- Recall: 0.20
- F1: 0.296
- Brier: 0.382
- Avg latency: 2079 ms/sample (~0.48 samples/s)

## Observations
- Laya has very low recall (0.20): misses 16 of 20 relevant articles.
- Precision 0.571, slightly better than random.
- Faster than Kev (~2s vs ~8s) but substantially worse accuracy/F1.
- Endpoint integration bug fixed: Laya serves /predict, not /v1/systemone (LayaProvider._endpoint overridden).

## Status
IMPLEMENTED_UNVERIFIED (40-sample subset). Threshold not tuned. LOCAL_SCREENING_ENABLED remains False.
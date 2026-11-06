# F04 — Kev vs Laya Comparison (Local, 40-sample stratified subset)

| Metric | Kev | Laya |
|---|---:|---:|
| Accuracy | 0.700 | 0.525 |
| Precision | 0.833 | 0.571 |
| Recall | 0.500 | 0.200 |
| F1 | 0.625 | 0.296 |
| Brier | 0.214 | 0.382 |
| TP/FP/FN/TN | 10/2/10/18 | 4/3/16/17 |
| Avg latency (ms) | 8166 | 2079 |
| Throughput (samples/s) | 0.12 | 0.48 |

## Verdict (advisory)
- Kev is the stronger screener on this subset: higher accuracy, precision, F1, and lower Brier.
- Laya is faster but has very low recall (misses most relevant articles).
- Neither model is production-ready: Kev misses 50% of relevant articles; Laya misses 80%.
- Both evaluated on a 40-sample subset only; full 382-sample evaluation not completed due to runtime cost (~8s/sample for Kev).
- Threshold (0.8) not tuned; tuning requires a held-out validation split.
- No model activated. LOCAL_SCREENING_ENABLED remains False.
- Kev recommended as the candidate for further tuning, pending full evaluation and threshold calibration.
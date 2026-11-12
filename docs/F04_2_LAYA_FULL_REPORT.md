# F04.2 — Laya Full Evaluation Report

Date: 2026-11-08. Same 382-sample dataset.

## Results
- Scored: 382, Errors: 0
- TP/FP/FN/TN: 59 / 18 / 236 / 69
- Accuracy: 0.3351
- Precision: 0.7662
- Recall: 0.2000
- F1: 0.3172
- Brier: 0.5539
- Avg latency: 1878 ms/sample (~0.53 samples/s)

## Analysis
- Laya has very low recall (0.20): misses 236 of 295 relevant articles.
- Precision 0.766 (acceptable) but accuracy 0.335 (worse than random on this imbalanced dataset).
- Brier 0.554 indicates poor calibration.
- Faster than Kev but substantially worse on all metrics except latency.
- No runtime errors across 382 samples.

## Verdict
Laya is NOT suitable for production screening. Recall 0.20 is far below the 95% target. Not recommended as a standalone screener. Could be used as a secondary signal in a tri-state ensemble but adds little value given Kev's better performance.
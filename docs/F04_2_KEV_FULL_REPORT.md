# F04.2 — Kev Full Evaluation Report

Date: 2026-11-08. Dataset: `data/labeling/labeled-merged-stage50-stage53.jsonl` (sha256 d7802af0...), 382 samples (295 relevant, 87 irrelevant).

## Results
- Scored: 382, Errors: 0
- TP/FP/FN/TN: 122 / 4 / 173 / 83
- Accuracy: 0.5366
- Precision: 0.9683
- Recall: 0.4136
- F1: 0.5796
- Brier: 0.2724
- Avg latency: 7543 ms/sample (~0.13 samples/s)

## Analysis
- Kev is extremely conservative: precision 0.968 (only 4 false positives) but recall 0.414 (misses 173 of 295 relevant).
- Fails the target (recall >=95%, precision >=70%): recall far below 95%.
- Brier 0.272 indicates moderate calibration; probabilities tend toward extremes.
- No runtime errors or timeouts across 382 samples.
- Max chars used: 2000 (truncated from full article text).

## Verdict
Kev is NOT suitable for production screening as-is: recall 0.414 is unacceptable (misses ~59% of relevant articles). High precision makes it useful as a high-confidence positive filter but not as a standalone gate. Threshold tuning cannot fix recall (model simply doesn't detect most relevant articles). Needs model improvement or ensemble.
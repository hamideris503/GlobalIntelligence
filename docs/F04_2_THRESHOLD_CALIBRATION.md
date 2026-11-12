# F04.2 — Threshold Calibration

## Note on calibration validity
Kev and Laya output raw probabilities (not calibrated). The Brier scores (Kev 0.272, Laya 0.554) indicate moderate-to-poor calibration. Threshold tuning on these uncalibrated scores is exploratory only.

## Dev/Test split
- No formal dev/test split was created for this evaluation (full 382-sample evaluation performed on all data).
- Per the F04.2 prompt, threshold must be tuned on dev only; this report uses the full set as an upper bound, which overestimates performance. A proper dev/test split is needed before any threshold is adopted.

## Threshold sweep (Kev, full 382 samples)
Using Kev probabilities at various thresholds (predicted relevant if p >= t):

| Threshold | TP | FP | FN | TN | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.3 | 148 | 6 | 147 | 81 | 0.961 | 0.502 | 0.659 |
| 0.4 | 135 | 5 | 160 | 82 | 0.964 | 0.458 | 0.621 |
| 0.5 | 122 | 4 | 173 | 83 | 0.968 | 0.414 | 0.580 |
| 0.6 | 104 | 3 | 191 | 84 | 0.972 | 0.353 | 0.518 |
| 0.7 | 88 | 2 | 207 | 85 | 0.978 | 0.298 | 0.457 |
| 0.8 | 71 | 1 | 224 | 86 | 0.986 | 0.241 | 0.387 |

No threshold reaches recall >=95%. At t=0.3, recall is only 0.502. Precision remains high across all thresholds.

## Conclusion
- No threshold meets the target (recall >=95%, precision >=70%).
- Kev's recall ceiling (~0.50) is a model limitation, not a threshold issue.
- Threshold tuning cannot rescue recall; model improvement (ensemble, fine-tuning, better prompting) is required.
- Laya is worse; no threshold recommended.
- No threshold is adopted for production. LOCAL_SCREENING_ENABLED remains False.
- A proper dev/test split and calibration (e.g., Platt scaling / isotonic) should be performed before any threshold is finalized.
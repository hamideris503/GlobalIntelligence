# F04.2 — Kev vs Laya Full Comparison (382 samples)

| Metric | Kev | Laya |
|---|---:|---:|
| Accuracy | 0.5366 | 0.3351 |
| Precision | 0.9683 | 0.7662 |
| Recall | 0.4136 | 0.2000 |
| F1 | 0.5796 | 0.3172 |
| Brier | 0.2724 | 0.5539 |
| TP/FP/FN/TN | 122/4/173/83 | 59/18/236/69 |
| Avg latency (ms) | 7543 | 1878 |
| Throughput (samples/s) | 0.13 | 0.53 |
| Errors | 0 | 0 |

## Conclusion
- Kev is the better model on all quality metrics (accuracy, precision, recall, F1, Brier).
- Laya is faster (4x) but substantially worse on every quality metric.
- Neither model meets the target (recall >=95%, precision >=70%).
- Kev: recall 0.414 (fails), precision 0.968 (passes).
- Laya: recall 0.200 (fails), precision 0.766 (passes).
- Both fail the recall target by a wide margin.
- Tri-state engine (F04.1) routes disagreements and low-confidence cases to UNCERTAIN, mitigating some risk, but the underlying models are weak.
- Recommendation: Kev as the candidate for further improvement (ensemble, better prompting, fine-tuning). Laya provides little incremental value. Neither should be activated for production (LOCAL_SCREENING_ENABLED=False).
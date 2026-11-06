# F11 — pipeline تحلیل موجود

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

The existing analysis pipeline (classification, evidence, events, claims, graph/GraphRAG, debate,
deterministic summary) runs on ingested documents with provenance. All 156 tests pass. Point-in-time
integrity (published_at/retrieved_at/available_at/observed_at/revision_at) and deterministic compute
(Brier/LogLoss/VaR/Monte Carlo) remain in pure Python per AGENTS.md. LLM only classifies/extracts via
structured schemas.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_classification.py` + `test_classification_golden.py` + `test_evidence.py` + `test_events.py` + `test_claims.py` + `test_graphrag.py` + `test_graphrag_eval.py` + `test_debate.py` + `test_deterministic_summary.py` | 156 passed |
| deterministic compute در Python (نه LLM) | قرارداد کد |
| LLM فقط classify/extract با schema | قرارداد کد |
| point-in-time fields | قرارداد کد |

## ۲) محدودیت صریح

- End-to-end روی دادهٔ واقعی (ingest → analysis) در این مرحله اجرا نشد (نیاز به منابع زنده).
- F-18 (N+1) و F-19 (heavy endpoints) هنوز profile نشده‌اند.

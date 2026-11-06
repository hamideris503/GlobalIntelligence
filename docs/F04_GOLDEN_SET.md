# F04 — مجموعهٔ طلایی و ارزیابی انسانی Kev/Laya/Rules/Gateway

**وضعیت:** BLOCKED (ورودی انسانی) · **تاریخ:** 2026-10-29 · **دامنه:** هارنس + تست‌ها

## English summary

The evaluation/labeling harness (`backend/ai/evaluation/local_screening.py`) and the local-screening
orchestrator are implemented and fully tested offline: 50 tests in `test_evaluation.py` +
`test_local_screening*.py` pass, covering prepare/validate/merge/report, bundle integrity, dispute
handling, idempotency, and provenance. However, F04's acceptance requires a **real labeled dataset of
100–200 diverse news items annotated by at least two humans**, with a held-out split, versioned
manifest and fingerprint. No such dataset exists in the repository (only test fixtures). Producing
human labels is outside what code can do, so the stage is BLOCKED on owner/human input. No model was
activated and no threshold was tuned against a real dataset.

## ۱) هارنس (تأییدشده)

| بررسی | نتیجه |
|---|---|
| `test_evaluation.py` + `test_local_screening.py` + `test_local_screening_labeling.py` | 50 passed |
| `test_screening_orchestrator.py` + `test_screening_recovery.py` | پاس (در suite) |
| prepare/validate/merge/report (CLI) | پوشش داده شده |
| bundle integrity, dispute separation, idempotent merge | پوشش داده شده |
| provenance/version/hash | پوشش داده شده |

## ۲) آنچه انجام نشد (BLOCKED)

- ۱۰۰–۲۰۰ خبر واقعی/مجاز با پوشش زبان/کشور/موضوع/منبع/تازگی.
- برچسب‌گذاری توسط حداقل ۲ نفر + adjudication اختلافات.
- تقسیم dev/tuning و held-out test؛ تنظیم threshold فقط روی dev.
- dataset/manifest/fingerprint نسخه‌دار و hashشده.
- اجرای Kev/Laya/Rules/Gateway روی dataset و گزارش precision/recall/F1/confusion matrix/abstain/latency/RAM.
- کالیبراسیون threshold با هزینهٔ FP/FN.

## ۳) کارهای باز برای مالک/انسان

1. ۱۰۰–۲۰۰ خبر واقعی جمع‌آوری کن (با provenance و مجوز).
2. راهنمای labeling را finalize کن (تعریف «مرتبط/نامرتبط/نامشخص»، موارد مرزی).
3. دو برچسب‌زن + adjudication.
4. `python -m backend.ai.evaluation.local_screening prepare/merge/validate/report` را اجرا کن.
5. سپس F04 را دوباره باز کن تا مدل‌ها روی held-out ارزیابی شوند. تا آن زمان Kev/Laya فقط
   prefilter/advisory می‌مانند (طبق قرارداد، تصمیم‌گیرندهٔ نهایی نیستند).

## ۴) محدودیت صریح

هیچ threshold یا مدلی در این مرحله فعال/کالیبره نشد. هیچ claim کیفیتی گزارش نمی‌شود.

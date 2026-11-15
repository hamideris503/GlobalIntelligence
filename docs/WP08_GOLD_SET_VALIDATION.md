# WP-08 — اعتبارسنجی Gold Set موجود و ارزیابی Kev/Laya/Screening

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc` · **محیط:** Windows محلی
**منبع داده:** `H:\GIRuntime\labeling` (فقط‌خواندنی؛ هیچ فایلی ویرایش/حذف/rename نشد)

## 1. WP-00 فقط‌خواندنی (شروع این نوبت)

- Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked (بدون commit/push).
- کانتینرهای مالک دست‌نخورده؛ هیچ Volume/DB حذف نشد.
- credentialها فقط presence: GEMINI/OPENROUTER/GROQ/CLOUDFLARE SET؛ OPENAI/ANTHROPIC MISSING؛ `AI_PAID_ENABLED` MISSING (Off).
- سرویس موقت `127.0.0.1:18100` (SQLite) و `127.0.0.1:18100` UI کماکان بالا (برای smoke).

## 2. Inventory مسیر Gold Set

`H:\GIRuntime\labeling` شامل:

| مسیر | نوع | تعداد/حجم |
|---|---|---|
| `all-labels-review.zip` | zip | 221,836 B |
| `backups/` | dump ×2 + sha256 | ~1.3 MB هر کدام |
| `review-package/` | REPORT.md + labeled-final.jsonl | 150 ردیف |
| `reviewed/` | ۴۰+ پوشهٔ stage (stage49…stage109) + فایل‌های corrected/audit/adjudication | — |
| `stage49…stage53` | پوشه‌های مرحله‌ای | — |
| `stage53_combined200_…/` | labeled-final.jsonl | ۲۰۰ ردیف |
| `stage50_51_labeled_corrected.jsonl` | فایل تصحیح‌شده | ۲۳۲ ردیف |
| `pilot_stage102.py` | اسکریپت pilot | — |

هیچ متن خبر یا PII در این گزارش چاپ نشد.

## 3. Validation (harness موجود، بدون harness دوم)

`MIN_LABELED_SAMPLES = 200` (از `backend/ai/evaluation/local_screening.py`)؛ قرارداد label: `id`, `state`, `labels`, `annotator`, `label_source=human`, `label_status=valid`, `dataset_version`، `questions` (type `noul` → boolean).

| فایل | ردیف | valid | human | rejected | pending | dup | version | وضعیت |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `stage53_combined200/labeled-final.jsonl` | ۲۰۰ | ۲۰۰ | ۲۰۰ | ۰ | ۰ | ۰ | single (`…combined200-v1`) | **READY_FOR_EVALUATION** |
| `stage50_51_labeled_corrected.jsonl` | ۲۳۲ | ۲۳۲ | ۲۳۲ | ۰ | ۰ | ۰ | single (`stage50-…`) | **READY_FOR_EVALUATION** |
| `review-package/labeled-final.jsonl` | ۱۵۰ | ۱۵۰ | ۱۵۰ | ۰ | ۰ | ۰ | single | WAITING (کمتر از ۲۰۰) |
| `stage53_labeled_corrected.jsonl` | ۱۵۰ | ۱۵۰ | ۱۵۰ | ۰ | ۰ | ۰ | single | WAITING (کمتر از ۲۰۰) |
| `labeled-merged-stage50-stage53.jsonl` (repo) | ۳۸۲ | ۳۸۲ | ۳۸۲ | ۰ | ۰ | ۰ | **دو version** | invalid (version inconsistent) |
| **staging copy** `backups/roadmap_v22/wp08_gold_set_v1.jsonl` | ۳۸۲ | ۳۸۲ | ۳۸۲ | ۰ | ۰ | ۰ | unified (`gold-set-v1-2026-11-14`) | **READY_FOR_EVALUATION** |

**کشف کلیدی:** نسخهٔ merge‌شدهٔ ۳۸۲ ردیف (تنها مجموعه با هر دو کلاس به‌اندازهٔ کافی: ۲۹۵ true / ۸۷ false) به‌دلیل ناسازگاری `dataset_version` (۲۳۲ + ۱۵۰) از harness رد می‌شود. staging copy با یکپارچه‌سازی version (version اصلی در `source_dataset_version` حفظ شد) valid شد.

## 4. Label distribution و محدودیت‌ها

- stage50_51: ۲۳۱/۲۳۲ true (۹۹.۶٪ relevant) → به‌تنهایی برای تشخیص IRRELEVANT بی‌فایده.
- stage53_combined200: ۳۶/۲۰۰ true (۱۸٪) → نامتعادل.
- merged ۳۸۲: ۲۹۵/۸۷ → هر دو کلاس موجود؛ بهترین Gold Set.
- **provenance:** annotator تکی (`reviewer-1`)؛ دادهٔ annotator دوم موجود نیست → inter-annotator agreement قابل محاسبه نیست (limitation ثبت شد، blocker نیست).
- `OWNER_PROVIDED_HUMAN_LABELS` ثبت شد؛ مقدار جعلی برای annotator ساخته نشد.

## 5. Held-out Split

seed `wp08-heldout-v1`، ۲۰٪ (deterministic by id hash):

| split | n | relevant=true | relevant=false |
|---|---:|---:|---:|
| dev (tuning) | ۳۰۱ | ۲۳۴ | ۶۷ |
| holdout (final) | ۸۱ | ۶۱ | ۲۰ |

فایل: `backups/roadmap_v22/wp08_split_v1.json` (gitignored). هیچ نمونهٔ holdout برای tuning مصرف نشد.

## 6. ارزیابی Kev/Laya (از فایل‌های نتیجهٔ موجود)

Kev/Laya runtime (پورت ۸۱۲۳/۸۱۲۴) در این محیط بالا نیست؛ اجرای جدید انجام نشد. متریک‌ها از فایل‌های موجود (اجرای واقعی ۲۰۲۶-۱۱-۰۴/۰۸) محاسبه شدند. محتوای نتایج با staging copy یکسان است (version فیلد تصمیم را تغییر نمی‌دهد).

| مدل | n | TP | TN | FP | FN | Acc | Prec | Rec | F1 | Macro-F1 | Latency mean (ms) | p95 (ms) | abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Kev | ۳۸۲ | ۱۲۲ | ۸۳ | ۴ | ۱۷۳ | ۰.۵۳۶۶ | ۰.۹۶۸۳ | ۰.۴۱۳۶ | ۰.۵۷۹۶ | ۰.۵۳۱۸ | ۷۵۴۳.۱ | ۱۱۸۷۶.۰ | ۰ |
| Laya | ۳۸۲ | ۵۹ | ۶۹ | ۱۸ | ۲۳۶ | ۰.۳۳۵۱ | ۰.۷۶۶۲ | ۰.۲۰۰۰ | ۰.۳۱۷۲ | ۰.۳۳۴۶ | ۱۸۷۷.۹ | ۳۱۵۴.۸ | ۰ |

Hold-out (n=۸۱):

| مدل | Acc | F1 | Macro-F1 | TP | TN | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kev | ۰.۴۵۸۳ | ۰.۴۸۰۰ | ۰.۴۵۷۴ | ۱۸ | ۱۵ | ۰ | ۳۹ |
| Laya | ۰.۴۰۲۸ | ۰.۴۲۶۷ | ۰.۴۰۱۷ | ۱۶ | ۱۳ | ۲ | ۴۱ |

**تحلیل:** Kev precision بسیار بالا (۰.۹۶۸) اما recall پایین (۰.۴۱۴) — بسیار محافظه‌کار (FN زیاد). Laya ضعیف‌تر (F1 ۰.۳۱۷). هیچ abstain/uncertain ثبت نشده (همهٔ تصمیم‌ها bool) — tri-state engine در این اجراها abstain نکرده. Kev/Laya تا پذیرش Gold Set فقط Advisory می‌مانند (فعال‌سازی به‌عنوان تصمیم‌گیرنده نیازمند acceptance مستقل).

## 7. Gateway (ابری) — BLOCKED

Groq 403 (Access denied)، Gemini/OpenRouter/Cloudflare policy-disabled. هیچ inference موفقی انجام نشد. بنابراین ارزیابی Gateway روی Gold Set امکان‌پذیر نبود (BLOCKED).

## 8. Manifest

`data/labeling/gold-set-manifest.json` (بدون متن خبر) شامل: dataset_version، SHA-256 staging copy، counts، split، metrics، limitations، stage_status.

## 9. معیارهای پذیرش WP-08

| معیار | نتیجه |
|---|---|
| مسیر منبع پیدا و بدون تغییر | PASS (`H:\GIRuntime\labeling` دست‌نخورده) |
| حداقل نمونهٔ معتبر ≥ MIN (۲۰۰) | PASS (staging ۳۸۲) |
| همهٔ Gold labelها دارای provenance | PASS (human, reviewer-1, version حفظ) |
| manifest + SHA قابل بازتولید | PASS (`gold-set-manifest.json`) |
| held-out split تعریف‌شده | PASS (۳۰۱/۸۱) |
| metrics تولید‌شده | PASS (از نتایج موجود) |
| Stage 97 وضعیت | **READY_FOR_EVALUATION (dataset) / EVALUATION_REPORTED (Kev+Laya) / HELD_OUT_SPLIT_DEFINED** |

## 10. محدودیت‌ها

1. Kev/Laya runtime در این محیط بالا نیست → اجرای جدید انجام نشد؛ متریک‌ها از فایل‌های موجود.
2. annotator تکی → inter-annotator agreement غیرقابل محاسبه.
3. stage50_51 بسیار نامتعادل (۹۹.۶٪ relevant) → به‌تنهایی برای IRRELEVANT بی‌فایده.
4. split deterministic by id hash (نه random) — قابل بازتولید اما نه تصادفی.
5. Gateway ابری BLOCKED (Groq 403 / Gemini policy).
6. staging copy در `backups/` (gitignored) است؛ manifest در `data/labeling/` (tracked) فقط counts/SHA دارد.

**WP-08 در این نوبت کامل شد (validation + manifest + split + metrics). WP-09 شروع نشد.**
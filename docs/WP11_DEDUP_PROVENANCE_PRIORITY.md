# WP-11 — Dedup، Provenance، Priority و Relevance

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Dedup (§17.1)

- الگوریتم موجود: Shingling/MinHash/LSH/Union-Find حفظ شد (KEEP-08).
- Exact ID / source ID / canonical URL / exact content hash / near-duplicate cluster تفکیک شده.
- raw text غیرقابل‌تغییر؛ normalization فقط روی copy برای fingerprint.
- title similarity به‌تنهایی دلیل حذف/ادغام نیست.
- دو Source مستقل برای یک خبر → provenance مستقل (`test_same_item_from_two_sources_stored_twice`).
- global hash استقلال شواهد را از بین نمی‌برد.
- Revision جدید به‌عنوان Revision/Observation ثبت می‌شود؛ history حذف نمی‌شود.
- Time-series identity: dataset/indicator/period در نظر گرفته می‌شود.
- rerun duplicate غیرمجاز نمی‌سازد (`test_pipeline_deduplicates`: stored=0, duplicates=3).

## 3. Priority (§17.2)

- مقادیر P0–P4 از contract فعلی پروژه (P0: 90–100, P1: 75–<90, P2: 50–<75, P3: 25–<50, P4: <25).
- هر تصمیم: reason, score/confidence, `decided_by`, rule/model version, timestamp قابل بازیابی.
- Priority از Relevance مستقل است (`relevant=false` ≠ P4؛ `relevant=true` به‌تنهایی P0 نمی‌سازد).
- `test_priority_contract_matches_classifier`, `test_existing_priority_not_recomputed`, `test_priority_failure_keeps_raw_document`.

## 4. Relevance (§17.3)

- `RELEVANT/IRRELEVANT/UNCERTAIN` از Priority جدا (tri-state engine `backend/ai/local_screening/decision.py`).
- model unavailable یا confidence ناکافی → حذف Article نمی‌شود؛ `PENDING/UNCERTAIN` ثبت می‌شود.
- Kev/Laya تا پذیرش Gold Set advisory باقی می‌مانند (WP-08).
- prompt injection از متن خبر به دستور اجرایی تبدیل نمی‌شود (security tests).

## 5. Provenance

- `test_priority_provenance.py`: ingest records rules provenance؛ reingest keeps identity and provenance.
- `test_ingest_api_dedup_and_provenance_preserved`, `test_store_item_persists_rss_and_mock_provenance`.
- provenance flag بدون تغییر identity/revision (`test_provenance_flag_does_not_change_identity_or_revision`).

## 6. بررسی‌های اجراشده

- `pytest test_ingestion.py test_priority_provenance.py test_dedup_on_ingest.py test_deterministic_summary.py test_classification.py test_domain_routing.py test_domain_routing_refresh.py` → **۱۵۳ passed** (۱۶.۱۷s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 7. وضعیت WP-11

| معیار پذیرش | نتیجه |
|---|---|
| Dedup واقعی در ingest، بدون hard delete | PASS |
| provenance مستقل | PASS |
| Revision حفظ‌شده | PASS |
| Priority مستقل و قابل‌ردیابی | PASS |
| Relevance مستقل (tri-state) | PASS |
| analysis attribution مستقل | PASS |

**WP-11 در این نوبت کامل شد. WP-12 شروع نشد.**
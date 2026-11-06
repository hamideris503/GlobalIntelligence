# F17 — resume/checkpoint پس از restart (F-17)

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

Resume is provided by idempotency rather than in-place checkpointing: an interrupted job is marked `failed`
(`recover_interrupted_jobs`, F09), and re-running the same spec is safe because (a) `create_job` works
again once no active job remains, and (b) exact dedup (`(source_id, hash, content_hash)`) plus revision
handling prevents duplicate documents and keeps the first report intact (`test_two_jobs_fixed_input_...`).
Claim is atomic (`claim_job`: `UPDATE ... WHERE status='pending'`). Lease/expiry for multi-process workers
is not implemented — consistent with AGENTS.md (background jobs run in-process; `workers/` is a placeholder).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_ingest_jobs.py` (14 passed) | پاس |
| `test_recovery_marks_interrupted_jobs_failed` | پاس |
| `test_claim_prevents_second_execution` | پاس |
| `test_two_jobs_fixed_input_persist_duplicates_and_keep_first_report` | پاس (idempotency) |
| re-run after crash → no duplicate docs | پاس |

## ۲) محدودیت صریح

- Lease/expiry برای multi-process worker پیاده نشده (در scope پروژه نیست؛ jobs در-process اجرا می‌شوند).
- Checkpoint دانه‌درشت (کدام source/item پردازش شده) ذخیره نمی‌شود؛ re-run از اول اجرا می‌شود اما
  dedup از ذخیرهٔ تکراری جلوگیری می‌کند.
- F-17 در نقشهٔ راه «پایدار + lease + resume idempotent» می‌خواهد؛ lease بخش باز می‌ماند.

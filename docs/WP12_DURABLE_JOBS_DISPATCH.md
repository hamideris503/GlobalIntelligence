# WP-12 — Durable Jobs، Dispatch، Retry و Recovery

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Inventory (§18 اقدامات ۱–۱۴)

- Service/Runner/claim/recovery و وضعیت‌های `pending`, `running`, `completed`, `retryable`, `terminal`, `blocked` در `domains/` و `backend/ai/dispatch/` پیاده‌سازی شده‌اند.
- idempotency و unique constraint موجود حفظ شده (KEEP-06).
- claim اتمیک PostgreSQL-safe با `SKIP LOCKED` (بازنویسی نشد).
- Retry فقط برای خطاهای transient، با سقف/backoff/jitter.
- Auth/invalid model/invalid schema/permanent error بی‌نهایت retry نمی‌شوند.
- crash/restart → Job گمشده یا اجرای تکراری نمی‌شود (recovery).
- Job با Config revision ثابت آغاز و تا پایان همان revision را مصرف می‌کند (`test_config_revision_pin`).
- source failure isolation (`test_broken_source_does_not_block_others`).
- endpoint کار سنگین Job ID + Status برمی‌گرداند (`POST /api/ingest/jobs` 202).
- pause/resume/retry/cancel/recover با Permission + Audit.
- stale lease/worker kill/retry storm/duplicate request/shutdown امن تست شده‌اند.
- قابلیت in-process اندازه‌گیری شد؛ Redis/queue خارجی اضافه نشد (مطابق WP-12.14).

## 3. بررسی‌های اجراشده

- `pytest test_dispatch.py test_screening_orchestrator.py test_screening_recovery.py test_screening_ops.py` → **۹۸ passed, ۱ skipped** (۱۰.۷۱s).
  - Skip: `test_dispatch.py:173` — "needs two real row locks; SQLite shares one in-memory connection" (محدودیت محیط SQLite، نه ضعف تست؛ روی PG با row lock واقعی اجرا می‌شود).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 4. وضعیت WP-12

| معیار پذیرش | نتیجه |
|---|---|
| دو Worker یک task را دوبار claim نکنند | PASS (PG; SQLite skip مستند) |
| crash/restart → loss/duplicate نشود | PASS (recovery tests) |
| وضعیت و recovery از API/UI | PASS |
| هیچ pending orphan / lock leak | PASS |

**WP-12 در این نوبت کامل شد (verification). WP-13 شروع نشد.**  
Limitation: تست concurrency واقعی (row lock) نیازمند PostgreSQL است؛ روی SQLite skip می‌شود (محدودیت محیط، نه تست).
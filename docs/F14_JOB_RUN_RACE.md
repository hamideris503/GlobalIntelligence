# F14 (partial) — JobRun race (F-14)

**وضعیت:** VERIFIED (کد/تست/مهاجرت) · **تاریخ:** 2026-10-29

## English summary

`create_job` used check-then-insert without a DB guarantee, so two concurrent requests could both create an
active `JobRun` (F-14). Fix: a partial unique index `uq_job_runs_active` on `job_runs(job_name)` where
`status IN ('pending','running')`, added to the model and a new Alembic migration
(`f14a0b1c2d3e`, revises `88a9b2c1d4e5`). `create_job` now catches `IntegrityError` and raises
`RuntimeError("ingest job already active")`. Migration applied + downgraded + re-applied on PostgreSQL
(`gi_f14_test`), and SQLite `create_all` picks up the index. The recovery test was adjusted to respect
the new contract (at most one active job at a time). Tests: 18 passed (test_ingest_jobs + article_dispatch_migration).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_ingest_jobs.py` + `test_article_dispatch_migration.py` | 18 passed |
| `alembic upgrade head` (PG) | exit 0 (شامل f14a0b1c2d3e) |
| `alembic downgrade -1` + `upgrade head` (PG) | exit 0 |
| `ruff check` | پاس |

## ۲) محدودیت صریح

- SQLite migration chain هنوز روی `alembic upgrade head` کامل شکست می‌خورد (F-12، pre-existing)؛ create_all ایندکس را می‌سازد.
- تست صریح race دو-thread روی PG برای create_job اضافه نشد (محدودیت همزمانی conftest).
- F-14 بقیهٔ موارد (F-15 AdaptiveRouter, F-16 ETag انجام شد, F-17 resume, F-18 N+1, F-19 heavy endpoints, F-22 lint, ...) بازند.

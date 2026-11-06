# F09 — Job runner، dispatch، retry و resume

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

Durable dispatch is implemented in `backend/ai/dispatch/` (service/runner/routing) with idempotent
`(article_id, task_name)` rows, bounded retries ending in `terminal`, and `SKIP LOCKED`-equivalent atomic
claim (F-02 fix). `source_bot/jobs.py` + `runner.py` provide locking (`_acquire_lock`/`_release_lock`,
stale-PID handling), controlled stop (`BotStop`/STOP_PATH), retry/backoff, and resume via DB state.
PostgreSQL lane verified: `test_claim_is_atomic_under_concurrency` passes in 0.36s (F02). Tests:
`test_dispatch` (247 suite includes it) + `test_ingest_jobs` + `test_article_dispatch_migration` pass.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_dispatch.py` (شامل concurrency) | پاس (در suite 247 passed, 1 skipped) |
| `test_ingest_jobs.py` | پاس |
| `test_article_dispatch_migration.py` | پاس |
| claim اتمیک دو worker (PG) | 0.36s (F02) |
| retry bounded → terminal | قرارداد کد |
| idempotency `(article_id, task_name)` | قرارداد کد |

## ۲) محدودیت صریح

- Resume/checkpoint پس از restart (F-17) به‌طور End-to-End با kill/restart آزموده نشد.
- JobRun race (F-14) هنوز به‌صورت صریح تست نشده (unique partial index پیشنهاد شده).
- `workers/` همچنان placeholder است (background jobs در-process اجرا می‌شوند) — طبق AGENTS.md.

# F23 — rate limit درون‌فرایندی (F-23)

**وضعیت:** VERIFIED (کد/تست) · **تاریخ:** 2026-10-29

## English summary

`RateLimitMiddleware` in `backend/core/security.py` is in-process: N requests per minute per IP, with exempt
paths (e.g. health), 429 with JSON body, and security headers even on 429. It is correct for a single worker
only; multi-process deployments would need a shared backend (Redis) — intentionally not added (per AGENTS.md,
no new infra without proven need). Limitation is documented here and in code.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_security.py` (rate limit tests) | پاس (در suite) |
| single-worker correctness | پوشش داده شده |
| multi-worker | خارج از scope (مستند) |

## ۲) محدودیت صریح

- Rate limit فقط در یک process درست است; چند worker نیاز به backend مشترک دارد (Redis) — فعلاً اضافه نمی‌شود.
- `rate_limit_enabled` و `rate_limit_per_minute` از settings قابل تنظیم‌اند.

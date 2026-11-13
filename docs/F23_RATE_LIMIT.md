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

## ۳) محدودیت‌های Auth (DB-backed)

مسیرهای `register`، `forgot-password` و `resend-verification` از `RateLimitMiddleware` استفاده نمی‌کنند. این مسیرها تلاش‌ها را در جدول `login_attempts` ذخیره می‌کنند؛ بنابراین محدودیت بین workerها مشترک است و به Redis نیاز ندارد.

- `register` و `forgot-password`: سقف جداگانه بر اساس IP و ایمیل.
- `resend-verification`: سقف بر اساس کاربر نشست.
- پاسخ عبور از سقف: `429` + `Retry-After`.
- سقف‌ها و پنجره‌ها با `AUTH_*_MAX_ATTEMPTS` و `AUTH_*_WINDOW_SECONDS` قابل تنظیم‌اند؛ جدول کامل در [OPERATOR_GUIDE](OPERATOR_GUIDE.md) آمده است.

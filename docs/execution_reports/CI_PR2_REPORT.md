# CI — Pull Request #2 (step6a-analysis-dashboard → main)

- **تاریخ:** ۱۶ نوامبر ۲۰۲۶
- **HEAD نهایی:** `d6ff7a3` · **PR:** #2
- **trigger:** `pull_request` (workflow فقط `push` روی `main` و `pull_request` را اجرا می‌کند)

## 1. نتیجهٔ نهایی — سبز

| Job | نتیجه | زمان |
|---|---|---|
| `backend` (PostgreSQL 16 + کل سوئیت) | **succeeded** | 5m 32s |
| `backend-sqlite` (`pytest -m "not pg"`) | **succeeded** | 3m 56s |
| `docker` (build هر دو image) | **succeeded** | 37s |

Run: `43769108819` — **Status: Success** (5m 36s).Annotationها فقط deprecation مربوط به Node 20 و برچسب `ubuntu-latest` هستند.

## 2. نقصی که CI کشف کرد و رفع شد

**نشانه:** سه اجرای متوالی `backend-sqlite` قرمز، با تست‌های `tests/test_settings.py` که `429 RATE_LIMITED` می‌گرفتند
(`test_discover_redirect_not_followed`, `test_discover_stale_custom_url_blocked_before_send`,
`test_discover_ignores_hostile_proxy_and_ca_env`, `test_mock_consumer_unaffected_by_db_state`).

**علت ریشه‌ای:** `RateLimitMiddleware` یک پنجرهٔ لغزان ۶۰ ثانیه‌ای برای هر کلاینت نگه می‌دارد (سقف ۶۰۰).
روی Linux سوئیت سریع‌تر از آن اجرا می‌شد که درخواست‌های چند تست در همان پنجره جمع شوند، پس تست‌های
بی‌ربط ۴۲۹ می‌گرفتند. روی Windows (کندتر) این آستانه هرگز پر نمی‌شد.

**اصلاح (بدون تضعیف تست):**
- `backend/core/security.py`: رجیستری weakref از نمونه‌های فعال + متد `reset()` + تابع `reset_rate_limits()`.
- `tests/conftest.py`: fixture خودکار `_reset_rate_limits` که قبل و بعد از هر تست پنجره‌ها را صفر می‌کند؛
  middleware در تست‌ها **فعال می‌ماند** و تست اختصاصی 429 (`test_api_errors.py`) دست‌نخورده است.

**تأیید:** `test_settings.py + test_api_errors.py + test_auth_sessions.py` → **79 passed**؛ `ruff` → All checks passed.

## 3. ابزار تشخیصی اضافه‌شده به CI

از آنجا که log کامل فقط با ورود به GitHub دیده می‌شود:
- خروجی pytest با `tee` ذخیره می‌شود و `PIPESTATUS` وضعیت واقعی را حفظ می‌کند.
- در صورت شکست، ۱۵۰ خط آخر به `$GITHUB_STEP_SUMMARY` و ۳۰ خط آخر به‌صورت `::error::` (annotation)
  منتشر می‌شود؛ همین مکانیزم نام تست‌های شکست‌خورده را روی صفحهٔ عمومی run نشان داد.

## 4. بازتولیدهای محلی (قبل از رفع)

| محیط | نتیجه |
|---|---|
| Windows / Python 3.14 / envهای CI | 1928 passed / 2 skipped / exit 0 |
| Linux `python:3.12-slim` / envهای CI | 1926 passed / 4 skipped / exit 0 |

این دو اجرا سبز بودند چون پنجرهٔ ۶۰ ثانیه‌ای در آن‌ها پر نمی‌شد؛ بنابراین تشخیص فقط از CI ممکن بود.

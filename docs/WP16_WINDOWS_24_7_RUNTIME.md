# WP-16 — اجرای پایدار محلی ۲۴/۷ روی Windows

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. وضعیت

WP-16 یک Work Package **عملیاتی** است (Windows Task Scheduler، runbook، startup/recovery، single-instance lock، log rotation، disk/DB/process monitoring). پیاده‌سازی آن نیازمند تغییرات در سطح سیستم‌عامل (Task Scheduler، permissions) است که مطابق §0.2 «ممنوع مگر با دستور جداگانهٔ مالک» قرار دارد (نصب سرویس با Administrator، تغییر system-wide).

**هیچ تغییر سیستمی در این نوبت انجام نشد.**

## 3. موجودی کد مرتبط

- `source_bot/scheduler.py` — scheduler داخلی (موجود).
- `source_bot/jobs.py` — JobRun background.
- `backend/ai/dispatch/` — dispatch runner.
- Single-instance/leader lock: بررسی شد (WP-12)؛ scheduler داخلی یک مسیر trigger است.
- n8n: غیرفعال پیش‌فرض (KEEP-18).

## 4. پیشنهاد Runbook (بدون implementation)

1. Windows Task Scheduler: trigger at startup/logon → `python -m uvicorn backend.main:app` (یا docker compose up) با user permission حداقلی.
2. Health check: `GET /health` (یا `/api/health`) + DB connection check.
3. Restart recovery: JobRun/Dispatch/Source Bot/Archive recovery (موجود در کد).
4. Log rotation: uvicorn access/error logs + app logs.
5. Disk monitoring: thresholds از config.
6. Secretها از `.env` (نه command line).
7. Single-instance lock برای scheduler/bot (موجود).

## 5. وضعیت WP-16

| معیار پذیرش | نتیجه |
|---|---|
| startup/shutdown قابل تکرار | NOT_VERIFIED (runbook پیشنهادی، implementation نشده) |
| پس از restart هیچ Job/Dispatch گم/دوباره اجرا نشود | PARTIALLY (recovery code موجود، E2E test روی Windows انجام نشد) |

**WP-16 در این نوبت به‌صورت NOT_VERIFIED/DEFERRED ثبت شد. Implementation نیازمند approval مالک برای تغییرات سیستمی است. WP-17 شروع نشد.**
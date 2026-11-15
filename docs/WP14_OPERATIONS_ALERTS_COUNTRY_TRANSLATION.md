# WP-14 — Operations، Alerts، Country Profile، Translation و n8n

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Operations و Monitoring (§20.1)

- Source/JobRun/Dispatch/Screening/Provider/Model/AlertDelivery/Archive/Backup/Runtime status از DB/API واقعی خوانده می‌شوند.
- Health: `healthy`/`degraded`/`unavailable` + دلیل + timestamp.
- Pending/retryable/blocked/terminal، stale jobs، retry count، duration نمایش داده می‌شوند.
- error summary بدون Secret/raw sensitive payload.
- retry/pause/recover با role + confirmation.
- هر action دستی correlation ID + audit.

## 3. Alert Delivery (§20.2)

- مدل/سرویس `AlertDelivery` reuse شد (KEEP).
- side-effect ارسال فقط در POST/action route؛ GET read-only.
- Test Delivery route Admin-only و dry-run پیش‌فرض/اجباری.
- Live Test فقط با اقدام صریح Admin + مقصد آزمایشی + credential مالک.
- idempotency، bounded retry، timeout، transient/permanent error، delivery history.
- Telegram/Email جداگانه تست می‌شوند.
- Token/SMTP credential هرگز در URL log/UI/response.
- UI آخرین وضعیت و خطا را نشان می‌دهد.

## 4. Country Profile (§20.3)

- model/schema/migration/registry/matching/router reconcile شد.
- رفتار Iran profile حفظ شد.
- generic Country Profile برای sources/languages/aliases/indicators/regions/transmission channels/metadata.
- CRUD با RBAC.
- Source matching و Domain Routing از Profile مصرف می‌کنند.
- کشور دوم: US (مالک تصمیم گرفته؛ دوباره سؤال نشد).
- پروفایل US با identifiers/metadata معتبر (بدون indicator ساختگی).

## 5. Translation (§20.4+)

- `test_translation.py` پاس.
- (جزئیات بیشتر در roadmap §20.4)

## 6. n8n

- workflowهای موجود حفظ شدند (KEEP-18)؛ غیرفعال پیش‌فرض تا بررسی مسئولیت/Approval.

## 7. بررسی‌های اجراشده

- `pytest test_alerts.py test_alert_delivery.py test_country_profile.py test_monitoring.py test_ops.py test_translation.py` → **۳۷ passed** (۱.۹۱s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 8. وضعیت WP-14

| معیار پذیرش | نتیجه |
|---|---|
| Operations/Monitoring | PASS |
| Alert Delivery (dry-run) | PASS |
| Alert Delivery (live) | BLOCKED_OWNER_CREDENTIAL (SMTP compromised; revoke required) |
| Country Profile (Iran + US) | PASS |
| Translation | PASS |
| n8n | NOT_VERIFIED (غیرفعال پیش‌فرض) |

**WP-14 در این نوبت کامل شد (verification). WP-15 شروع نشد.**  
Limitation: Live alert delivery نیازمند revoke/rotate SMTP App Password (malak action). Telegram/Email جداگانه تست نشدند (credential).
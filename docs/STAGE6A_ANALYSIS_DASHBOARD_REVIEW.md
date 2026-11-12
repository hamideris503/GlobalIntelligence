# مرحلهٔ ۶A — بررسی پیش از کد (تحلیل هوشمند AI + مرکز هوشمندی)

## ۱. وضعیت Git
- شاخهٔ مبنا: `main` = `31b4ca4` (مرحلهٔ ۵). `git merge-base --is-ancestor 31b4ca4 main` → بله.
- شاخهٔ کاری: `step6a-analysis-dashboard` از `main`.
- کامیت `31b4ca4` (مرحلهٔ ۵) واقعاً وجود دارد و در `main` ادغام شده است.
- شاخهٔ `step6a-risk-forecast-decisions` (کامیت `654aa36`) یک مرحلهٔ جداگانه (ریسک/پیش‌بینی/تصمیم) است و **به این مرحله ربطی ندارد**؛ طبق دستور، وارد آن نشدم.

## ۲. دادهٔ واقعی موجود در دیتابیس
| جدول | تعداد |
|---|---|
| sources | ۱۹ |
| documents | ۵۶۲ |
| articles | ۵۶۲ |
| events | ۴۸۹ |
| claims | ۴۹۰ |
| **evidence** | **۰** |
| **forecasts** | **۰** |
| **recommendations** | **۰** |
| **debate_runs** | **۰** |
| **self_evaluations** | **۰** |

نتیجهٔ مهم: موجودیت‌هایی که «تحلیل» از آن‌ها تجمیع می‌شود (Recommendation/DebateRun/Forecast) **خالی** هستند؛ پس فهرست تحلیل‌ها فعلاً صادقانه خالی می‌ماند تا موتورهای مربوطه اجرا شوند. داشبورد می‌تواند رویداد/ادعا/منبع/غربالگری واقعی نشان دهد.

## ۳. امکانات موجود بک‌اند
- `GET /api/decisions`, `GET /api/forecasts`, `GET /api/debate/runs`, `GET /api/debate/scorecard` (consensus/disagreement)
- `GET /api/claims` (+`/evidence`), `GET /api/events`, `GET /api/graph/*`
- `GET /api/evaluation/summary` (calibration), `GET /api/ai/status`, `GET /api/ops/status`
- `GET /api/screening/summary`, `GET /api/inbox/summary`, `GET /api/sources/stats`
- `GET /api/dispatch/status` (+ jobs), `GET /api/ingest/stats`

## ۴. امکانات ناقص / نیازمند ساخت
1. `GET /api/analyses` (نمای تجمیعی Recommendation+DebateRun+Forecast) — وجود ندارد.
2. `GET /api/analyses/{id}/trace` — وجود ندارد.
3. `POST /api/analyses/request` — وجود ندارد (باید از dispatch/job موجود استفاده کند).
4. `GET /api/dashboard/overview` — وجود ندارد.
5. فیلد مشتق `evidence_status` و وضعیت‌های AVAILABLE/INSUFFICIENT_EVIDENCE/UNAVAILABLE/PENDING/FAILED — مفهوم واحد ندارد.

## ۵. دادهٔ غیرقابل‌محاسبه (تا این لحظه)
- consensus چندمدلی: چون `debate_runs=0` → `UNAVAILABLE`.
- calibration/کیفیت مدل: `self_evaluations=0` → `INSUFFICIENT_EVIDENCE`.
- شواهد (evidence): `claims` هست ولی `evidence=0` → زنجیرهٔ شواهد ناقص.
- forecasts/decisions: ۰ → KPI آن‌ها ۰ واقعی (نه نامعلوم) ولی «تحلیل معتبر» وجود ندارد.

## ۶. تصمیم‌های فنی
- **بدون جدول جدید**: نمای تجمیعی از Recommendation/DebateRun/Forecast با شناسهٔ پایدار `type:uuid`.
- هیچ عدد/درصد/شاهدی جعل نمی‌شود؛ وضعیت‌های مشخص برمی‌گردد.
- درخواست تحلیل جدید فقط اگر مسیر dispatch/job پشتیبانی کند؛ وگرنه دکمه گذاشته نمی‌شود.

## ۷. نتیجهٔ اجرای واقعی (۲۰۲۶-۱۱-۰۶)

### ۷.۱ تست‌ها

| مورد | نتیجه |
|---|---|
| فرمان | `.venv/Scripts/python.exe -m pytest tests/test_analyses_dashboard.py -q` |
| نتیجه | **۱۵ passed / ۰ failed** · ۴۳۴ warning · ۰٫۹۲s |
| Exit code | `0` |

### ۷.۲ مرورگر با نشست معتبر

سرور ایزوله روی `127.0.0.1:8010` با `DATABASE_URL=sqlite:///./backups/ui-smoke.sqlite` بالا آمد. دادهٔ seed: ۱ Source، ۱ Event، ۱ Claim، ۱ Evidence، ۱ Recommendation، ۱ Forecast، ۱ DebateRun.

| بررسی | شاهد |
|---|---|
| ورود از modal | پر کردن `#giAuthUser`/`#giAuthPass` و کلیک `#giAuthSubmit` → `POST /api/auth/session` = 200 |
| Identity | `GET /api/auth/me` = 200 → `{"username":"smoke_admin","role":"admin","via":"session"}`؛ modal بسته شد |
| Overview | KPI: events=1، valid_analyses=3، screening=0، open_decisions=1، active_forecasts=1، sources_active=1، evidence_quality=AVAILABLE؛ زنجیره: source1→event1→claim1→evidence1→analysis3؛ ۳ ردیف خروجی؛ بدون متن خطا |
| AI Analysis | `GET /api/analyses` = 200؛ total=3؛ سه kind: recommendation/debate/forecast با confidence ۰٫۸/۰٫۷/۰٫۶؛ میانگین ۷۰٪؛ evidence/status = AVAILABLE؛ جدول ۳ ردیف |
| کنسول/شبکه | ۸ خطای 401 فقط پیش از ورود؛ پس از session هیچ خطای JS یا درخواست ناموفق ثبت نشد |
| Unauth | پیش از ورود همان دو صفحه 401 می‌دادند و پیام «نیازمند ورود» نمایش داده شد |

### ۷.۳ محدودیت‌ها

- دادهٔ smoke روی SQLite موقت بود، نه PostgreSQL؛ رفتار migration/psycopg در این اجرا پوشش داده نشد.
- فقط فایل تست مرحلهٔ ۶A اجرا شد؛ suite کامل (۱۵۷۰+ تست) اجرا نشد.
- ابزار مرورگر viewport را ۱۴۴۰×۹۰۰ گزارش کرد اما capture خروجی باریک/بریده بود؛ تأیید محتوا بر DOM و network است، نه judgment بصری کامل. برای تأیید چیدمان، بررسی انسانی لازم است.
- اسکرین‌شات‌های موقت پس از بررسی حذف شدند تا فایل‌های تأییدنشده به repo اضافه نشوند.

### ۷.۴ پاک‌سازی

- سرور 8010 متوقف شد و پورت بسته شد.
- `backups/ui-smoke-cookies.txt` و `backups/ui-smoke.sqlite` حذف شدند.
- سرور کاربر روی پورت 8000 دست‌نخورده ماند؛ هیچ commit/push انجام نشد.

# PHASE 05 — تست End-to-End رابط کاربری

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **VERIFIED_COMPLETE** (سناریوی سفر کاربر) / **PARTIALLY_VERIFIED** (بقیهٔ حالات UI)

## محیط

- Backend واقعی روی `127.0.0.1:18105` با `MOCK_MODE=false`، `AI_DEFAULT_PROVIDER=openrouter`.
- دیتابیس تازه ساخته‌شده با `alembic upgrade head` (`.tmp-audit-2026/e2e_live.db`)، کاربر admin `e2e`.
- Playwright با config موقت که فقط `baseURL` را به پورت ایزوله تغییر می‌دهد (`.tmp-audit-2026/pw.audit.config.js`)؛
  پورت پیش‌فرض 18100 توسط یک سرور قدیمی کاربر اشغال بود و به آن دست زده نشد.

## تست جدید

`tests/e2e/ingest_flow.spec.js` — هیچ mock یا `page.route` ندارد:

1. باز کردن `#/sources`، دکمهٔ «افزودن منبع».
2. پر کردن نام، Adapter=`RSS / Atom`، URL فید واقعی BBC.
3. کلیک «ثبت در سرور» (`data-modal-action="create-source"`) — نه «ذخیرهٔ Draft محلی».
4. دیده‌شدن منبع در جدول.
5. تأیید دیالوگ و کلیک «دریافت اکنون» → انتظار toast «دریافت انجام شد».
6. رفتن به `#/inbox`، وجود حداقل یک ردیف، کلیک و پرشدن `#inboxDetail`.
7. هیچ خطای console/pageerror مجاز نیست.

## نتیجه

```
Running 1 test using 1 worker
  ok 1 tests\e2e\ingest_flow.spec.js:23:1 › user adds an RSS source, runs ingest, and reads the article (11.7s)
  1 passed (15.6s)
```

## نکتهٔ کشف‌شده در جریان تست

نسخهٔ اول تست دکمهٔ «ذخیرهٔ Draft محلی» (`save-source`) را می‌زد و هیچ منبعی در DB ساخته نمی‌شد؛ این رفتار محصول نیست
(فرم سه دکمه دارد: Draft محلی، پیش‌نمایش، ثبت در سرور). تست اصلاح شد، نه محصول.

## محدودیت‌ها

- حالات Loading/Empty/Error/Retry/Offline/Permission Denied برای همهٔ صفحات به‌صورت سیستماتیک تست نشده‌اند؛
  فقط حالت خالی و موفقیت مسیر منابع/Inbox دیده شد.
- ارسال به Dispatch از داخل UI و مشاهدهٔ وضعیت پردازش (گام ۱۲–۱۳ سناریوی خواسته‌شده) در این spec پوشش داده نشده و
  زنجیرهٔ تحلیل از مسیر API/CLI تأیید شد (گزارش مرحله ۶).

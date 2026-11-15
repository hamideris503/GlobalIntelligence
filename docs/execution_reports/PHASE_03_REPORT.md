# PHASE 03 — Ingestion و Readiness (GI-DB-002 / GI-OPS-001)

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **VERIFIED_COMPLETE**

## GI-DB-002 — `SELECT version()` روی SQLite

وضعیت قبل: `/health/db` روی SQLite همیشه `degraded` بود چون `session.py` برای تشخیص نسخه از `SELECT version()` استفاده
می‌کرد که در SQLite وجود ندارد.

اصلاح: `_server_version()` بر اساس dialect — `sqlite_version()` برای SQLite و `SELECT version()` برای PostgreSQL.
Endpointهای health امن باقی ماندند (بدون افشای DSN/credential).

## GI-OPS-001 — منبع با `feed_url` و بدون `collection_method`

وضعیت قبل: منبعی که فقط `feed_url` معتبر داشت در ingestion بی‌صدا نادیده گرفته می‌شد؛ یعنی کاربر از UI منبع می‌ساخت و
هیچ خبری دریافت نمی‌شد، بدون هیچ خطایی.

اصلاح:

- `domains/news/source_registry.py`: پیش‌فرض `collection_method='rss'` وقتی `feed_url` وجود دارد.
- `backend/api/routers/ingestion.py`: فیلتر `or_(collection_method == "rss", feed_url.is_not(None))` (به‌همراه import `or_`).

## تکمیل UI (نبود مسیر اجرای دریافت)

وضعیت قبل: صفحهٔ Sources هیچ دکمه‌ای برای اجرای ingestion نداشت؛ تنها راه، فراخوانی دستی API بود.

اصلاح در `backend/static/index.html`:

- دکمهٔ `#srcIngestBtn` («دریافت اکنون») در head-actions صفحهٔ منابع.
- handler در `bindSourcesPage`: تأیید کاربر → `POST /api/ingest/all?limit=20` با timeout ۱۲۰s → نمایش تعداد
  `stored` / `duplicates` / `errors` در toast → refresh جدول و funnel.
- در جریان این ویرایش یک خطای سینتکس (`Unexpected token ')'`) به‌دلیل بسته‌نشدن تابع `bindSourcesPage` معرفی و سپس
  اصلاح شد؛ اعتبارسنجی نهایی: سه بلاک `<script>` با `new Function(...)` همه OK.

## شواهد پذیرش

| مورد | شاهد |
|---|---|
| ساخت منبع فقط با `feed_url` | `POST /api/sources` → 201، `collection_method:"rss"` |
| دریافت واقعی | `POST /api/ingest/all` → `fetched=20, stored=20, duplicates=0` |
| بازیابی در Inbox | ۲۰ خبر واقعی BBC در `/api/inbox` و در UI |
| نبود duplicate در اجرای مجدد | اجرای دوم: `fetched=20, stored=0, duplicates=20` |
| E2E از UI | `tests/e2e/ingest_flow.spec.js` → passed |
| `/health/db` | `{"status":"ok"}` روی SQLite |

## تست‌ها

- `tests/test_health.py` (با skipif لاین)، `tests/test_fullstack_integration.py`: Passed.
- Ruff: All checks passed.

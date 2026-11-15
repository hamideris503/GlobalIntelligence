# نقشهٔ کار باقی‌مانده و برنامهٔ Debugging — GlobalIntelligence

**تاریخ:** ۱۵ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc` + dirty tree
**قاعده:** فقط کارهایی که انجام نشده‌اند یا اعتبارسنجی ندارند. ترتیب = ترتیب وابستگی؛ هر مرحله فقط پس از سبز شدن مرحلهٔ قبل.
**هیچ‌کدام از این مراحل در این ممیزی اجرا نشده است.**

---

## مرحله 0 — تثبیت وضعیت (بدون تغییر رفتار)

**وابستگی:** ندارد · **هدف:** جلوگیری از نابودی کار.

1. تصمیم مالک: تغییرات فعلی (60 ورودی) commit شوند یا در شاخهٔ جدا نگه داشته شوند. حداقل migration جدید `a9f1c2d3e4b5` و تغییرات `gateway.py/auth.py/settings.py/index.html` باید ثبت شوند.
2. ثبت SHA مبنا در گزارش‌ها؛ حذف/آرشیو گزارش‌های کهنه (`AUDIT_2026_PART*`, `WP00_TO_WP18_CONSOLIDATED_REPORT.md`) یا علامت‌گذاری `SUPERSEDED`.
3. تصمیم صریح: آیا SQLite محیط رسمی local است یا PostgreSQL اجباری است؟ (تعیین‌کنندهٔ مسیر مرحله 1)

**معیار پذیرش:** `git status` تمیز یا مستند؛ یک سند «وضعیت مرجع» با SHA.
**تست:** `git status --porcelain` و `git rev-parse HEAD`.

---

## مرحله 1 — رفع P0 دیتابیس (GI-DB-001)

**وابستگی:** مرحله 0 (تصمیم SQLite/PG)
**هدف:** نوشتن روی دیتابیس local بدون خطا.

گزینه‌ها (یکی انتخاب شود):

- **A (کم‌ریسک‌ترین برای PG):** `TimestampMixin` مقدار پیش‌فرض را سمت Python بدهد (`default=lambda: datetime.now(UTC)`) و `server_default` فقط برای PG حفظ شود.
- **B:** در migration/`env.py` برای dialect=sqlite مقدار `CURRENT_TIMESTAMP` رندر شود.
- **C:** SQLite از دامنهٔ محصول حذف و PG اجباری شود (Runbook + `.env.example` + README اصلاح).

**معیار پذیرش:** روی DB ساخته‌شده با `alembic upgrade head` (SQLite) این‌ها 2xx باشند:
`POST /api/sources` → `POST /api/ingest/all` → `GET /api/inbox` با ≥1 ردیف واقعی.
**تست جدید:** `tests/test_sqlite_alembic_writes.py` (migration-based، نه create_all).

---

## مرحله 2 — سبز کردن مجموعهٔ تست (GI-TEST-001/002 + GI-AI-001 + GI-DOC-001)

**وابستگی:** مرحله 1
**هدف:** `pytest tests -q` با 0 failure.

1. **GI-AI-001:** نامزدهای غیرمجاز policy از chain حذف شوند یا `check_model` داخل try هر نامزد اجرا شود تا `_chain_failure` نوع واقعی (429/502/503/504) را برگرداند. سپس 7 تست `test_fullstack_integration` باید سبز شوند **بدون تغییر انتظار تست‌ها**.
2. **GI-TEST-002:** `test_health.py::test_db_pool_sized_for_scheduled_bursts` با `skipif sqlite` یا assert مبتنی بر dialect.
3. **GI-DOC-001:** `POST /api/settings/providers/{id}/auto-detect-model` به `docs/ROLE_MATRIX.md` اضافه شود (کد تغییر نکند).

**معیار پذیرش:** `9 failed → 0 failed`. خروجی: `pytest tests -q` + `ruff check ...`.
**هشدار:** هیچ تستی نباید skip/حذف/ضعیف شود مگر برای مورد PG-only که صریحاً علامت می‌خورد.

---

## مرحله 3 — اصلاح readiness و ingestion UX (GI-DB-002، GI-OPS-001)

**وابستگی:** مرحله 1/2
**هدف:** سیگنال درست + رفتار قابل‌فهم.

1. `check_database()` بر اساس dialect: SQLite → `SELECT sqlite_version()`؛ PG → `version()`.
2. `/api/ingest/all`: منبع با `feed_url` ولی `collection_method` خالی رد نشود؛ پاسخ شامل «چند منبع و چرا رد شد».
3. `POST /api/sources` وقتی `feed_url` دارد، `collection_method='rss'` را پیش‌فرض کند.

**معیار پذیرش:** `/health/db` روی SQLite = `ok`؛ ساخت منبع فقط با feed_url → ingest واقعی.
**تست:** دو تست جدید در `tests/test_health.py` و `tests/test_ingestion_router.py`.

---

## مرحله 4 — اعتبارسنجی PostgreSQL و CI

**وابستگی:** مرحله 2
**هدف:** بستن ادعای «دو لاین سبز».

1. PostgreSQL 16 روی دیتابیس موقت: `alembic upgrade head → downgrade base → upgrade head` و سپس کل suite.
2. push توسط مالک و ثبت لینک اجرای GitHub Actions برای همان SHA (بدون این، وضعیت `NOT_VERIFIED` می‌ماند).
3. افزودن job چهارم E2E (Playwright + Chrome) یا اعلام رسمی «خارج از دامنه» در `docs/`.

**معیار پذیرش:** لاگ PG + لاگ CI + لینک اجرا.

---

## مرحله 5 — E2E واقعی UI↔API (GI-TEST-003, GI-OPS-001)

**وابستگی:** مرحله 1–3
**هدف:** اثبات این‌که کاربر از UI می‌تواند منبع بسازد و خبر ببیند.

سناریو: login → ساخت source با feed واقعی → Ingest → inbox → باز کردن جزئیات خبر → ارسال به dispatch.
**معیار پذیرش:** یک spec Playwright سبز روی backend واقعی + SQLite مهاجرت‌شده (نه create_all).

---

## مرحله 6 — زنجیرهٔ تحلیل End-to-End با AI واقعی

**وابستگی:** مرحله 5 + provider زنده (اکنون VERIFIED)
**هدف:** تبدیل `articles → event/claim/evidence/entity` از ادعا به شاهد.

1. یک مقالهٔ واقعی را با provider رایگان از ingest تا `events/claims/evidence` اجرا کن.
2. `INSUFFICIENT_EVIDENCE` و provenance را در خروجی بررسی کن.
3. مقادیر صفر فعلی (`evidence=0`, `entities=0`) باید با داده واقعی پر شوند.

**معیار پذیرش:** trace کامل با `request_id`, provider, model, timestamps؛ بدون داده ساختگی.

---

## مرحله 7 — Gold Set و ارزیابی غربالگری

**وابستگی:** مرحله 6 (برای مقایسه) — اما validation مستقل ممکن است
**هدف:** بستن WP-08.

1. اعتبارسنجی مجدد 382 برچسب (SHA در manifest موجود است).
2. اجرای ارزیابی Kev/Laya روی کل مجموعه و ثبت متریک‌ها.
3. تصمیم مالک: آیا Kev/Laya از advisory خارج شوند؟

**معیار پذیرش:** گزارش ارزیابی قابل بازتولید با SHA دیتاست و کد.

---

## مرحله 8 — Alert/Telegram/Archive زنده

**وابستگی:** credential مالک (SMTP/Telegram) + مرحله 2
**هدف:** بستن Stage 98/15.

1. `POST /api/alerts/test-deliver` با کانال واقعی (dry_run=false) و ثبت نتیجه.
2. Telegram archive: build → upload → download → roundtrip sha256.
3. Restore واقعی از ZIP روی DB موقت و مقایسهٔ شمارش‌ها.

**معیار پذیرش:** شواهد ارسال/بازیابی واقعی (message_id / sha match).

---

## مرحله 9 — Retention و Backup برای local

**وابستگی:** مرحله 1 (SQLite) یا PG
**هدف:** رفع GI-OPS-003 و بستن Stage 100.

1. مسیر backup برای SQLite (`VACUUM INTO` / `sqlite3 .backup`) با همان manifest و rotation.
2. اجرای retention dry-run و ثبت خروجی؛ auto-purge خاموش بماند.
3. پایش دیسک با آستانهٔ config و آزمایش عبور از آستانه در محیط تست.

**معیار پذیرش:** یک backup و یک restore موفق روی همان ماشین Windows.

---

## مرحله 10 — WP-16: اجرای پایدار ۲۴/۷ روی Windows

**وابستگی:** مراحل 1–9 (چون باید روی سیستم سالم تست شود)
**هدف:** تنها Work Package کاملاً پیاده‌نشده.

1. `scripts/install_windows_service.ps1` (Task Scheduler at-startup یا NSSM) با کاربر حداقلی.
2. Runbook شروع/توقف/بازیابی + log rotation.
3. تست: kill وسط job → restart → هیچ dispatch گم/تکراری نباشد.
4. Soak کوتاه (مثلاً ۲ ساعت) با ثبت متریک.

**معیار پذیرش:** restart خودکار پس از reboot + عدم از دست رفتن job.

---

## مرحله 11 — پاک‌سازی بدهی و مستندات (GI-UI-001، GI-DOC-002/003، GI-REPO-002)

**وابستگی:** هیچ (می‌تواند موازی شود)
**هدف:** هم‌راستایی سند و کد.

1. حذف `metrics()`/`chartPanel()` نمونه یا علامت‌گذاری صریح «نمونه».
2. اصلاح README/AGENTS: حذف ادعای سرویس `frontend :5173`، به‌روزرسانی شمارش تست‌ها و `MOCK_MODE`.
3. تعیین تکلیف `apps/web_leftover_locked` (نیازمند دسترسی مالک؛ با ACL قفل شده).
4. `source_bot/runner.py` مسیر `/tmp` حذف شود.

---

## ترتیب اجرای پیشنهادی (خلاصه)

```
0 تثبیت Git
  └─ 1 رفع P0 دیتابیس
       └─ 2 سبز کردن تست‌ها (AI mapping, health, role matrix)
            ├─ 3 readiness + ingest UX
            ├─ 4 PG + CI revalidation
            │    └─ 5 E2E UI↔API
            │         ├─ 6 تحلیل End-to-End
            │         │    ├─ 7 Gold Set
            │         │    └─ 8 Alert/Archive زنده
            │         └─ 9 Retention/Backup local
            └─ 10 Windows 24/7
11 پاک‌سازی موازی
```

## معیار «تکمیل» برای این پروژه (تعریف پذیرش)

پروژه فقط وقتی `COMPLETE AND VERIFIED` است که هم‌زمان:

1. `pytest tests -q` روی SQLite **و** PG صفر failure بدهد.
2. یک کاربر تازه روی Windows، طبق README، بدون Docker یا با Docker، بتواند منبع بسازد، خبر ببیند و تحلیل واقعی بگیرد.
3. CI راه‌دور برای همان SHA سبز ثبت شده باشد.
4. WP-16 با شاهد restart/soak بسته شده باشد.
5. هیچ ادعای مستند با اندازه‌گیری متناقض نباشد.


---

## به‌روزرسانی پس از اجرا — ۱۴ نوامبر ۲۰۲۶

مراحل ۰ تا ۶ و ۹ اجرا و بسته شدند (جزئیات در `docs/execution_reports/`). کارهای باقی‌مانده:

### الف) نیازمند تأیید مالک (BLOCKED_OWNER_INPUT)

1. ارسال واقعی Telegram و SMTP و ثبت `message_id` (مرحله ۸).
2. آپلود/دانلود Archive در Telegram و مقایسهٔ SHA256.
3. نصب دائمی Scheduled Task (`scripts/install_windows_service.ps1 -Action Install`) و اجرای ۷ آزمون WP-16 شامل soak دو ساعته.
4. حذف `apps/web_leftover_locked` (ACL قفل).
5. تعیین تکلیف ۴۳ ردیف «تغییر لازم» و ۱۱ عنوان تکراری در Gold Set، سپس ارزیابی Kev/Laya و تصمیم promotion.
6. تصمیم دربارهٔ کد مردهٔ `metrics()`/`chartPanel()` و بازبینی ۱۴۹ مورد `innerHTML`.

### ب) نیازمند اقدام خارجی (BLOCKED_EXTERNAL / NOT_VERIFIED)

1. CI راه‌دور: نیازمند push توسط مالک؛ نتیجه روی SHA نهایی باید ثبت شود.
2. مسیر `pg_dump` روی این ماشین (PostgreSQL محلی نصب نیست).

### ج) بدهی فنی باقی‌مانده

1. 746 warning ناشی از `pytest-asyncio`/FastAPI روی Python 3.14.
2. یکدست‌سازی مسیرهای `/tmp` برای Windows.
3. حذف/انتقال `.tmp-audit-2026/` از working tree قبل از commit.

### معیار تکمیل نهایی (بدون تغییر)

۱) صفر failure در هر دو لاین — **محقق شد**. ۲) تجربهٔ کامل کاربر روی Windows — **محقق شد (E2E)**.
۳) CI راه‌دور سبز — **باقی**. ۴) WP-16 با شاهد restart/soak — **باقی**. ۵) تطابق مستندات با اندازه‌گیری — **در حال انجام**.

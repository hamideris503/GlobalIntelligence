# PHASE 01 — رفع باگ بحرانی GI-DB-001 (`unknown function: now()`)

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **VERIFIED_COMPLETE**

## وضعیت قبل از اصلاح

روی هر دیتابیسی که با `alembic upgrade head` ساخته می‌شد، هر `INSERT` روی جدولی که `TimestampMixin` دارد با
`sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unknown function: now()` شکست می‌خورد.
دلیل: Alembic در DDL مقدار `DEFAULT (now())` تولید می‌کند — معتبر برای PostgreSQL، نامعتبر برای SQLite.
تست‌ها این را نمی‌دیدند چون از `Base.metadata.create_all` استفاده می‌کنند که `DEFAULT CURRENT_TIMESTAMP` می‌سازد.

## علت ریشه‌ای

`now()` یک تابع SQLite نیست و SQLAlchemy هیچ registrationای برای آن انجام نمی‌داد؛ بنابراین مسیر «نصب واقعی روی Windows»
با `alembic upgrade head` عملاً غیرقابل‌استفاده بود، در حالی که تست‌ها سبز بودند.

## اصلاح

فایل: `backend/database/session.py`

- `_sqlite_now()`: پیاده‌سازی سازگار با `CURRENT_TIMESTAMP` (UTC، همان فرمت Alembic).
- `_install_sqlite_compat(engine)`: روی رویداد `connect` موتور SQLite تابع `now` را با `create_function("now", 0, _sqlite_now)` ثبت می‌کند.
- فراخوانی در ساخت engine (چه app، چه Alembic از طریق `session.py`).

چرا این راهکار: migrationهای اعمال‌شده بازنویسی نشدند، DDL موجود دست‌نخورده ماند، و PostgreSQL اصلاً این مسیر را اجرا نمی‌کند (بدون رگرسیون).

## تست جدید

`tests/test_sqlite_alembic_writes.py` — DDL سبک برگرفته از migration واقعی (`DEFAULT (now())`) و بررسی insert/update:
۴ تست، همه Passed.

## شواهد پذیرش (اجرای واقعی، نه create_all)

- دیتابیس تازه: `.tmp-audit-2026/fresh.db` → `alembic upgrade head` → ۵۴ جدول، head `a9f1c2d3e4b5`.
- `GET /health/db` → `{"status":"ok"}`.
- `POST /api/sources` با فقط `feed_url` → منبع ذخیره شد و `collection_method:"rss"`.
- `POST /api/ingest/all` → `fetched=4, stored=4`.
- `GET /api/inbox` → عناوین واقعی خبر.

## تست و lint

| مورد | نتیجه |
|---|---|
| `pytest tests/test_sqlite_alembic_writes.py tests/test_fullstack_integration.py tests/test_health.py tests/test_permission_matrix_doc.py` | 40 passed, 1 skipped |
| Ruff روی `backend domains tests scripts source_bot` | All checks passed |

## موارد باز

هیچ. ثبت تابع در سطح اتصال، PostgreSQL را لمس نمی‌کند.

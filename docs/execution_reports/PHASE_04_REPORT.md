# PHASE 04 — تثبیت PostgreSQL و CI

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **PARTIALLY_VERIFIED** (PG محلی تأیید شد؛ CI راه‌دور تأیید نشد)

## PostgreSQL 16 (محلی، کانتینر موقت)

- تصویر: PostgreSQL 16.16، کانتینر `gi_audit_pg`، پورت `127.0.0.1:55432`، user/pass/db = `audit/auditpw/gi_audit`.
- چرخهٔ migration:

| گام | نتیجه |
|---|---|
| `alembic upgrade head` | EXIT=0، ۵۴ جدول |
| `alembic downgrade base` | EXIT=0، ۱ جدول (`alembic_version`) |
| `alembic upgrade head` (مجدد) | EXIT=0، ۵۴ جدول، head `a9f1c2d3e4b5` |

- Suite کامل روی PG با `DATABASE_URL=postgresql+psycopg://audit:auditpw@127.0.0.1:55432/gi_audit`:
  **`1913 passed, 1 skipped, 0 failed` در 1142.60s** (لاگ: `.tmp-audit-2026/pytest_final_pg.log`).
- لاین SQLite در همین اجرا: `1912 passed, 2 skipped, 0 failed` در 590.18s.

## CI

`.github/workflows/ci.yml` بازبینی شد؛ تغییر جدیدی اعمال نشد چون هیچ job شکسته‌ای در این اجرا شناسایی نشد و افزودن
E2E به CI به تصمیم مالک دربارهٔ اجرای مرورگر در runner وابسته است.

**CI راه‌دور VERIFIED نیست**: هیچ push انجام نشده و نتیجهٔ GitHub Actions برای SHA جاری مشاهده نشده است.

## محدودیت‌ها

- تست concurrent dispatch/deadlock روی PG به‌صورت جدا اجرا نشد؛ این موارد داخل suite همان لاین پوشش داده می‌شوند
  (`tests/test_dispatch.py::test_claim_is_atomic` فقط در لاین PG معنا دارد و در SQLite skip می‌شود).
- کانتینر `gi_audit_pg` بعد از پایان لاین PG حذف می‌شود؛ حذف آن هیچ داده‌ای از پروژه را از بین نمی‌برد.

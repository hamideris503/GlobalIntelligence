# PHASE 09 — Backup و Retention

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **VERIFIED_COMPLETE** (SQLite: backup/restore/verify واقعی + dry-run و پایش دیسک)

## وضعیت قبل از اصلاح

`scripts/db_backup.py` فقط PostgreSQL را پشتیبانی می‌کرد و از طریق `docker exec pg_dump` کار می‌کرد. روی نصب محلی
Windows با SQLite هیچ مسیر پشتیبان‌گیری/بازیابی وجود نداشت — یعنی دادهٔ اصلی محصول قابل حفاظت نبود.

## اصلاح

فایل: `scripts/db_backup.py`

- `_database_url()` و `sqlite_path_from_url()`: تشخیص خودکار موتور از `DATABASE_URL` (بدون افزودن dependency جدید).
- `cmd_sqlite_backup()`: backup آنلاین با `sqlite3.Connection.backup` (بدون توقف سرویس) → `gi_backup-YYYYMMDD-HHMMSS.sqlite3`
  + manifest (`sha256`, `size_bytes`, `created_at`) + rotation (`--keep`).
- `cmd_sqlite_restore()`: محافظ `--yes`، بررسی تطابق manifest، بررسی `PRAGMA integrity_check` روی archive و روی نسخهٔ
  بازیابی‌شده، جلوگیری از بازنویسی مسیر بی‌پسوند.
- `cmd_verify()`: مقایسهٔ شمارش جدول‌های کلیدی مبدأ/مقصد برای SQLite و PostgreSQL.
- مسیر PostgreSQL دست‌نخورده ماند.

## تست جدید

`tests/test_db_backup_sqlite.py` — ۶ تست (parse DSN، manifest، backup/restore رفت‌وبرگشتی، امتناع بدون `--yes`،
امتناع با archive دست‌کاری‌شده، rotation): **۶ passed** در ۰٫۵۹s.

## شواهد اجرای واقعی روی Windows

```
backup -> .tmp-audit-2026\backups\gi_backup-20261114-224508.sqlite3
sha256 = 19992ab9ca3a...   (manifest نوشته شد)
restore ok -> .tmp-audit-2026\backups\restore_test.sqlite3
verify ok: all counts match
محتوا: sources=1, articles=4, alembic_version=a9f1c2d3e4b5
```

## Retention و Disk Monitoring

- `GET /api/retention/dry-run` → 200؛ سیاست: `document_min_age_days=90`, `market_observation_min_age_days=180`,
  `job_run_min_age_days=30`, `dispatch_terminal_min_age_days=30`, `batch_size=500`؛ candidates روی دیتابیس خالی صفر.
- `GET /api/retention/disk` → 200: `free=49,611,653,120` بایت (≈۴۹٫۶GB)، `used_percent=85.12`، `alert_needed=true`.
- **هیچ داده‌ای حذف نشد**؛ auto-purge خاموش است.

## محدودیت‌ها

- مسیر `pg_dump` روی این ماشین تست نشد (PostgreSQL محلی نصب نیست؛ فقط کانتینر ممیزی موقت وجود داشت). این مسیر تغییر
  نکرده و رفتار قبلی خود را دارد.
- آستانهٔ هشدار دیسک روی این ماشین عملاً فعال است (۸۵٪)؛ این وضعیت به مالک گزارش می‌شود.

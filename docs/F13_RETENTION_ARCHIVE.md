# F13 — Retention، ZIP، Telegram، verified restore/purge

**وضعیت:** PARTIALLY_VERIFIED · **تاریخ:** 2026-10-29

## English summary

Archive/retention code exists in `domains/memory/run_archive.py` and `domains/memory/service.py`;
`TELEGRAM_ARCHIVE_ENABLED=false` and `ARCHIVE_AUTO_PURGE_ENABLED=false` are defaults (per AGENTS.md).
Only 9 tests pass (`test_memory.py`); verified restore/round-trip and auto-purge gating have not been
exercised end-to-end. Disk monitoring (F-26) is not implemented. Auto-purge stays off by default.

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `test_memory.py` | 9 passed |
| auto-purge default | false (خاموش) |
| Telegram archive default | false (خاموش) |
| verified restore/round-trip | تأیید نشد (تست ندارد) |
| disk monitoring (F-26) | غایب |

## ۲) کارهای باز

- تست verified restore (backup → restore → compare) روی DB آزمایشی.
- تست اینکه خاموش‌بودن purge شروع batch بعدی را می‌گیرد.
- disk monitoring + alert (F-26).
- تصمیم مالک برای فعال‌سازی هرگونه purge.


## F13-LOCAL-1 (implemented)

- domains/archive/service.py: settings defaults, measure_storage, is_eligible, build_archive_zip, build_archive_zips, validate_archive_zip.
- Tests: test_archive_local.py, test_archive_split.py, test_archive_validation_fail.py (9 passed).
- Auto-purge remains OFF; no Telegram live upload; no real data deletion.


## F13-LOCAL-3 (2026-10-30) — restore fidelity + migration guards

English

- `domains/archive/restore.py` now writes `document.id`, `document.source_id`, `doc_metadata`
  (provenance), `content_hash`, `hash`, `revision`, `url` and the article point-in-time fields back
  unchanged, so a restored row still satisfies the per-source identity contract.
- The write phase is all-or-nothing: one bad record rolls the whole archive back and the response
  reports `restored: 0` + `rolled_back: true` instead of a partial success that was never committed.
- `restore_dry_run` also reports `missing_source` and `invalid_records`.
- `domains/archive/catalog.py` records `revision`/`content_hash` per `ArchiveArticle`, read from the
  archive itself (not the live row), which conflict detection on restore depends on.
- Both new migrations are idempotent against `create_all`-built schemas; before this,
  `alembic upgrade head` failed with `index uq_job_runs_active already exists` /
  `table archive_catalog already exists`.

فارسی

- بازیابی حالا `source_id` و provenance را حفظ می‌کند و تراکنش all-or-nothing است؛ موفقیت جزئی
  گزارش نمی‌شود.
- catalog برای هر مقاله `revision` و `content_hash` را از خودِ ZIP ثبت می‌کند.
- دو migration جدید در برابر اسکیمای ساخته‌شده با `create_all` بی‌اثر و ایمن شدند.
- تست‌ها: `test_archive_*` = 20 passed؛ کل suite (SQLite) = **1505 passed / 1 skipped** (بازاجرای کامل ۲۰۲۶-۱۰-۳۰، ۲۴۱ ثانیه)؛ `ruff check` سبز.

## F13-LOCAL-2 (implemented)

- Eligibility expanded with event dependency check + status labels.
- ArchiveCatalog + ArchiveArticle models + migration f15b2c3d4e5f.
- restore.py: dry-run preview, restore_from_zip with conflict/duplicate handling, no overwrite.
- check_zip_security (path traversal, zip bomb, size limits).
- catalog.py: record_archive/get/list.
- Tests: test_archive_restore (5), test_archive_catalog (1). Total archive tests 15 passed.
- Auto-purge remains OFF; no Telegram live upload; no real data deletion.

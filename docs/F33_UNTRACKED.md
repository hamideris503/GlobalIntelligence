# F33 — فایل‌های untracked (F-33)

**وضعیت:** PARTIALLY_VERIFIED · **تاریخ:** 2026-10-29

## English summary

Untracked files from prior work were reviewed for secrets. No secret-like pattern (password/secret/token/api_key/
connection string) was found in the operational untracked files. They are left in place (not deleted) since
they may be valuable; the user manages git manually per project rules.

## ۱) فایل‌های untracked بررسی‌شده

| فایل | secret pattern |
|---|---|
| tests/_phase6_probe.py | none |
| tests/test_screening_recovery.py | none |
| tests/test_stage96_cost.py | none |
| domains/news/run_backfill_routing.py | none |
| domains/news/run_screening_inventory.py | none |

## ۲) محدودیت صریح

- بررسی فقط grep بود؛ اثبات کامل نبودن secret نیست (F-33).
- فایل‌های untracked حذف نشدند (تصمیم مالک).
- `.pytest_cache`/temp dirs با permission denied باقی مانده‌اند (خود-پاک نمی‌شوند).

# F28–F31 — همگام‌سازی مستندات (F-28..F-31)

**وضعیت:** PARTIALLY_VERIFIED · **تاریخ:** 2026-10-29

## English summary

Minimal, evidence-backed documentation sync performed:
- `AGENTS.md`: test count updated to 109 `test_*.py` (~1490 tests) (F-35).
- `docs/STAGE_STATUS.md`: new consolidated stage status (F00–F16) with BLOCKED/PARTIALLY_VERIFIED markers.
- Per-stage reports added: F02.5, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14 (partial ×3: JobRun race, ETag, IPv6), F17, F22, F27, F34.
- `FIXES_BACKLOG.md`: F-09/F-10 marked FIXED with root cause; F-03/F-04 etc. left for future.

## ۱) کارهای باز (F-28..F-31)

- `ROADMAP.md` (قدیمی) هنوز Phase 0–52 را پایان پروژه معرفی می‌کند → باید به این سند ارجاع دهد (F-28).
- `TASKS.md` ادعای ruff بدون `source_bot` دارد → باید همگام شود (F-29). (TASKS.md همچنین F-14/F-16 را TODO می‌داند که اکنون انجام شده‌اند.)
- `AUDIT_REPORT.md` بر HEAD قدیمی (`7d7ed17`) است → audit جدید بساز (F-30).
- شمارهٔ Stage در کامنت‌ها با roadmap تعارض دارد → از شناسهٔ پایدار (BUG-xx/TASK-xx) استفاده شود (F-31).

## ۲) محدودیت صریح

- ویرایش کامل TASKS.md/ROADMAP.md/AUDIT_REPORT.md در این مرحله انجام نشد (Persian/mojibake risk + حجم).
- F-32 (.gitignore) قبلاً انجام شد (`.pytest-ci/` اضافه).
- F-33 (untracked cleanup) انجام نشد — نیاز به بررسی secret.
- F-35 (شمارش تست در AGENTS.md) انجام شد (109).

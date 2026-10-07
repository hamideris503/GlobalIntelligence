# PROGRESS.md

> گزارش پیشرفت مرحله‌به‌مرحله. بعد از هر مرحله، بخش «Completed / Files changed / Tests / Known issues / Next step» ثبت می‌شود.

---

## Phase 1 — Environment Preparation & Repository Skeleton
**تاریخ:** 2026-10-07
**وضعیت:** DONE

### Completed
- بررسی و تأیید ابزارهای محیط (Git, Python, pip, Node, npm, Docker CLI, Compose)
- ساخت اسکریپت `scripts/check_env.py` (بدون وابستگی خارجی)
- فایل نسخه‌های مرجع `config/environment.toml`
- فایل‌های وابستگی Backend: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `backend/.gitignore`
- فایل‌های Frontend: `apps/web/package.json`, `.npmrc`, `.gitignore`
- تنظیمات ویرایشگر: `.editorconfig`
- ساخت `.env` محلی از `.env.example` (تأیید شد که توسط Git نادیده گرفته می‌شود)

### Files changed
- `scripts/check_env.py` (جدید)
- `config/environment.toml` (جدید)
- `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pyproject.toml`, `backend/.gitignore` (جدید)
- `apps/web/package.json`, `apps/web/.npmrc`, `apps/web/.gitignore` (جدید)
- `.editorconfig` (جدید)
- `.env` (جدید، محلی و gitignored)
- `PROGRESS.md`, `TASKS.md`, `DECISIONS.md`, `README.md` (به‌روزرسانی)

### Tests
- `python -m py_compile scripts/check_env.py` → OK
- `python scripts/check_env.py` → exit code 0 (همه ابزارهای حیاتی OK)
- `git check-ignore .env` → تأیید شد که `.env` نادیده گرفته می‌شود

### Known issues
- **Docker Daemon در حال اجرا نیست** (Docker Desktop باید شروع شود). CLI و Compose نصب‌اند و برای Phase 2 کافی است.
- خطای اولیه‌ی انکودینگ کنسول ویندوز (cp1256) برطرف شد (reconfigure به UTF-8 + تغییر کدگذاری subprocess).
- npm روی ویندوز فقط از طریق `npm.cmd` اجرا می‌شود؛ اسکریپت این حالت را پوشش می‌دهد.

### Next step
- Phase 2 — Skeleton: Backend (FastAPI) + Frontend (Vite) + Database + Health endpoint + `docker-compose.yml` پایه

---

## Phase 0 — Project Specification & Architecture
**تاریخ:** 2026-10-07
**وضعیت:** DONE (اسناد پایه)

### Completed
- تعریف نهایی محصول، Goals و Non-goals
- معماری کلان (Runtime View + Logical Pipeline)
- ساختار Repository
- طراحی مفهومی AI Gateway (Provider-Agnostic)
- تعریف مدل داده Core Entities
- تعریف Memory (۷ لایه) و Forecast Ledger
- تعریف اصول: Free-First، Point-in-Time Integrity، Reproducibility
- ساخت اسکلت پوشه‌ها
- ساخت ۱۰ سند پایه

### Files changed
- `.gitignore`
- `.env.example`
- `README.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `TASKS.md`
- `PROGRESS.md`
- `DECISIONS.md`
- `LICENSES.md`
- `DATA_SOURCES.md`
- `AI_MODELS.md`
- اسکلت پوشه‌ها (backend, workers, domains, integrations, ml, db, tests, docs, scripts, config, data, docker, apps/web)

### Tests
- (Phase 0 فقط اسناد است — تست کد ندارد)
- بررسی محیط: Git ✅، Python 3.14 ✅، Node v24 ✅، Docker 23 ✅

### Known issues
- مجوز پروژه هنوز تعیین نشده (در DECISIONS.md پیگیری می‌شود)
- انتخاب Provider پیش‌فرض برای AI هنوز نهایی نشده (Mock پیش‌فرض است)

### Next step
- Phase 1 — آماده‌سازی محیط و اسکلت اجرایی Repository (package files، Docker skeleton)

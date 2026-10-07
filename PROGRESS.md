# PROGRESS.md

> گزارش پیشرفت مرحله‌به‌مرحله. بعد از هر مرحله، بخش «Completed / Files changed / Tests / Known issues / Next step» ثبت می‌شود.

---

## Phase 4 — n8n orchestration (Trigger → Backend → Database)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- n8n نسخه 2.42.4 در حال اجرا (http://localhost:5678)
- مدل `JobRun` + جدول `job_runs` + migration `71f41613dd11`
- jobs API:
  - `POST /api/jobs/trigger` → ثبت JobRun در PostgreSQL
  - `GET /api/jobs` → آخرین اجراها
- workflow نمونه: `integrations/n8n/workflows/phase4-trigger-backend-database.json`
  - Schedule Trigger (هر ۵ دقیقه) → HTTP POST به `http://backend:8000/api/jobs/trigger`
- import + publish workflow در n8n + ری‌استارت
- اسکریپت کمکی: `scripts/import_n8n_workflows.py`

### Files changed
- `backend/database/models/job.py`, `models/__init__.py`
- `backend/api/schemas/jobs.py`, `backend/api/routers/jobs.py`, `backend/main.py`
- `db/migrations/versions/71f41613dd11_add_job_runs.py`
- `integrations/n8n/workflows/phase4-trigger-backend-database.json`, `integrations/n8n/README.md`
- `tests/test_jobs.py`, `scripts/import_n8n_workflows.py`

### Tests
- `python -m pytest tests -q` → **9 passed** ✅
- import workflow در n8n → «Successfully imported 1 workflow» ✅
- publish + restart → «1 published workflows» ✅
- **اجرای زمان‌بندی‌شده‌ی واقعی**: n8n در 2026-10-07 21:25:01 خودکار درخواست زد و
  رکورد `scheduled_heartbeat` با source=`n8n` در `job_runs` ثبت شد ✅
- تست شبکه از داخل کانتینر n8n به `http://backend:8000` ✅

### Known issues
- در n8n 2.x، فایل workflow باید فیلد `id` داشته باشد و از `publish:workflow`
  استفاده شود (نه صرفاً active کردن). اسکریپت کمکی این را مدیریت می‌کند.
- n8n با volume خودش (`n8n_data`) کار می‌کند؛ workflowها در DB داخلی n8n ذخیره می‌شوند.

### Next step
- Phase 5 — AI Gateway (Provider interface + Mock provider + routing پایه)

---

## Phase 3 — PostgreSQL (models + migrations)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- مدل‌های ORM موجودیت‌های اصلی (۱۵ جدول):
  sources, documents, articles, events, claims, evidence, entities,
  entity_relationships, market_observations, macro_observations,
  world_states, scenarios, forecasts, forecast_outcomes, recommendations
- `base.py`: `Base`, `UUIDMixin`, `TimestampMixin`, `PointInTimeMixin`
- `enums.py`: SourceType, VerificationStatus, EntityType, RelationType, EvidenceDirection
- Alembic setup: `alembic.ini`, `db/migrations/env.py`, `script.py.mako`
- migration اولیه autogenerate: `50834c9c3273_initial_schema.py`
- entrypoint بکاند: اجرای خودکار `alembic upgrade head` پیش از سرور
- session factory + `get_db()` + health/db با نسخه‌ی migration
- seed منابع اولیه (`db/seed/sources.py`) — ۶ منبع
- تست‌های مدل (`tests/test_models.py`)

### Files changed
- `backend/database/base.py`, `enums.py`, `session.py`, `__init__.py`
- `backend/database/models/` (۱۲ فایل مدل + `__init__.py`)
- `alembic.ini`, `db/migrations/{env.py,script.py.mako}`, `db/migrations/versions/50834c9c3273_initial_schema.py`
- `docker/backend.Dockerfile`, `docker/backend-entrypoint.sh`
- `db/seed/sources.py`, `tests/test_models.py`

### Tests
- `python -m pytest tests -q` → **7 passed** ✅
- `alembic upgrade head` → ۱۶ جدول (۱۵ + alembic_version) ✅
- `alembic downgrade base` → ۱ جدول (فقط alembic_version) ✅
- `alembic upgrade head` دوباره → ۱۶ جدول ✅ (migration برگشت‌پذیر)
- اجرای داخل Docker: entrypoint migration را اجرا و سرور را بالا آورد ✅
- seed → ۶ منبع ثبت شد ✅
- `/health/db` → `{"ok":true,"server":"PostgreSQL 16.15...","migration":"50834c9c3273"}` ✅

### Known issues
- فایل `.env` باید UTF-8 باشد؛ اگر با PowerShell و encoding اشتباه بازنویسی شود، pydantic-settings خطای decode می‌دهد (با کپی مستقیم از `.env.example` حل شد).
- در شبکه‌ی محدود، `PIP_INDEX_URL` در `.env` باید ست بماند تا build بکاند موفق شود.

### Next step
- Phase 4 — n8n: ساخت workflow ساده Trigger → Backend → Database

---

## Phase 2 — Skeleton (Backend + Frontend + DB + Health)
**تاریخ:** 2026-10-07
**وضعیت:** DONE

### Completed
- Backend FastAPI با endpoints: `/`, `/health` (liveness)، `/health/db` (readiness)
- تنظیمات مرکزی با `pydantic-settings` (خواندن از `.env`)
- لایه‌ی دیتابیس: `get_engine()` و `check_database()` (بدون crash در نبود DB)
- Frontend React + Vite با HTML `dir="rtl"`، Dark Mode و نمایش وضعیت API/DB
- `docker-compose.yml` شامل postgres, backend, frontend, n8n
- Dockerfiles برای backend و frontend + `.dockerignore`
- ۳ تست pytest برای health endpoints

### Files changed
- `backend/main.py`, `backend/asgi.py`, `backend/__init__.py`
- `backend/core/{__init__,config,logging}.py`
- `backend/database/{__init__,session}.py`
- `backend/api/__init__.py`, `backend/api/routers/{__init__,health}.py`
- `apps/web/{index.html,vite.config.ts,tsconfig.json}`
- `apps/web/src/{main.tsx,App.tsx,styles.css,vite-env.d.ts}`
- `docker-compose.yml`, `.dockerignore`, `docker/{backend,frontend}.Dockerfile`
- `tests/{__init__.py,test_health.py}`

### Tests
- `python -m pytest tests -q` → **3 passed** ✅
- اجرای زنده uvicorn روی پورت 8010:
  - `/` → `{"name":"GlobalIntelligence","env":"development","status":"ok","docs":"/docs"}` ✅
  - `/health` → `{"status":"ok"}` ✅
  - `/health/db` → `{"status":"degraded", ...}` (graceful، چون Postgres در دسترس نبود) ✅
- `npx tsc --noEmit` → exit 0 ✅
- `npm run build` → build موفق (dist ساخته شد) ✅
- `docker compose config --quiet` → معتبر ✅

### Known issues
- **Docker Desktop در ابتدا خراب بود** و حل شد: نسخه‌ی قدیمی 4.19 با WSL 3.x ناسازگار بود؛ با به‌روزرسانی به Server **29.8.2** درست شد.
- **شبکه‌ی PyPI ناپایدار** (`files.pythonhosted.org` خطای SSL EOF می‌داد) — با استفاده از آینه‌ی `mirror-pypi.runflare.com` در build حل شد (قابل تنظیم از `.env`).
- `/health/db` در نبود DB به‌درستی `degraded` می‌دهد و crash نمی‌کند (طبق قانون 72).

### Docker stack (اجراشده و تأییدشده)
| سرویس | وضعیت | URL |
|---|---|---|
| backend | healthy | http://localhost:8000 |
| frontend | up | http://localhost:5173 |
| postgres | healthy | localhost:5432 |
| n8n | up | http://localhost:5678 |

آدرس‌های تست‌شده:
- `/health` → `{"status":"ok"}` ✅
- `/health/db` → `{"status":"ok","database":{"ok":true,"detail":"connected"}}` ✅
- `/docs` → 200 ✅
- `:5173` → 200 (دارای `#root`) ✅
- `:5678` → 200 ✅

### Next step
- Phase 3 — PostgreSQL: مدل‌ها، Alembic، migration اولیه، اتصال کامل و health check دیتابیس

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

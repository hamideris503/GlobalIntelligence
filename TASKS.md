# TASKS.md

> مدیریت کارهای پروژه. هر تسک یکی از چهار وضعیت را دارد: TODO / IN_PROGRESS / DONE / BLOCKED

**به‌روزرسانی:** Phase 10 (fix round)

---

## TODO
- [ ] Phase 10 (redo): اجرای واقعی با یک Provider واقعی + ۲۰ مقاله‌ی واقعی
- [ ] Phase 11: Event Extraction
- [ ] بعد: تست‌ها روی PostgreSQL واقعی در CI + workflow CI (ruff/mypy/pytest/docker build)
- [ ] بعد: انتقال endpointهای سنگین به workers/ پس‌زمینه
- [ ] بعد: JSONB برای topics/entities (به‌جای Text)

## IN_PROGRESS
- (هیچ)

## DONE
- [x] Phase 12: Claim extraction (event → claims) + API + CLI + prompt/schema
- [x] Phase 11: Event extraction (cluster → event) + API + CLI + prompt/schema
- [x] Phase 10 validation: golden set (importance variety + country + meta)
- [x] Phase 10 fix (P0/P1): رفع مسیریابی Gateway (mock در production)، ذخیره‌ی همه‌ی اسناد، feed_url، پرامپت/schema، احراز هویت، LSH 32×2، raw_payload، savepoint، Gemini header، n8n pin
- [x] Phase 10: Article classification (topics/entities/sentiment) + deterministic importance
- [x] Phase 9: dedup (MinHash/LSH/Union-Find) + service + CLI + API + ingest hook
- [x] Phase 8: News ingestion pipeline + fetchers + normalizer + API + CLI worker
- [x] Phase 8: dedup سبک بر اساس content_hash
- [x] Phase 8: workflow n8n زمان‌بندی‌شده برای ingestion
- [x] Phase 7: Source Registry service + API (`/api/sources`) + seed ۱۴ منبع
- [x] Phase 5: AI Gateway (Provider interface + Mock + HTTP adapters + fallback/retry)
- [x] Phase 5: Mock Provider (به‌نوعی Phase 6 هم پوشش داده شد)
- [x] Phase 5: endpointهای `/api/ai/generate` و `/api/ai/providers`
- [x] Phase 4: n8n workflow (Trigger → Backend → Database) import و فعال شد
- [x] Phase 4: jobs API (`POST /api/jobs/trigger`, `GET /api/jobs`) + جدول `job_runs`
- [x] Phase 4: اجرای زمان‌بندی‌شده‌ی واقعی n8n تأیید شد (رکورد در DB)
- [x] Phase 3: ORM models (۱۵ جدول) + enums + Point-in-Time mixin
- [x] Phase 3: Alembic + migration اولیه (`50834c9c3273`) + upgrade/downgrade تست‌شده
- [x] Phase 3: entrypoint بکاند اجرای خودکار migration
- [x] Phase 3: session factory + `get_db` + health/db با نسخه migration
- [x] Phase 3: seed منابع اولیه + تست‌های مدل (۷ تست pass)
- [x] Phase 2: Backend FastAPI + health endpoints (`/`, `/health`, `/health/db`)
- [x] Phase 2: Frontend React + Vite (RTL/Dark) + build موفق
- [x] Phase 2: `docker-compose.yml` (postgres, backend, frontend, n8n) + Dockerfiles
- [x] Phase 2: تست‌های pytest health (۳ تست pass)
- [x] Phase 2: `.dockerignore`
- [x] Phase 1: بررسی محیط و اسکریپت `check_env.py`
- [x] Phase 1: `config/environment.toml` (نسخه‌های مرجع)
- [x] Phase 1: فایل‌های وابستگی Backend (`requirements*.txt`, `pyproject.toml`)
- [x] Phase 1: فایل‌های Frontend (`package.json`, `.npmrc`, `.gitignore`)
- [x] Phase 1: `.editorconfig` و `.env` محلی
- [x] Phase 0: ساخت ساختار پوشه‌ها (Repository skeleton)
- [x] Phase 0: `.gitignore`
- [x] Phase 0: `.env.example`
- [x] Phase 0: `README.md`
- [x] Phase 0: `ARCHITECTURE.md`
- [x] Phase 0: `ROADMAP.md`
- [x] Phase 0: `TASKS.md`
- [x] Phase 0: `PROGRESS.md`
- [x] Phase 0: `DECISIONS.md`
- [x] Phase 0: `LICENSES.md`
- [x] Phase 0: `DATA_SOURCES.md`
- [x] Phase 0: `AI_MODELS.md`

## BLOCKED
- (هیچ)

---

## Definition of Done (برای همه تسک‌ها)
- Code exists
- Configuration exists
- Tests pass
- Health check passes
- Documentation updated
- No known critical error
- User can reproduce result

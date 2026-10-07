# TASKS.md

> مدیریت کارهای پروژه. هر تسک یکی از چهار وضعیت را دارد: TODO / IN_PROGRESS / DONE / BLOCKED

**به‌روزرسانی:** Phase 0

---

## TODO
- [ ] Phase 1: فعال‌سازی pre-commit hooks (اختیاری، پس از نصب وابستگی‌ها)
- [ ] Phase 2: اسکلت Backend (FastAPI) + Frontend (Vite) + Health endpoint
- [ ] Phase 2: `docker-compose.yml` پایه (frontend, backend, postgres, n8n)
- [ ] Phase 3: PostgreSQL + migrations + models + connection + health check
- [ ] Phase 5: اینترفیس AI Gateway + Mock Provider
- [ ] Phase 7: جدول Source + seed منابع اولیه

## IN_PROGRESS
- (هیچ)

## DONE
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

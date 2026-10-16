# TASKS.md

> مدیریت کارهای پروژه. هر تسک یکی از چهار وضعیت را دارد: TODO / IN_PROGRESS / DONE / BLOCKED

**به‌روزرسانی:** Phase 52 ✅ COMPLETE

---

## TODO
- [ ] BLOCKED — Phase 48 live: اجرای `--live` روی VPS (نیازمند host/user/key)
- [ ] کاربر: بررسی/ابطال کلیدهای احتمالی واقعی داخل `.env` محلی (در RAR قدیمی بوده است)
- [x] Step 0: Security Hygiene (gitignore/.env history/secret scan/check_env warnings/archive check)
- [x] Step 1: Real AI on (check_ai + structured fallback + Phase 10 redo 30 real, report for review)
- [x] Step 2: Real market+macro (fetch real + sanity + flag_mock_rows + staleness check)
- [ ] User decision: delete 135 mock-classified articles? (flagged, NOT deleted)
- [x] Step 3: Debate Engine (code+dry-run done; real debate AWAITS user approval)
- [x] User approval: ONE real debate done (market:WTI, lite, transcript in reports/)
- [x] Step 4: Scorecard + کارنامه + daily debate workflow (active:false)
- [x] Step 5: Debate proposals (gates+experimental) + Debate page
- [x] Step 6: CI real + evidence counter + N+1 report/fix + backup docs (no live deploy)
- [x] Step 8-A: Settings backend (encryption, providers, gateway DB, prices, void)
- [ ] Step 8-B: Settings UI (5 tabs) — needs user go-ahead
- [ ] User: set APP_ENCRYPTION_KEY in .env (else key storage refuses)
- [x] Step 9 (1-2 done; 3-4 waiting: user registers mappings+prices, then approves)
- [x] Reliability: scheduled success proven (12:30) + mock override + pool
- [x] Cleanup executed (249 rows, backup verified, audit logged)
- [ ] Watch: hourly tick recovery (13:00)
- [ ] User approval: delete 7 dup evidence rows (IDs listed, backup first)
- [ ] Phase 10 (redo): اجرای واقعی با یک Provider واقعی + ۲۰ مقاله‌ی واقعی
- [ ] بعد: تست‌ها روی PostgreSQL واقعی در CI + workflow CI (ruff/mypy/pytest/docker build)
- [ ] بعد: انتقال endpointهای سنگین به workers/ پس‌زمینه
- [ ] بعد: JSONB برای topics/entities (به‌جای Text)

## IN_PROGRESS
- (هیچ)

## DONE
- [x] Phase 52: Advanced Research (GraphRAG-lite + API + CLI + تست) 🎉
- [x] Phase 51: Long-Term Learning (روند دقت + نرخ رژیم + آستانه p90 + API + CLI + migration + تست)
- [x] Phase 49: 24/7 Automation (۵ workflow + ops status + تست)
- [x] Phase 48: VPS Deployment automation + docs (اجرای زنده BLOCKED: بدون سرور)
- [x] Phase 47: Staging (stack جدا + smoke سبز + docs + تست)
- [x] Phase 46: Docker Production (compose prod + ایمیج nginx + راستی‌آزمایی ایمیج‌ها)
- [x] Phase 45: Backup (dump/restore/verify + manifest + rotation + تست)
- [x] Phase 44: Security Hardening (هدرها + rate limit + fail-fast + تست امنیتی)
- [x] Phase 43: Alerts (قواعد آستانه + ارزیابی + API + CLI + migration + تست)
- [x] Phase 42: Weekly Intelligence (خلاصه ۷ روزه + مقایسه‌ها + API + CLI + تست)
- [x] Phase 41: Daily Intelligence (خلاصه ۲۴ ساعته + Briefing + API + CLI + migration + تست)
- [x] Phase 40: Dashboard (۷ بخش زنده + کلید API + RTL + بیلد موفق)
- [x] Phase 39: Self Evaluation (۶ چک + نمره/grade + API + CLI + migration + تست)
- [x] Phase 38: Audit / Replay (لاگ افزودنی + بازپخش قطعی + API + CLI + migration + تست)
- [x] Phase 37: Adaptive AI Router (ثبت عملکرد + زنجیره تطبیقی + API + CLI + migration + تست)
- [x] Phase 36: Model Performance (ثبت دوره‌ای + leaderboard + API + CLI + migration + تست)
- [x] Phase 35: Portfolio Intelligence (پورتفوی + snapshot + API + CLI + migration + تست)
- [x] Phase 34: Iran Transmission (۴ کانال انتقال + assessment + API + CLI + migration + تست)
- [x] Phase 33: Iran Mode (لنز تجمیعی ایران + API + CLI + تست)
- [x] Phase 32: Decision Engine (تصمیم قانون‌مند + Recommendation + API + CLI + تست)
- [x] Phase 31: Risk Engine (۸ دسته ریسک + assessment + API + CLI + migration + تست)
- [x] Phase 30: Scenario Engine (۴ سناریوی قطعی + Ledger + API + CLI + تست)
- [x] Phase 29: Forecast Tournament (رقابت مدل‌ها + leaderboard + API + CLI + migration + تست)
- [x] Phase 28: Forecast Evaluation (متریک‌ها + کالیبراسیون + API + CLI + تست)
- [x] Phase 27: Outcome Engine (تطبیق نتایج واقعی + resolved + API + CLI + تست)
- [x] Phase 26: Forecast Ledger (سناریو + چرخه حیات + جانشینی + active as-of + migration + تست)
- [x] Phase 25: Forecast Engine (baselineهای قطعی + Ledger + API + CLI + تست)
- [x] Phase 24: Narrative Engine (خوشه‌بندی روایت + strength + API + CLI + migration + تست)
- [x] Phase 23: Social Intelligence (فضای اجتماعی قلمروها + assessment + API + CLI + migration + تست)
- [x] Phase 22: Geopolitical Engine (تنش بازیگران + assessment + API + CLI + migration + تست)
- [x] Phase 21: Macro Engine (تحلیل قطعی سری‌ها + assessment + API + CLI + migration + تست)
- [x] Audit Fix: اصلاحات ممیزی Phase 18/20 (cosine، پوشش no_data، پنجره drawdown، آرشیو تمیز، بیلد frontend)
- [x] Phase 20: Historical Analogue (فاصله‌ی برداری + رتبه‌بندی + aftermath + API + CLI + تست)
- [x] Phase 19: Historical Memory (بایگانی ۳ لایه + timeline Point-in-Time + API + CLI + migration + تست)
- [x] Phase 18: World State (۹ سیگنال قطعی + رژیم‌ها + snapshot + API + CLI + تست)
- [x] Phase 17: Market Data (کاتالوگ ۱۳ نماد + fetcherهای رایگان + upsert idempotent + API + CLI + تست)
- [x] Phase 16: Economic Data (World Bank fetcher + upsert idempotent + API + CLI + migration + تست)
- [x] Phase 15: Knowledge Graph (entity resolution + relationship extraction + API + CLI + migration + تست)
- [x] Phase 14: Source Independence (گراف وابستگی منابع + محاسبه‌ی تأیید مستقل + API + CLI + migration + تست)
- [x] Phase 13: Evidence Engine (claim → evidence) + `verify_status` + API + CLI + prompt/schema + migration + رفع باگ enum در Mock
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

## Stage 0 verified (2026-10-16, evidence in PROGRESS.md)
- [x] Debate engine + bridge + scorecard (30 tests green)
- [x] Settings tables + Auth endpoints
- [x] Source census registry + models (phase57 applied)
- [x] Phase58 index convergence (migration applied, alembic check green)
- [x] Source Bot + 4 fixes: keyless skip, stale lock, crawl, api_key (73 tests green)
- [x] Phase A unified mock-mode (36 tests green)
- [x] Evidence repair + attempts cap + MIME + routing + prompts v3
- [ ] Feed validation (`validate_feed` + `check=feed`): implemented + 11 tests green, UNCOMMITTED
- [ ] 198 census sources activation (user decision)
- [ ] Real API keys (FRED/AlphaVantage/ACLED absent)
- [ ] VPS deploy (LAST stage, after local validation)

---

## Definition of Done (برای همه تسک‌ها)
- Code exists
- Configuration exists
- Tests pass
- Health check passes
- Documentation updated
- No known critical error
- User can reproduce result

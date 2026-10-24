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
- [ ] بعد: تأیید اجرای راه‌دور CI روی GitHub — فایل `.github/workflows/ci.yml` موجود است (backend: ruff+pytest روی postgres:16، docker: build هر دو ایمیج، frontend: npm ci+build؛ mypy عمداً در CI نیست) ولی اجرای واقعی روی GitHub تأیید نشده (NOT_VERIFIED). شکاف‌های دقیق (ممیزی Phase 15): `ruff check backend domains tests scripts` فاقد `source_bot/` است؛ job فرانت‌اند فقط install+build را اجرا می‌کند (بدون `tsc --noEmit`، بدون lint، بدون E2E)؛ سرویس postgres:16 و `DATABASE_URL` در job بک‌اند عملاً توسط pytest مصرف نمی‌شود چون `tests/conftest.py` روی SQLite درون‌حافظه اجرا می‌کند (migrationها از Postgres استفاده می‌کنند)؛ هیچ `secrets.` در workflow نیست. تنها تغییر کوچک پیشنهادی: افزودن `source_bot` به scope دستور ruff (نیازمند تأیید؛ در Phase 15 اعمال نشد)
- [ ] تصمیم — مسابقه‌ی ساخت Job تکراری: `create_job` الگوی check-then-insert دارد (`source_bot/jobs.py:29-48`) و unique constraint روی JobRun فعال وجود ندارد ⇒ در دو POST هم‌زمان هر دو pending ساخته می‌شود و بازنده در `run_job` بعد از `claim_job` بی‌صدا رها می‌شود (`jobs.py:139-141` بدون `finish_job`) و همان ردیف pending تا restart همه‌ی Jobهای بعدی را با 409 رد می‌کند (`ACTIVE_STATUSES`). بازیابی فقط در startup است (`backend/main.py:90-95`) ⇒ نقص availability باریک، self-heal با restart. گزینه‌ها: ایندکس یکتای جزئی (نیازمند migration، فعلاً ممنوع) یا قفل درون‌پروسه‌ای (فقط تک‌پروسه؛ با محدودیت چند-worker هم‌سو است) — نیازمند تأیید؛ در Phase 15 تغییر محصول اعمال نشد
- [ ] بعد: انتقال endpointهای سنگین به workers/ پس‌زمینه
- [ ] بعد: JSONB برای topics/entities (به‌جای Text)
- [ ] تصمیم — Adaptive Router بی‌اثر است: `AdaptiveRouter.record` + `POST /api/ai-routing/record` وجود دارد، ولی هیچ مصرف‌کننده‌ی خودکاری (hook در gateway یا step در n8n) آن را صدا نمی‌زند. اتصال به hook می‌تواند باعث ثبت تکراری یا اثر جانبی (commit) روی مسیر AI شود؛ نیازمند تصمیم معماری (ممیزی Phase 13/14 روی `domains/ai_routing/router.py` و `backend/ai/gateway/gateway.py`). آزمون‌های لازم پیش از اتصال خودکار: (۱) دقیقاً یک ثبت به‌ازای هر `generate` حتی با fallback/چند retry، (۲) صفر ثبت در `MOCK_MODE`، (۳) خطای DB ثبت را نمی‌شکند و پاسخ AI دست‌نخورده برمی‌گردد، (۴) no commit ناخواسته روی session درخواست، (۵) رفتار race هم‌زمانی روی `uq_provider_run`
- [ ] بعد — نمایش جزئیات خوشه‌های dedup در UI: الان فقط شمارش تجمیعی (`duplicate_clusters`/`exact_pairs`/`near_pairs`) که به‌شکل یک خط متن زیر دکمه‌ی داشبورد دیده می‌شود؛ همچنین هیچ read-model/endpoint فعلی خوشه‌ها را برنمی‌گرداند (`ArticleClassifiedRead` فیلد `duplicate_cluster` ندارد و فقط `POST /api/dedup/run` با `DedupSummary` تجمیعی وجود دارد). ارزیابی Phase 14: برای تکمیل ingestion bot **ضروری نیست** (dedup تشخیص است نه حذف؛ یکتایی و شمارش‌ها کار می‌کنند) — یک بهبود پذیرش/ممیزی است
- [ ] تصمیم — ESLint و اسکریپت `lint`: `apps/web/package.json` اسکریپت `"lint": "eslint ."` دارد، اما eslint نه در dependencyها/lockfile هست، نه باینری‌اش نصب است و نه config دارد (هیچ linter جایگزینی مثل biome/oxlint/prettier هم موجود نیست) ⇒ `npm run lint` شکست می‌خورد و CI فقط `npm run build` را اجرا می‌کند. پیشنهاد مستدل: یا افزودن eslint+config به‌عنوان تصمیم آگاهانه در یک تغییر جدا (نیازمند نصب شبکه)، یا حذف اسکریپت `lint` و افزودن `tsc --noEmit` به CI به‌عنوان تنها بررسی استاتیک موجود؛ تا آن‌زمان این وضعیت باید صادقانه شکست‌خورده بماند
- [ ] محدودیت مستندشده — Scrapy فقط IPv4 (`source_bot/adapters/scrapy_policy.py:22`): مقصدی که تنها AAAA دارد fail-closed است (بدون اتصال، فقط `DNSLookupError`)
- [ ] بدهی (شواهد Phase 15) — ETag/Last-Modified در pipeline عملاً بی‌اثر است: `RestJsonAdapter` در هر fetch از نو ساخته می‌شود (`source_bot/runner.py:134`) ⇒ دیکشنری‌های `self._etag`/`self._last_mod` (`rest_json.py:67-68`) همیشه خالی‌اند و `If-None-Match`/`If-Modified-Since` هرگز فرستاده نمی‌شود؛ کش پایدار هم وجود ندارد (نه بین اجراها، نه بین منابع، نه برای RSS/HTML). راهکارهای سازگار بدون migration: (الف) نمونه‌ی process-scoped با reset در تست‌ها، یا (ب) ذخیره در `Source.endpoint_config` که همین حالا JSON است (`backend/database/models/source.py:35`). اعتبارسنجی واقعی نیازمند شبکه‌ی واقعی است ⇒ نیازمند تصمیم؛ در Phase 15 تغییر محصول اعمال نشد
- [ ] بدهی — چند worker/container: قفل ربات یک فایل tempdir است (`source_bot/runner.py:32`) ⇒ فقط درون یک host هماهنگ می‌کند؛ Job نیمه‌کاره بعد از restart فقط failed علامت می‌خورد (`recover_interrupted_jobs`) و از سر گرفته نمی‌شود
- [ ] BLOCKED (خارج از محدوده‌ی اجرای محلی) — اعتبارسنجی provider واقعی + زیرساخت خارجی: بدون کلید/سرویس واقعی، کیفیت داده و مسیریابی production تأییدشدنی نیست

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

## Phase 13/14 — اعتبارسنجی محلی (2026-10-18، شواهد: همان اجرای واقعی)
- [x] E2E فول‌استک محلی: `npm run test:e2e:fullstack` با `E2E_FRONTEND_PORT=14174` → ۱۴ passed (backend واقعی + SQLite دورانداختنی + `MOCK_MODE=true`؛ فایل گارد شبکه خالی ⇒ «هیچ درخواست خارجی» اثبات‌شده، سرورها در پایان متوقف شدند)
- [x] E2E پایه‌ی مرورگر (mock لوکال، `E2E_FRONTEND_PORT=14173`) → ۱۹ passed: ۵ تست اولویت P0..P4/Null در جدول اخبار و جزئیات مقاله + یک تست «بدون خطای مرورگر و بدون پاسخ 4xx»
- [x] دروازه‌های محلی: `pytest tests -q` → ۹۳۵ passed (۸۴۲ ثانیه)؛ `ruff check backend domains tests scripts source_bot`، `npm run build`، `npx tsc --noEmit`، `git diff --check` → همه پاک
- [ ] محدودیت محیطی این ماشین: پورت‌های پیش‌فرض E2E (4173/4174) در بازه‌ی رزرو Windows/Docker هستند ⇒ اجرای محلی باید `E2E_FRONTEND_PORT` را روی پورت آزاد بگذارد (مثلاً 14173/14174)

## Phase 15 — ممیزی CI / بازیابی job / ETag + collector فول‌استک (2026-10-18، شواهد: همان اجرای واقعی)
- [x] Task 1 (collector فول‌استک): در `apps/web/e2e/fullstack.spec.ts` سه شنونده اضافه شد — `pageerror`، `console.error` (به‌جز echo پاسخ‌های ≥400 که جداگانه و دقیق‌تر سنجیده می‌شوند) و پاسخ‌های ≥400 با `status + url`. allowlist عمدی‌ها دقیق است (status مشخص برای هر endpoint، نه «هر 4xx/5xx»): `/api/settings/*`→401/422، `/api/ai/status`→401، `/api/ai/chat`→403؛ assert ضد-vacuity (`badResponses.length > 0`) تا تست واهی سبز نشود. اثبات حساسیت: با mutation موقت (`402` جای `401/422`) فقط همان تست fail شد و لیست واقعی 401 چاپ شد، سپس revert ⇒ ۱۵ passed. علت تکرار 401ها پیش از ورود کلید به حافظه است (`useApi` در `apps/web/src/ui.tsx:48-69` با `version` refetch می‌کند و `signIn` کلید را دستی/فقط‌حافظه‌ای می‌گذارد) ⇒ رفتار عمدی، نه نقص
- [x] Task 2 (ممیزی CI، بدون اجرای راه‌دور): Python 3.12 / Node 20؛ هیچ `secrets.` در workflow (۰ مورد)؛ job بک‌اند: `ruff check backend domains tests scripts` (بدون `source_bot/`), `alembic upgrade head → downgrade base → upgrade head`, `pytest tests -q`؛ job docker: build هر دو ایمیج؛ job فرانت‌اند: `npm ci || npm install` + `npm run build` فقط. شکاف‌ها: بدون `tsc --noEmit`، بدون lint، بدون E2E؛ `DATABASE_URL/postgres:16` عملاً مصرف pytest نمی‌شود (conftest روی SQLite). اجرای واقعی روی GitHub همچنان NOT_VERIFIED
- [x] Task 3 (بازیابی job، ممیزی محور بدون تغییر محصول): ۱) توقف وسط اجرا → recovery در startup (`backend/main.py:90-95`) ۲) مرگ پیش از ثبت نتیجه → نتیجه در یک commit نوشته می‌شود (`source_bot/jobs.py:78-92`) و ردیف در running/pending نمی‌ماند ۳) restart → همان recovery + پذیرش Job جدید (تست `tests/test_ingest_jobs.py:174+`) ۴) دو worker → claim اتمیک `pending→running` (`jobs.py:59-68`) + تست `test_claim_prevents_second_execution` + قفل فایل با pid-زنده (`source_bot/runner.py:80-98`)؛ تنها شکاف باقی‌مانده مسابقه‌ی ساخت Job است (در TODO ثبت شد) ۵) retry → داده تکراری ذخیره نمی‌شود (`runner.py:310-320` + همان تست) ۶) خطای یک منبع → ایزوله با وضعیت `partial` (`tests/test_ingest_jobs.py:110-125`، `runner.py:361-362`)
- [x] Task 4 (ETag/Last-Modified، فقط ممیزی): `RestJsonAdapter` در هر fetch از نو ساخته می‌شود (`source_bot/runner.py:134`) ⇒ `self._etag/self._last_mod` همیشه خالی ⇒ هدرهای شرطی در pipeline واقعی فرستاده نمی‌شوند و ماندگاری وجود ندارد (نه بین اجراها، نه بین منابع). timeout/304/auth کنترل‌شده‌اند (تست‌های `tests/test_source_bot_adapters_phase4.py:227-258`). چون نقص کارکردی (نه داده‌ای) است و اعتبارسنجی نیازمند شبکه‌ی واقعی است، تغییر محصول اعمال نشد (گزینه‌ها در TODO)
- [ ] Task 5: `npm run lint` همچنان FAIL است (`exit=1`، `'eslint' is not recognized`؛ eslint در `package.json`/lockfile/`node_modules/.bin` نیست) — بدون نصب شبکه‌ای رفع نشد و برای سبزکردن گزارش حذف نشد
- [x] Task 6 (دروازه‌های Phase 15): `npm run test:e2e:fullstack` (`E2E_FRONTEND_PORT=14174`) → ۱۵ passed (۴۳ ثانیه)؛ `npm run test:e2e` (`E2E_FRONTEND_PORT=14173`) → ۱۹ passed؛ `npm run build` ✓؛ `npx tsc --noEmit` ✓؛ `ruff check backend domains tests scripts source_bot` ✓؛ `git diff --check` ✓ (فقط هشدار CRLF در همین فایل)؛ `pytest tests -q` → ۹۳۵ passed (۸۱۸ ثانیه، ۰ failed/error)؛ سرورهای E2E در پایان متوقف و فایل گارد شبکه غایب بودند
- [ ] محدودیت: `e2e/fullstack.spec.ts` و `e2e/news-mock.ts`/`news-priority.spec.ts` با اجرای دستی strict tsc تمیزند، ولی `apps/web/e2e/test-ports.ts` بدون `@types/node` قابل type-check نیست (پیش‌تر موجود و مستند در `e2e/node-builtins.d.ts`؛ افزودن وابستگی در این فاز انجام نشد)

---

## Definition of Done (برای همه تسک‌ها)
- Code exists
- Configuration exists
- Tests pass
- Health check passes
- Documentation updated
- No known critical error
- User can reproduce result

# F00 — Baseline، حفاظت و انتخاب checkout واقعی

**تاریخ اجرا:** ۲۰۲۶-۱۰-۲۹ محلی (UTC 2026-10-28T22:28) · **مرجع:** `GlobalIntelligence_Roadmap_Final_Local_v1.2.md` بخش F00
**قاعده:** این گزارش فقط خواندنی است؛ هیچ فایل tracked، دیتابیس یا داده‌ای تغییر نکرد. تنها نوشتن‌ها: پوشهٔ snapshot، یک backup تازه، و دیتابیس ایزولهٔ restore.

## English summary

Baseline captured without touching source, data or DB. Branch `stage95-pg-ci-verification` at `42b2278` (matches roadmap snapshot and `origin`); 25 tracked files modified + 7 untracked files are uncommitted outside the PR (F-01 reproduced). A recoverable snapshot (patch + untracked tarball + `git stash create` commit `975cb03`) was written under `backups/f00-20261028-222822/`. A fresh `pg_dump` (`gi_backup-20261028-222840.dump`, sha256 `4960dfc9…`) was created, restored into the isolated database `gi_f00_restore`, and all 20 key-table counts match. Full local suite passes (1480 passed, SQLite), `ruff` and `tsc --noEmit` and `vite build` pass, but `npm run lint` fails (no ESLint installed) and the PG lane (F-02) is still unverified. Local interpreter/versions drift from the pinned/CI set (Python 3.14.4, fastapi 0.136.1 vs pin `<0.116`, pytest 9.1.1 vs pin `<9`). 33 of the 35 audit defects were re-triageed; two (F-32/F-33) are already fixed, one partial fix (F-28/F-29 mix), six need the PostgreSQL lane.

---

## 1. Git / checkout

| قلم | مقدار |
|---|---|
| Branch | `stage95-pg-ci-verification` |
| HEAD | `42b2278e22deb19119bb8447db00bcaad4b549fb` («تست آپدیت ریدمی») |
| origin همان شاخه | `42b2278e…` — برابر با HEAD (`git ls-remote --heads origin`) |
| `origin/main` | `6e6a4b01eaeef83d43b4aac98abd634679db81cb` |
| شاخه‌های محلی | `main` (6e6a4b0)، `stage95-pg-ci-verification`*، `cbpool` (e3c6a4b) |
| staged | هیچ (`git diff --cached --stat` خالی) |
| tracked modified | ۲۵ فایل |
| untracked | ۷ مورد |
| stash-commit snapshot | `975cb03f19d090001130ae918360da16b683640b` (بدون تغییر working tree) |

**فایل‌های tracked تغییرکرده (۲۵):** `.github/workflows/ci.yml`، `.gitignore`، `AGENTS.md`، `ARCHITECTURE.md`، `PRODUCTION_READINESS.md`، `PROGRESS.md`، `ROADMAP.md`، `TASKS.md`، `apps/web/src/{api,icons,router,theme,ui}.tsx|ts`، `backend/ai/dispatch/runner.py` (+166)، `backend/ai/providers/http_base.py`، `backend/ai/schemas/types.py`، `backend/api/routers/dispatch.py` (+77)، `backend/api/routers/settings.py`، `backend/database/session.py` (connect_timeout=10 برای PG)، `db/migrations/env.py`، `domains/news/dedup.py`، `source_bot/normalizer.py` (حذف‌شده)، `tests/test_dispatch.py`، `tests/test_news_identity_phase7.py`، `tests/test_settings.py`، `tests/test_source_bot_e2e.py`.

**فایل‌های untracked (۷):** `docs/FIXES_BACKLOG.md`، `docs/ROADMAP_STAGE96_104.md`، `domains/news/run_backfill_routing.py`، `domains/news/run_screening_inventory.py`، `tests/_phase6_probe.py`، `tests/test_screening_recovery.py`، `tests/test_stage96_cost.py`.

**Working tree قبل/بعد:** قبل = همان ۲۵ modified + ۷ untracked؛ بعد = همان مجموعه بدون هیچ حذف/تغییر جدید، به‌اضافهٔ نسخهٔ untracked `docs/BASELINE_F00.md` (همین گزارش) و پوشهٔ `backups/f00-20261028-222822/` (gitignored). staged همچنان خالی است.

**تصمیم هر گروه:** همه «نگه‌دار». هیچ reset/checkout/clean انجام نشد. `source_bot/normalizer.py` و پنج فایل فرانت و `domains/news/dedup.py` + `.gitignore` از کار پاک‌سازی کد مردهٔ همین نشست هستند (مستند در ادامه).

**Snapshot قابل بازیابی:** `backups/f00-20261028-222822/` شامل `tracked.patch` (۶۰KB)، `untracked.tar` (۱۱۰KB، ۷ فایل)، `stash-commit.txt`. بازیابی: `git apply tracked.patch` + `tar -xf untracked.tar`؛ یا `git stash apply 975cb03`.

## 2. محیط

| ابزار | نسخهٔ محلی | انتظار پروژه/CI | اختلاف |
|---|---|---|---|
| Python | 3.14.4 | CI: 3.12، pin `>=3.11` | ⚠️ نسخهٔ CI متفاوت |
| fastapi | 0.136.1 | pin `>=0.115,<0.116` | ⚠️ خارج از pin |
| sqlalchemy | 2.1.3 | `>=2.0,<3` | OK |
| alembic | 1.20.0 | `>=1.13,<2` | OK |
| pytest | 9.1.1 | dev pin `>=8.0,<9` | ⚠️ خارج از pin |
| Node / npm | 24.16.0 / 11.13.0 | CI: Node 20 | ⚠️ نسخهٔ CI متفاوت |
| Docker / Compose | 29.8.2 / v5.6.0 | — | OK |
| PostgreSQL (container) | 16.15 (alpine) | CI: postgres:16 | OK |
| psql CLI روی host | ندارد | — | کوئری‌ها با `docker exec` انجام شد |

⚠️ یعنی «سبز بودن محلی» روی نسخه‌هایی اثبات شده که با pin/CI یکی نیست؛ این در F02 (بازگرداندن لاین PG/CI) باید با محیط pin‌شده تکرار شود.

## 3. Container / service

| نام | image | وضعیت | پورت |
|---|---|---|---|
| `gi_backend` | `globalintelligence-backend:latest` (ساخته 2026-10-28T13:13Z) | Up 9h · **healthy** | 127.0.0.1:8000 |
| `gi_frontend` | `globalintelligence-frontend:latest` (2026-10-16) | Up 12h | 127.0.0.1:5173 |
| `gi_postgres` | `postgres:16-alpine` | Up 12h · healthy | 127.0.0.1:15432 |
| `gi_n8n` | `n8nio/n8n:2.42.6` | Up 12h | 127.0.0.1:5678 |
| `my-postgres16` (غیرپروژه) | `postgres:16` | Up 12h | 5432 |
| `gi_staging_backend` / `gi_staging_postgres` | staging | Up 11h · healthy | 8001 / 15433 |

- `GET /health` → `{"status":"ok"}` · `GET /health/db` → `{"status":"ok","database":{"ok":true,"server":"PostgreSQL 16.15 …","migration":"88a9b2c1d4e5"}}` · فرانت `HTTP 200`.
- **نکتهٔ F01:** image بک‌اند ۹ ساعت پیش ساخته شده، در حالی که working tree تغییرات commit‌نشده دارد؛ اینکه کانتینر همین کد را اجرا می‌کند **اثبات نشده** و در F01 با version marker بررسی می‌شود.

## 4. دیتابیس و migration

- `alembic heads` → `88a9b2c1d4e5 (head)`؛ دیتابیس زنده همان `88a9b2c1d4e5` را گزارش می‌کند ⇒ یک head، هم‌راستا.
- ۴۲ جدول در schema `public`.
- شمارش read-only (دیتابیس زنده): `sources=229`, `documents=2102`, `articles=2102`, `events=827`, `claims=842`, `evidence=189`, `article_dispatches=529`, `job_runs=1499`, `ai_token_ledger=0`, `alert_rules=0`, `alerts=0`.
- وضعیت dispatch: `screening@v1` → terminal=516؛ `evidence_collection@v1` → terminal=2؛ بقیه (claim_extraction, claim_independence, domain_geopolitics, domain_routing, event_extraction, graph_extraction) → completed. **هیچ pending/retryable در دیتابیس زنده نیست** (پیش‌نیاز F10).

## 5. Backup و restore (اثبات‌شده)

| قلم | مقدار |
|---|---|
| فرمان | `python -m scripts.db_backup backup --dir backups --keep 7` |
| فایل | `backups/gi_backup-20261028-222840.dump` (+ `.manifest.json`) |
| sha256 | `4960dfc90359…` (در manifest کامل ثبت شده) |
| restore | `python -m scripts.db_backup restore --file … --target-db gi_f00_restore --yes` → `restore ok` |
| verify | `python -m scripts.db_backup verify --target-db gi_f00_restore` → **`verify ok: all counts match`** (۲۰ جدول کلیدی) |
| دیتابیس ایزوله | `gi_f00_restore` (می‌توان بعداً drop کرد؛ دادهٔ زنده دست‌نخورده) |

backupهای قدیمی (۲ فایل ۱۲ اکتبر) دست‌نخورده ماندند؛ rotation چیزی حذف نکرد.

## 6. دروازه‌های اجرایی (شاهد امروز)

| دروازه | فرمان | نتیجه |
|---|---|---|
| Lint | `ruff check backend domains tests scripts source_bot` | **All checks passed** |
| Full suite (SQLite) | `python -m pytest tests -q --basetemp=.pytest-tmp-…` | **1480 passed** در 19:56 |
| Typecheck | `npx tsc --noEmit` (apps/web) | **0 خطا** |
| Build | `npm run build` | **موفق** (324 kB JS / 31 kB CSS) |
| Frontend lint (F-22) | `npm run lint` | **FAILED**: `'eslint' is not recognized` |
| Migration روی SQLite (F-12) | `DATABASE_URL=sqlite:///… alembic upgrade head` | **FAILED**: `NotImplementedError: No support for ALTER of constraints in SQLite dialect` |
| Test وابسته به cwd (F-09) | `cd backend && pytest ../tests/test_deploy.py -k check_local_files` | **FAILED** (۶ آیتم اضافه: `docker-compose.yml`, …) |
| PostgreSQL lane (F-02/F-05/F-06/F-11) | — | **اجرا نشد** (نیازمند DB ایزوله + اتصال امن؛ در F02.1) |
| E2E (F-34) | — | اجرا نشد؛ در CI هم وجود ندارد |

## 7. Triage دفتر ۳۵ نقص (شاهد تازه، نه نقل گزارش قدیمی)

| ID | وضعیت | شاهد امروز | مرحلهٔ بستن |
|---|---|---|---|
| F-01 تغییرهای commit‌نشده بیرون PR | **REPRODUCED** | `git status`: ۲۵ tracked + ۷ untracked؛ snapshot گرفته شد | تصمیم مالک (بند ۶ نقشه) |
| F-02 deadlock `test_claim_is_atomic` روی PG | **PENDING_F02** | نیازمند لاین PG ایزوله؛ `tests/test_dispatch.py` در working tree تغییر کرده | F02.1 |
| F-03 CI فقط subset | **REPRODUCED** | `ci.yml:52` پنج فایل، `ci.yml:56` سه فایل؛ کل suite اجرا نمی‌شود | F02.4 |
| F-04 شاهد PR/CI | **PARTIAL** | `git ls-remote`: `origin/stage95=42b2278` = HEAD؛ PR state نه (`gh` نصب نیست) | F02 (refresh SHA) |
| F-05 چهار تست discover با `ConnectionTimeout` | **PENDING_F02** | نیازمند PG | F02.2 |
| F-06 چهار تست missing-article با FK | **PENDING_F02** | FK فقط در PG اعمال می‌شود | F02.2 |
| F-07 دو assert سخت SQLite | **REPRODUCED (static)** | `test_fullstack_integration.py:117`, `test_source_bot_validation.py:104` | F02.2 |
| F-08 patch DNS بی‌اثر | **REPRODUCED (static)** | `conftest.py:87` روی `domains.news.source_verify`؛ `source_bot/security.py:13` import مقداری | F02.3 |
| F-09 تست وابسته به cwd | **REPRODUCED** | اجرا از `backend/` → FAILED با ۶ آیتم اضافه | F02.5 |
| F-10 temp مشترک/`pytest-current` | **PARTIAL** | suite امروز با `--basetemp` تازه سبز شد؛ basetemp پیش‌فرض اندازه‌گیری نشد | F02.5 |
| F-11 claim بدون `SKIP LOCKED` | **PENDING_F02** | نیازمند PG و worker هم‌زمان | F02.1 |
| F-12 زنجیرهٔ migration روی SQLite | **REPRODUCED** | `NotImplementedError: No support for ALTER of constraints…` | F02/مستندسازی |
| F-13 نبود ابزار «کد مرده/شاخهٔ دست‌نیافتنی» | **OPEN** | vulture فقط دستی اجرا شد؛ هیچ دروازه‌ای در repo/CI نیست | F02/F14 |
| F-14 race ساخت JobRun | **REPRODUCED (static)** | `source_bot/jobs.py:29-47` check-then-insert؛ `job_runs` قید یکتا ندارد | F09/F14 |
| F-15 AdaptiveRouter بی‌مصرف‌کننده | **CONFIRMED** | تنها فراخوان‌ها: `api/routers/ai_routing.py:59` و CLI `domains/ai_routing/run_routes.py` | F12.1 |
| F-16 ETag بی‌اثر | **CONFIRMED** | تنها ساخت: `source_bot/runner.py:152` درون هر fetch | F09 |
| F-17 قفل runner = فایل temp | **CONFIRMED** | `source_bot/runner.py`: `LOCK_PATH = tempdir/source_bot.lock` | F09 |
| F-18 N+1 و load تمام‌جدولی | **UNMEASURED** | نیازمند profile قبل از بهینه‌سازی | F14.2 |
| F-19 endpoint سنگین در request thread | **UNMEASURED** | نیازمند سنجش latency/timeout | F09/F14 |
| F-20 `topics/entities` از نوع Text | **CONFIRMED** | `backend/database/models/article.py:33-34` | F14.3 |
| F-21 خوشهٔ dedup در API نیست | **CONFIRMED** | `ArticleClassifiedRead` (`api/routers/classify.py:41-52`) فیلد `duplicate_cluster` ندارد | F12.1 |
| F-22 lint/typecheck فرانت ناقص | **REPRODUCED** | `npm run lint` → `'eslint' is not recognized`؛ CI فقط `npm run build` (`ci.yml:78`) | F14.1 |
| F-23 rate limit درون‌فرایندی | **CONFIRMED** | `backend/core/security.py:38` «درون‌حافظه‌ای»، `rate_limit_per_minute=600` | F12.1/F14 |
| F-24 آستانه/confidence کالیبره‌نشده | **CONFIRMED** | هارنس هست (`backend/ai/evaluation/local_screening.py`) ولی dataset برچسب‌خوردهٔ انسانی نیست | F04 |
| F-25 تحویل هشدار غایب | **CONFIRMED** | هیچ telegram/smtp/smtplib در `backend/`, `domains/`, `integrations/n8n/workflows` نیست | F12.2 |
| F-26 retention/disk monitoring غایب | **CONFIRMED** | هیچ `disk_usage`/`retention` در کد نیست (فقط متن privacy در free_policy) | F13.1 |
| F-27 Scrapy فقط IPv4 | **CONFIRMED (مستند خودش)** | `source_bot/adapters/scrapy_policy.py` docstring: «فقط IPv4 … fail-closed» | F06 |
| F-28 ROADMAP پایان Phase 52 | **ALREADY_FIXED** | `ROADMAP.md:6,396`: «Phase 52 پایان فازهای ۰–۵۲ بود، نه پایان پروژه» | F14.4 |
| F-29 TASKS ادعای کهنه ruff | **PARTIAL** | `TASKS.md:11` اصلاح شده؛ `TASKS.md:39` هنوز «فاقد `source_bot/`» می‌گوید | F14.4 |
| F-30 AUDIT_REPORT روی HEAD قدیمی | **CONFIRMED** | تاریخ 2026-10-09، مبنا `7d7ed17` | F14.4 |
| F-31 تعارض شمارهٔ Stage | **CONFIRMED** | `runner.py:152,172,447,526` و `session.py:32` → Stage96/97.1/104 | F14.4 |
| F-32 `.gitignore` ناقص | **ALREADY_FIXED (این نشست)** | الگوهای `pg*.txt`، `pytest-*.txt`، `.pytest-tmp*/`، `.pytest-pg-tmp/`، `pytest_temp/`، `.freebuff/`، `.tmp-*/` افزوده شد | — |
| F-33 زبالهٔ untracked ریشه | **ALREADY_FIXED (این نشست)** | ۱۴ فایل + ۳ پوشه حذف شد؛ `git status` دیگر آن‌ها را نشان نمی‌دهد | — |
| F-34 E2E در CI اجرا نمی‌شود | **CONFIRMED** | `ci.yml` هیچ مرحلهٔ playwright/e2e ندارد؛ `apps/web/e2e/` موجود است | F14/F12.1 |
| F-35 عدد کهنه در AGENTS | **NOT_REPRODUCED** | AGENTS «106 فایل / ~1480 تست»؛ واقعی ۱۰۸ فایل و **1480 تست** (تفاوت جزئی فایل‌ها) | F14.4 |

**جمع:** ۲ مورد رفع‌شده، ۱ مورد فقط جزئی، ۱۱ مورد بازتولید/تأییدشده با شاهد امروز، ۶ مورد نیازمند لاین PG (F-02/F-05/F-06/F-11 + بخشی از F-07/F-10)، ۲ مورد نیازمند اندازه‌گیری (F-18/F-19)، ۲ مورد نیازمند تصمیم مالک (F-01، F-04).

## 8. ریسک‌ها و محدودیت‌های ثبت‌شده

1. **تغییرات commit‌نشده (F-01) تنها نسخهٔ WIP هستند** — snapshot گرفته شد ولی تا commit/stash آگاهانهٔ مالک در معرض از دست رفتن‌اند.
2. **اختلاف محیط محلی با pin/CI** (Python 3.14، fastapi 0.136، pytest 9.1، Node 24) — سبز بودن محلی تضمین CI نیست.
3. **کانتینر بک‌اند ممکن است کد قدیمی را اجرا کند** (image ۹ ساعت پیش، working tree جدیدتر) — F01.
4. **لاین PostgreSQL اجرا نشد**؛ P0 (F-02) و پنج مورد P1 هنوز فقط «گزارش‌شده» هستند، نه «اندازه‌گیری‌شده».
5. **PR/CI راه‌دور بازبینی نشد** (نبود `gh`/توکن)؛ فقط برابری SHA شاخه‌ها تأیید شد.
6. هیچ secret در این گزارش نیست؛ `.env` فقط از نظر وجود (۹۴ خط) بررسی شد و مقادیرش خوانده/چاپ نشد.

## 9. دروازهٔ F00

| معیار | نتیجه |
|---|---|
| Baseline شامل branch/HEAD/تغییرات/محیط/container/DB-مigration/شمارش/تست | ✅ |
| شناسایی همهٔ فایل‌های کاربر و untracked ارزشمند، بدون از دست رفتن تغییر | ✅ (snapshot + فهرست) |
| نبود secret در گزارش | ✅ |
| اثبات backup و restore در DB آزمایشی | ✅ (`verify ok: all counts match`) |

**Status: VERIFIED** (با دو زیرمورد خارجی NOT_VERIFIED: PR state، و لاین PG که به F02 منتقل شده است).

## 10. Next single task (auto-start ممنوع)

**F01 — تشخیص build، hash mismatch و اثبات اجرای Backend جدید:** build/بازسازی image بک‌اند، بررسی بازتولید hash mismatch، و اثبات با version marker که کانتینر کد فعلی را اجرا می‌کند؛ بدون پاک‌کردن volume/DB و بدون خاموش‌کردن hash verification.

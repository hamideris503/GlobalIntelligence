# فهرست نقص‌ها و باگ‌های GlobalIntelligence

**تاریخ:** ۲۸ اکتبر ۲۰۲۶ · **مبنا:** `stage95-pg-ci-verification` (`9292754`) + وضعیت کاری روی دیسک
**قاعده:** هر قلم با شاهد آمده است. اقلامی که از `TASKS.md` / `PROGRESS.md` / `PRODUCTION_READINESS.md` گرفته شده‌اند و دوباره اجرا نشده‌اند، با برچسب **«گزارش‌شده»** مشخص شده‌اند؛ بقیه **«اندازه‌گیری‌شده»** هستند.

## English summary

35 defects/debts, grouped by severity. P0 blocks the merge (uncommitted work outside the PR,
a PostgreSQL deadlock, CI down to ~5% coverage). P1 breaks the PostgreSQL run (10 failures,
a fake "offline" resolver, cwd- and temp-dependent tests). P2 is documented engineering debt.
P3 is doc/hygiene drift. Each entry lists symptom + evidence, cause, fix and the command that
proves the fix.

---

## خلاصهٔ شمارش

| سطح | تعداد | معنی |
|---|---|---|
| P0 | ۴ | ادغام/CI را مسدود می‌کند |
| P1 | ۹ | درستی یا قابلیت اتکا را می‌شکند |
| P2 | ۱۴ | بدهی فنی شناخته‌شده |
| P3 | ۸ | هم‌راستایی مستندات و بهداشت مخزن |

---

# P0 — مسدودکننده

### F-01 · تغییرهای commit‌نشده بیرون از PR — **اندازه‌گیری‌شده**
- **علامت:** ۱۱ فایل tracked تغییر‌یافته + فایل‌های جدید untracked روی دیسک، هیچ‌کدام در `9292754` نیستند.
- **شاهد:** `git status --porcelain` → `M backend/ai/dispatch/runner.py`, `M backend/api/routers/dispatch.py`, `M backend/database/session.py`, `M db/migrations/env.py`, `M .github/workflows/ci.yml`, `M tests/{test_dispatch,test_settings,test_news_identity_phase7}.py`, … + `?? tests/test_screening_recovery.py`, `?? tests/test_stage96_cost.py`.
- **ریسک:** بازبینی PR این کار را نمی‌بیند؛ یک `reset/checkout` آن را از بین می‌برد.
- **اصلاح:** تصمیم آگاهانه commit یا stash + ثبت hash پایه.
- **اثبات:** `git status --porcelain` تمیز.

### F-02 · deadlock دیسپچ روی PostgreSQL — **اندازه‌گیری‌شده**
- **علامت:** `tests/test_dispatch.py::test_claim_is_atomic` روی PG هرگز تمام نمی‌شود.
- **شاهد:** `pg_stat_activity` → یک session `idle in transaction` (SELECT روی articles) + یک session با `wait_event_type=Lock, wait_event=transactionid` روی `UPDATE article_dispatches … attempts = attempts + 1`، هر دو ۱۶+ دقیقه؛ بازتولید تک‌فایل: timeout در ۱۰۰s. همان فایل روی SQLite: ۳۴ تست در ۳٫۴۵s پاس.
- **علت:** تست دو `Session` جدا باز می‌کند؛ `claim` اول ردیف را قفل می‌کند و تا `commit` در پایان تست، `claim` دوم روی همان ردیف بلوکه می‌شود. روی SQLite (یک اتصال مشترک) این قفل متقابل رخ نمی‌دهد.
- **اصلاح:** بازطراحی تست (دو تراکنش/دو thread با commit واقعی، یا سنجش `rowcount` بدون قفل متقابل). مرتبط با F-11.
- **اثبات:** تست روی PG زیر ۵ ثانیه پاس + `pytest tests -q` با PG بدون deadlock.
- **وضعیت F02: FIXED** — علت در خود تست بود (دو session با قفل باز)؛ بازنویسی با تراکنش‌های commit‌شده + تست دو-thread جدید. شاهد: `test_claim_is_atomic` روی PG در 0.36s و کل suite روی PG ۱۴۸۳ passed / ۰ failed (`docs/F02_PG_LANE.md`).

### F-03 · CI شاخه به ~۵٪ تست‌ها کاهش یافته — **اندازه‌گیری‌شده**
- **علامت:** مرحلهٔ تست PG فقط ۴ فایل را اجرا می‌کند؛ در `main` کل suite اجرا می‌شد.
- **شاهد:** `.github/workflows/ci.yml` (HEAD) → `pytest tests/test_article_dispatch_migration.py` + `pytest tests/test_screening*.py …` = ۷۷ تست از ۱۴۸۰ (۱۰۶ فایل). تاریخچه: `8d143d7`، `932e4c3`، `b725ea3`، `9292754` («replace full suite with focused regression subset»).
- **ریسک:** دقیقاً همان deadlock و ۱۰ شکست PG را پنهان کرده است؛ ضمناً هیچ‌یک از تست‌های dispatch/classification/ingestion جدید در CI اجرا نمی‌شود.
- **اصلاح:** بازگرداندن `pytest tests -q` روی PG پس از F-02/F-05/F-06/F-07.
- **اثبات:** لاگ CI با ~۱۴۸۰ تست و `0 failed`.
- **وضعیت F02: PARTIAL** — CI اکنون `pytest tests -q` روی PG اجرا می‌کند (timeout جاب ۳۰→۴۰، مرحله ۳۰ دقیقه) و همان دستور محلی ۱۴۸۳/۰ است؛ اجرای واقعی CI هنوز تأیید نشده.

### F-04 · نبود شاهد برای وضعیت PR/CI راه‌دور — **تأیید‌نشده**
- **علامت:** ادعای «CI در ۲۵ اکتبر سبز بود» و «PR #1 باز است» در مخزن قابل تأیید نیست.
- **اصلاح:** پس از دسترسی شبکه، لینک اجرا و وضعیت PR در `PROGRESS.md` ثبت شود؛ تا آن زمان `NOT_VERIFIED`.

---

# P1 — درستی و قابلیت اتکا

### F-05 · ۴ تست Settings روی PG با `ConnectionTimeout` — **اندازه‌گیری‌شده (علت تأییدشده)**
- **شاهد:** `tests/test_settings.py::{test_discover_ignores_hostile_proxy_and_ca_env, test_discover_redirect_not_followed, test_discover_oversized_body_rejected, test_discover_timeout_and_key_safety}` → `psycopg.errors.ConnectionTimeout`. روی PG تازه و به‌صورت تک‌فایل هم بازتولید شد.
- **علت:** `_mock_public_dns()` به‌صورت سراسری `socket.getaddrinfo` را patch می‌کند تا همه‌چیز به `93.184.216.1` حل شود؛ `tests/conftest.py` در حالت PG از `NullPool` استفاده می‌کند (هر درخواست = اتصال جدید) و DSN شامل `localhost` است → اتصال DB هم به همان IP جعلی هدایت و تا ۱۰s تایم‌اوت می‌شود.
- **تأیید:** با `DATABASE_URL` روی `127.0.0.1` همان ۵ تست `discover` پاس شدند (۵ passed).
- **اصلاح:** DSN تست/CI روی IP، یا محدودکردن دامنهٔ پچ DNS به ماژول هدف، یا pool مناسب در تست.
- **اثبات:** `pytest tests/test_settings.py -q` روی PG → ۰ failed.
- **وضعیت F02: FIXED** — DSN تست در حالت PG به IP literal تبدیل می‌شود (`make_url().set(host="127.0.0.1")`)؛ `tests/test_settings.py` روی PG ۵۳ passed.

### F-06 · ۴ تست «مقالهٔ گمشده» روی PG با `ForeignKeyViolation` — **اندازه‌گیری‌شده**
- **شاهد:** `test_domain_engines.py::{test_geopolitics_missing_article_is_terminal, test_society_missing_article_is_terminal}` و `test_domain_routing.py::{test_domain_routing_missing_article_is_terminal, test_claim_independence_missing_article_is_terminal}` → `insert or update on table "article_dispatches" violates foreign key constraint "article_dispatches_article_id_fkey"`.
- **علت:** helper تست `_orphan()` عمداً dispatch بدون مقالهٔ موجود می‌سازد؛ SQLite به‌طور پیش‌فرض FK را اعمال نمی‌کند، PG اعمال می‌کند. نتیجهٔ مهم‌تر: **حالت «dispatch بدون مقاله» در PG قابل وقوع نیست**، پس شاخهٔ terminal برای مقالهٔ گمشده عملاً دست‌نیافتنی است.
- **اصلاح:** تصمیم صریح — یا شاخهٔ گمشده در سطح handler با ورودی ساختگی تست شود (بدون نقض FK)، یا شاخه به‌عنوان «غیرقابل‌رخداد» حذف/مستند شود.
- **اثبات:** ۴ تست روی PG بدون نقض FK و با پوشش واقعی مسیر terminal.
- **وضعیت F02: FIXED** — پوشش به قرارداد handler منتقل شد (ردیف در حافظه، بدون insert)؛ هر چهار تست روی PG پاس و `detail` شامل `article not found` بررسی می‌شود.

### F-07 · ۲ تست که صراحتاً SQLite را assert می‌کنند — **اندازه‌گیری‌شده**
- **شاهد:** `tests/test_fullstack_integration.py:117` → `assert 'sqlite' in …` · `tests/test_source_bot_validation.py:104` → `assert seen["driver"] == "sqlite"`.
- **اصلاح:** assert روی «همان bind تست» یا `skipif` صریح.
- **اثبات:** اجرای هر دو روی PG → pass یا skip مستند.
- **وضعیت F02: FIXED** — هر دو assert به «همان bind تست» تغییر کرد؛ هر دو روی PG پاس. بازرسی متن DDL ایندکس در `test_news_identity_phase7` هم به SQLite محدود شد (اعمال قید در هر دو لاین سنجیده می‌شود).

### F-08 · تضمین «آفلاین» تست‌ها روی مسیر source_bot برقرار نیست — **اندازه‌گیری‌شده**
- **علامت:** کندترین تست‌ها ۲۴ ثانیه؛ کل suite ۱۵:۱۲.
- **شاهد:** `tests/conftest.py:87` فقط `source_verify.resolve_host_ips` را patch می‌کند، اما `source_bot/security.py:13` تابع را با import مقداری گرفته است → آن patch روی source_bot اثر ندارد و هر تست ingest واقعاً DNS می‌زند.
- **اصلاح:** patch روی `source_bot.security.resolve_host_ips` (یا import ماژولی) + تست محافظ «هیچ resolve واقعی رخ نداد».
- **اثبات:** کاهش محسوس زمان suite + سبز شدن تست محافظ.
- **وضعیت F02: FIXED** — `source_bot.security` با import ماژولی، و `socket.getaddrinfo` برای TLDهای رزروشدهٔ RFC 6761 بسته شد؛ تست محافظ در `tests/test_security.py`. شاهد: SQLite از ~۱۵:۱۲ به ۷:۲۲.

### F-09 · تست وابسته به cwd — **اندازه‌گیری‌شده**
- **شاهد:** `tests/test_deploy.py::test_check_local_files` از ریشهٔ مخزن ۵/۵ پاس، از `backend/` فِیل (`assert ['docker-comp…'] == []`).
- **اصلاح:** مسیرها نسبت به `Path(__file__).resolve().parents[1]`.
- **اثبات:** سبز شدن از هر دو cwd.
- **وضعیت F02.5: FIXED** — تست ریشه را از `Path(__file__).resolve().parents[1]` می‌سازد؛ از root و `backend/` پاس می‌شود.

### F-10 · وابستگی به پوشهٔ temp سیستم (فِیل کاذب) — **اندازه‌گیری‌شده**
- **شاهد:** اجرای پرتکرار/موازی تست‌ها → `PermissionError: [WinError 5] …\pytest-of-<user>\pytest-current` و ۱۳ فِیل کاذب؛ با `--basetemp` تازه همه پاس شدند.
- **اصلاح:** مستندسازی `--basetemp` برای اجرای موازی، یا fixture/naming مستقل از symlink `pytest-current`.
- **اثبات:** دو اجرای متوالی/موازی بدون خطای دسترسی.
- **وضعیت F02.5: FIXED** — علت ریشه‌ای: `pytest-current` یک symlink دایرکتوری است و `Path.unlink()` ویندوز روی symlink مرده `WinError 5` می‌دهد (`_pytest/pathlib.py:cleanup_dead_symlinks`)؛ هر اجرا پس از retention دور ریخته می‌شد. `tests/conftest.py` حالا `PYTEST_DEBUG_TEMPROOT` را به یک ریشهٔ اختصاصی هر اجرا (`gi-pytest-<pid>-*`) می‌برد و در exit پاک می‌کند، پس ریشهٔ مشترک و symlink آن هرگز لمس نمی‌شود. تست محافظ: `tests/test_temp_isolation.py`. بدون هیچ فلگ `--basetemp` روی همان temp آلودهٔ قبلی، اجراهای متوالی و موازی پاس شدند.

### F-11 · `claim` بدون `SKIP LOCKED` — **اندازه‌گیری‌شده (با اثر طراحی)**
- **شاهد:** `backend/ai/dispatch/service.py:229` یک `UPDATE … WHERE id=… AND status IN (…)` است.
- **اثر:** دو worker هم‌زمان پشت یک ردیف می‌ایستند (سریال) تا اولی commit کند؛ در محیط چند-worker به تأخیر و در تست به deadlock می‌رسد.
- **اصلاح:** `SELECT … FOR UPDATE SKIP LOCKED` یا معادل آن در claim دسته‌ای.
- **اثبات:** تست دو worker هم‌زمان بدون بلوکه‌شدن؛ هر ردیف فقط یک بار claim شود.

### F-12 · زنجیرهٔ migration روی SQLite قابل اجرا نیست — **اندازه‌گیری‌شده**
- **شاهد:** `DATABASE_URL=sqlite:///… alembic upgrade head` → `NotImplementedError: No support for ALTER of constraints in SQLite dialect`.
- **اثر:** «سبز بودن migration» فقط روی PG معنا دارد؛ تست‌های SQLite به `create_all` وابسته‌اند و این تفاوت باید در مستندات اجرا صریح باشد.
- **اصلاح:** مستندسازی (یا batch mode اگر SQLite واقعاً لازم است) + آزمون‌های migration فقط روی PG.

### F-13 · نبود ابزار واحد برای تشخیص «کد مرده/شاخهٔ دست‌نیافتنی» — **اندازه‌گیری‌شده**
- **شاهد:** F-06 نشان داد یک شاخهٔ terminal برای داده‌ای است که در PG قابل ساخت نیست؛ هیچ تستی این را نمایان نمی‌کرد.
- **اصلاح:** در Stage 96-۳ هر شاخهٔ خطای handler یک تست با دادهٔ واقعی PG داشته باشد.

---

# P2 — بدهی فنی شناخته‌شده

> اقلام این بخش از `TASKS.md` / `PRODUCTION_READINESS.md` گرفته شده‌اند و در این بازبینی دوباره اجرا نشده‌اند؛ پیش از بستن، بازآزمایی لازم دارند.

### F-14 · race ساخت JobRun — **گزارش‌شده**
`create_job` الگوی check-then-insert دارد (`source_bot/jobs.py:29-48`) و unique constraint فعال نیست ⇒ دو POST هم‌زمان دو job می‌سازد؛ بازنده در `run_job` بی‌صدا رها می‌شود و ردیف pending تا restart بقیه را ۴۰۹ می‌کند. اصلاح: ایندکس یکتای جزئی (migration) یا قفل درون‌پروسه‌ای.

### F-15 · Adaptive Router بی‌اثر — **گزارش‌شده**
`AdaptiveRouter.record` و `POST /api/ai-routing/record` وجود دارند ولی هیچ مصرف‌کنندهٔ خودکاری آن را صدا نمی‌زند. پیش از اتصال: (۱) دقیقاً یک ثبت per generate حتی با retry/fallback، (۲) صفر ثبت در `MOCK_MODE`، (۳) خطای DB پاسخ AI را نشکند، (۴) بدون commit ناخواسته روی session درخواست، (۵) رفتار race روی `uq_provider_run`.

### F-16 · ETag/Last-Modified بی‌اثر — **گزارش‌شده**
`RestJsonAdapter` در هر fetch نو ساخته می‌شود (`source_bot/runner.py:134`) ⇒ `self._etag`/`self._last_mod` همیشه خالی و `If-None-Match` هرگز فرستاده نمی‌شود. راهکار سازگار: نمونهٔ process-scoped یا ذخیره در `Source.endpoint_config`.

### F-17 · قفل ربات = فایل temp — **گزارش‌شده**
`source_bot/runner.py:32` → فقط درون یک host هماهنگ می‌کند؛ job نیمه‌کاره بعد از restart فقط `failed` می‌شود و resume نمی‌شود.

### F-18 · N+1 و load تمام‌جدولی — **گزارش‌شده**
adjacency گراف، replay تمام‌جدولی، load کامل macro در context (scorecard قبلاً با کش per-symbol رفع شده).

### F-19 · endpointهای سنگین در request thread — **گزارش‌شده**
انتقال به `workers/` (که فعلاً فقط `.gitkeep` دارد) باید با آزمون و نیاز عملیاتی توجیه شود.

### F-20 · `topics`/`entities` از نوع Text — **گزارش‌شده**
مهاجرت به JSONB با migration سازگار، دادهٔ قدیمی، ایندکس و rollback برنامه‌ریزی‌شده.

### F-36 · replay با دورهٔ جاری به‌جای دورهٔ ذخیره‌شده — **برطرف شد**
`rerun()` موتورهای دوره‌محور را بدون `period` اجرا می‌کرد؛ replay دادهٔ ماه قبل ردیف ماه جدید می‌ساخت و drift کاذب گزارش می‌شد (`matches=False` در `test_replay_all_supported_engines_match`). حالا `latest_period()` دورهٔ ذخیره‌شده را پین می‌کند. شاهد: `docs/FIX_REPLAY_PERIOD.md`.

### F-21 · نمایش خوشه‌های dedup در UI نیست — **برطرف شد (F12.1.1)**
`ArticleClassifiedRead`/`ArticleDetailRead` فیلد `duplicate_cluster` دارند و `/api/dedup/clusters?cluster=` فیلتر سمت سرور دارد (به‌جای برگرداندن کل جدول)؛ صفحهٔ جزئیات خبر خوشهٔ خودش را fetch می‌کند. شاهد: `docs/F12_1_1_DEDUP_CLUSTER_API.md`.

### F-22 · `npm run lint` در فرانت‌اند شکست می‌خورد — **گزارش‌شده**
اسکریپت `lint` هست، اما eslint نه در dependency، نه در lockfile و نه config دارد؛ CI فقط `npm run build` را اجرا می‌کند (بدون `tsc --noEmit`).

### F-23 · rate limit تک‌فرایندی — **گزارش‌شده**
با چند worker نیازمند Redis؛ فعلاً محدودیت مستندشده.

### F-24 · آستانه/confidence کالیبره‌نشده — **گزارش‌شده**
v1 ثابت است؛ Stage 104/97 آن را هدف می‌گیرد.

### F-25 · نبود تحویل هشدار — **اندازه‌گیری‌شده**
`domains/alerts/engine.py` فقط `evaluate/acknowledge/resolve` دارد؛ هیچ کانال Telegram/Email/SMTP در کد نیست.

### F-26 · نبود Retention و پایش دیسک — **اندازه‌گیری‌شده**
هیچ `shutil.disk_usage` یا سیاست retention در کد نیست؛ فقط rotation بکاپ وجود دارد.

### F-27 · Scrapy فقط IPv4 — **گزارش‌شده**
`source_bot/adapters/scrapy_policy.py:22` → مقصدی که فقط AAAA دارد fail-closed است.

---

# P3 — مستندات و بهداشت مخزن

### F-28 · `ROADMAP.md` هنوز Phase 52 را پایانی می‌داند — **اندازه‌گیری‌شده**
هیچ بخشی برای Stage 88–95 یا 96+ ندارد؛ کلمهٔ «Stage» فقط یک بار (در بخش Post-52) آمده. باید به `docs/ROADMAP_STAGE96_104.md` ارجاع دهد.

### F-29 · `TASKS.md` ادعای کهنه دارد — **اندازه‌گیری‌شده**
می‌گوید `ruff check …` شامل `source_bot/` نیست، در حالی که در HEAD شامل است و lint پاس می‌شود (`All checks passed`).

### F-30 · `AUDIT_REPORT.md` روی HEAD قدیمی — **اندازه‌گیری‌شده**
تاریخ ۲۰۲۶-۱۰-۰۹ و مبنای `7d7ed17`؛ وضعیت فعلی را توصیف نمی‌کند.

### F-31 · تداخل شماره‌گذاری Stage — **اندازه‌گیری‌شده**
کامنت‌های کد از «Stage96» برای بهینه‌سازی perf، «Stage97.1» برای `connect_timeout` و «Stage104» برای `screening_history` استفاده می‌کنند؛ در حالی که در نقشه‌راه ۹۶ = تثبیت و ۱۰۴ = کالیبراسیون. نیاز به یک مرجع واحد + شناسهٔ تسک در کد.

### F-32 · `.gitignore` ناقص برای خروجی‌های تولیدشده — **اندازه‌گیری‌شده**
`pg*.txt`، `pytest-*.txt`، `.pytest-tmp*/`، `.pytest-pg-tmp/`، `pytest_temp/`، `.freebuff/` پوشش داده نشده‌اند.

### F-33 · زبالهٔ untracked در ریشه — **اندازه‌گیری‌شده**
۱۵ فایل/پوشه (`pg1..pg8.txt`، `pg-run.txt`، `pytest-out.txt`، `pytest-pg-full*.txt`، `_api_check.py`، `_db_audit19.py`، `.pytest-tmp*`، `.freebuff/`). هیچ DSN یا مقدار محرمانه‌ای در آن‌ها یافت نشد (بررسی فقط برای الگوی اتصال)، اما باید حذف و gitignore شوند.

### F-34 · E2E وجود دارد ولی هیچ‌جا اجرا نمی‌شود — **اندازه‌گیری‌شده**
`apps/web/e2e/` شامل `screening-ops.spec.ts` و `playwright.config.ts`؛ CI فقط `npm ci` + `npm run build` دارد. باید یا اجرا شود یا صریح «خارج از دامنه» اعلام شود.

### F-35 · `AGENTS.md` عدد کهنه دارد — **اندازه‌گیری‌شده**
«~۶۵ `test_*.py`» در حالی که ۱۰۶ فایل در HEAD و ۱۱۳ فایل در پوشهٔ tests است.

---

# وضعیت به‌روزشده — ۴ نوامبر ۲۰۲۶ (QA-00)

| قلم | وضعیت قبلی | وضعیت فعلی | شاهد |
|---|---|---|---|
| F-11 `claim` بدون `SKIP LOCKED` | اندازه‌گیری‌شده | **VERIFIED (single-row atomic)** — `UPDATE … WHERE status IN (…)` با بررسی `rowcount` | `tests/test_dispatch.py` در هر دو لاین پاس |
| F-14 race ساخت JobRun | باز | **CLOSED** — ایندکس یکتای جزئی `uq_job_runs_active` + `IntegrityError` | تست جدید `test_job_runs_active_unique_index_blocks_second_active_row` |
| F-15 AdaptiveRouter بی‌اثر | باز | **CLOSED** — `adaptive_bootstrap` در lifespan با فلگ پیش‌فرض خاموش | `tests/test_adaptive_bootstrap.py`, `backend/main.py:130` |
| F-16 ETag بی‌اثر | باز | **CLOSED** — کش process-scoped | تست جدید `test_rest_json_conditional_headers_survive_adapter_rebuild` |
| F-22 lint فرانت‌اند | گزارش‌شده | **CLOSED** — eslint config + dependency؛ ۰ خطا / ۱۶ warning | `npm run lint` exit 0 |
| F-27 IPv6 | باز | **CLOSED** — loopback/private IPv6 مسدود | `tests/test_security.py`, `docs/F27_IPV6.md` |
| F-20 topics/entities → JSONB | باز | باز (تصمیم schema) | — |
| F-23 rate limit چندفرایندی | باز | باز (مستند؛ نیاز Redis در صورت scale-out) | `docs/F23_RATE_LIMIT.md` |

**دادهٔ اندازه‌گیری‌شده:** SQLite `1570 passed / 1 skipped`؛ PostgreSQL `1573 passed / 0 failed`
روی دیتابیس موقتِ ساخته‌شده از schema خالی و سپس حذف‌شده. جزئیات: `docs/qa/QA_BASELINE.md`.

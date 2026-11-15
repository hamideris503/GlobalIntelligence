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

> **توجه:** شمارش جدول زیر فقط ۳۵ قلم اصلی ۲۸ اکتبر را می‌شمارد و به‌روز نشده است.
> دو قلم تازهٔ `GI-DISPATCH-001` و `GI-DISPATCH-002` در بخش «نقص‌های آزمون ۲۴/۷ — ۱۵ نوامبر ۲۰۲۶»
> در پایان همین سند ثبت شده‌اند؛ اقلام `GI-ALERT-001/002/003` و `GI-ARCH-001` در
> `docs/BUGS_AND_DEFECTS_REGISTER.md` نگه‌داری می‌شوند.

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
- **وضعیت بازبینی ۲۰۲۶-۱۱-۱۴:** **FIXED (کد از قبل درست بود، سند کهنه بود)** — `DispatchService.claimable()` در `backend/ai/dispatch/service.py:457-475` با `.with_for_update(skip_locked=True)` انتخاب می‌کند و تنها مصرف‌کننده‌اش `runner.run_once()` (`runner.py:665`) است. شاهد ماشینی: `tests/test_doc_claims.py::test_claimable_statement_uses_skip_locked` (SQL کامپایل‌شده برای دیالکت PG شامل `FOR UPDATE SKIP LOCKED`). `claim()` نیز یک UPDATE شرطی compare-and-swap است و روی PG فقط یک برنده دارد.

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

---

## وضعیت به‌روزشده — ۱۳ نوامبر ۲۰۲۶ (Stage 96 بسته شد)

**مبنا:** `step6a-analysis-dashboard` (`ebe1292`) + commitهای بعدی

| قلم | وضعیت قبلی | وضعیت فعلی | شاهد |
|---|---|---|---|
| Stage 96 — تثبیت PG + CI | در انتظار | **COMPLETE** | PostgreSQL 16 **1814 passed / 0 failed** (۹۲۳.۹۶s، HEAD `ebe1292`) |
| F-02 PG deadlock | PARTIAL | **FIXED** | `test_claim_is_atomic` روی PG ۰.۳۶s؛ ۱۸۱۴/۰ |
| F-03 CI کاهش‌یافته | PARTIAL | **FIXED** | CI job بک‌اند کل suite اجرا می‌کند |
| F-05 discover PG timeout | FIXED | **FIXED** | — |
| F-06 missing article FK | FIXED | **FIXED** | — |
| F-07 SQLite assert | FIXED | **FIXED** | — |
| F-08 آفلاین واقعی | FIXED | **FIXED** | — |
| F-09 cwd وابسته | FIXED | **FIXED** | — |
| F-10 temp isolation | FIXED | **FIXED** | — |
| F-11 `SKIP LOCKED` | VERIFIED | **CLOSED** | commit `0160bfe`؛ `with_for_update(skip_locked=True)` در `service.py:473` |
| F-14 race JobRun | CLOSED | **CLOSED** | — |
| F-15 AdaptiveRouter | CLOSED | **CLOSED** | — |
| F-16 ETag | CLOSED | **CLOSED** | — |
| F-27 IPv6 | CLOSED | **CLOSED** | — |
| Playwright E2E | Not run | **34 passed / 0 failed** | Chrome محلی `chrome-win64/`، backend موقت :18100، HEAD `ebe1292` + باگ UI |
| باگ بنر آفلاین (giApplyAuthGate) | bug — بنر آفلاین مخفی | **FIXED** | `backend/static/index.html` — وضعیت `down` دیگر auth gate را trigger نمی‌کند |
| F-20 topics/entities JSONB | باز | باز (نیاز به تصمیم schema) | — |
| F-23 rate limit multi-process | باز | باز (مستند) | `docs/F23_RATE_LIMIT.md` |
| F-13 شاخهٔ غیرقابل‌دستیافتنی | باز | باز (پیاده‌سازی نشده) | F-06 دستی حل شد |

**دادهٔ اندازه‌گیری‌شده:** PostgreSQL 16 **1814 passed / 0 failed** (۲۰۲۶-۱۱-۱۳، Python 3.14، ۹۲۳.۹۶s)؛ Playwright E2E **34 passed / 0 failed** (۱.۵ دقیقه)؛ SQLite **1813 passed / 1 skipped / 0 failed** (Python 3.14، ۴۴۲.۹۸s)

---

# بازبینی ادعاها — ۱۴ نوامبر ۲۰۲۶

**دلیل:** در جریان کار روی UI معلوم شد دو ادعای امنیتی این سند/`UI_MIGRATION_MANIFEST`
از grep ناقص آمده بودند (`GI-SEC-001`, `GI-SEC-002`) و یک قلم P1 (`F-11`) از قبل
حل شده بود. این بخش اقلام **P0/P1** را دوباره با کد سنجیده است. اقلام P2/P3
(۱۴ + ۸) در این بازبینی **بازآزمایی نشده‌اند** و وضعیت قبلی‌شان معتبر نیست.

| قلم | وضعیت واقعی | شاهد (دستور/کد) |
|---|---|---|
| F-01 تغییرهای commit‌نشده | **OPEN** (بدون تغییر) | `git status --porcelain` همچنان فایل tracked تغییریافته دارد |
| F-02 deadlock دیسپچ روی PG | **FIXED** | `tests/test_dispatch.py:132,177` دو session با commit واقعی + تست دو-`Barrier` |
| F-03 CI فقط زیرمجموعه | **FIXED** | `.github/workflows/ci.yml:54` → `pytest tests -q --basetemp=.pytest-ci` |
| F-04 شاهد CI راه‌دور | **NOT_VERIFIED** | نیازمند push مالک؛ بدون تغییر |
| F-05 تایم‌اوت Settings روی PG | **FIXED** | `tests/conftest.py:71` → `_pg_url.set(host="127.0.0.1")` |
| F-06 مقالهٔ گمشده روی PG | **FIXED** | `tests/test_domain_engines.py:76` → `_orphan()` ردیف در حافظه، بدون INSERT |
| F-07 assert صریح SQLite | **FIXED** | هیچ `assert 'sqlite' in` در `tests/` نمانده؛ نگهبان: `test_no_sqlite_only_assertions_remain` |
| F-08 «آفلاین» نبودن source_bot | **FIXED** | `tests/test_security.py:230` تست محافظ resolver آفلاین |
| F-09 تست وابسته به cwd | **FIXED** | `tests/test_deploy.py:41` → `Path(__file__).resolve().parents[1]` |
| F-10 temp مشترک/فِیل کاذب | **FIXED** | `tests/conftest.py:25-28` → ریشهٔ `gi-pytest-<pid>-*` اختصاصی هر اجرا |
| F-11 `claim` بدون SKIP LOCKED | **FIXED (کهنه بود)** | `service.py:473` + نگهبان `test_claimable_statement_uses_skip_locked` |
| F-12 migration روی SQLite | **OPEN (طراحی)** | `alembic` روی SQLite از ALTER constraint پشتیبانی نمی‌کند؛ لاین migration فقط PG |
| F-13 تشخیص کد مرده | **OPEN (ابزار)** | هنوز ابزار واحد نیست؛ پوشش شاخه‌های خطا موردی است |

**نگهبان ماشینی:** `tests/test_doc_claims.py` چهار واقعیت پرتکرار مستند را قفل می‌کند
(SKIP LOCKED، گیت admin برای `test-deliver`، IP literal در DSN لاین PG، ریشهٔ temp
اختصاصی) تا این اسناد بی‌صدا از کد جدا نشوند.

---

# نقص‌های آزمون ۲۴/۷ — ۱۵ نوامبر ۲۰۲۶

**مبنا:** سرویس نصب‌شدهٔ ویندوز روی `8010` (Task Scheduler + `scripts/run_backend_forever.cmd`)،
DB = `dev.db` (SQLite)، `MOCK_MODE=false`، HEAD `2d0e1bc` + working tree (هیچ commit نشده).
همهٔ اقلام زیر **اندازه‌گیری‌شده** هستند (اجرای واقعی، نه گزارش).

## GI-DISPATCH-001 · ردیف `running` پس از restart تا ۹۰۰ ثانیه قفل می‌ماند — **FIXED**

- **علامت:** پس از `kill -9` در میانهٔ dispatch، ردیف `event_extraction@v1` دقیقه‌ها در وضعیت
  `running` ماند، هیچ مصرف‌کننده‌ای آن را برنداشت و Job مربوطه پیش نمی‌رفت.
- **شاهد:**
  - `SELECT task_name,status,attempts FROM article_dispatches WHERE status='running'`
    → `('event_extraction@v1','running',1)` با `updated_at` چند ثانیه قبل از crash.
  - پس از restart، لاگ **هیچ** خط `dispatch recovery` نداشت (یعنی `recover_stale` ردیفی پیدا نکرد).
  - علت عددی: `backend/core/config.py` → `dispatch_lease_seconds: int = 900`؛
    `recover_at_startup` با lease پیش‌فرض اجرا می‌شد و ردیف تازه‌تر از ۹۰۰ ثانیه را «زنده» می‌پنداشت.
- **علت ریشه‌ای:** فرض «lease یعنی مالک زنده» در مسیر startup غلط است؛ پروسه‌ای که تازه بالا آمده
  هرگز lease پروسهٔ قبلی را در دست ندارد، پس هر ردیف `running` در آن لحظه رهاشده است.
- **اصلاح:**
  - `backend/ai/dispatch/runner.py` → `recover_at_startup`: `service.recover_stale(stale_seconds=0)`.
  - `backend/ai/dispatch/service.py` → `recover_stale`: `cutoff = utcnow() - timedelta(seconds=max(0, seconds))`
    (قبلاً `max(1, …)` بود و مقدار ۰ را بی‌اثر می‌کرد)؛ مقدار ۰ = «بدون پنجرهٔ مهلت».
- **اثبات:**
  - لاگ واقعی پس از restart: `dispatch stale running recovered | n=1` و
    `dispatch recovery | {'stale': 1, 'reenqueued': 0}`.
  - ردیف: `retryable`, `last_error="stale running recovered after restart"`, سپس
    `dispatch tick | {'claimed': 1, 'completed': 1, …}` و نهایتاً `completed` با `attempts=2`.
  - تست نگهبان: `tests/test_dispatch.py::test_startup_recovery_frees_rows_claimed_just_before_a_crash`.
  - سوئیت کامل پس از اصلاح: `pytest tests -q` → **1928 passed, 2 skipped, 0 failed** (446.20s, exit 0).
- **گزارش کامل:** `docs/execution_reports/PHASE_12_REPORT.md`

## GI-DISPATCH-002 · روی SQLite هر claim ردیف `retryable` استثنا می‌داد — **FIXED**

- **علامت:** حلقهٔ dispatch هر ۲۰ ثانیه `dispatch tick failed` می‌داد و **هیچ retry اجرا نمی‌شد**؛
  ردیف `retryable` برای همیشه در صف می‌ماند.
- **شاهد:** `logs/backend-8010.out.log` → ۱۱ بار
  `WARNING backend.ai.dispatch.runner | dispatch tick failed` با stack:
  `runner.py:666 service.claim(dispatch)` → `service.py:232 update(ArticleDispatch)` →
  `sqlalchemy/orm/evaluator.py:263` → `TypeError: can't compare offset-naive and offset-aware datetimes`.
- **علت ریشه‌ای:** SQLite datetime را naive برمی‌گرداند، در حالی که `utcnow()` aware است. هندل
  `UPDATE … WHERE next_retry_at <= :now` با `synchronize_session` پیش‌فرض SQLAlchemy سعی می‌کند
  شرط را در Python روی اشیای درون‌حافظه ارزیابی کند → مقایسهٔ naive/aware. ردیف‌های `pending`
  (که `next_retry_at` آن‌ها NULL است) به این مقایسه نمی‌رسیدند، پس فقط مسیر retry می‌شکست.
  روی PostgreSQL این رخ نمی‌دهد چون درایور datetime aware برمی‌گرداند — یعنی نقص **مخصوص SQLite**
  و در نتیجه در تست‌های PG دیده نمی‌شد.
- **اصلاح:** `backend/ai/dispatch/service.py` → `claim()` با
  `.execution_options(synchronize_session=False)`؛ مقایسه در خود DB انجام می‌شود و
  `refresh` بعدی مقدار واقعی را می‌خواند.
- **اثبات:**
  - `tests/test_dispatch.py::test_retryable_row_is_claimable_after_a_db_roundtrip` — با برداشتن
    موقت اصلاح **fail** می‌شود و با اصلاح pass (اعتبارسنجی خودِ تست انجام شد).
  - `pytest tests/test_dispatch.py tests/test_domain_routing.py tests/test_domain_engines.py -q`
    → **78 passed, 1 skipped** (۵.۶۲s)؛ `ruff check` روی فایل‌های تغییریافته پاک.
  - لاگ واقعی: `dispatch tick | {'claimed': 1, 'completed': 1, …}` بدون خطای بعدی.
  - سوئیت کامل پس از اصلاح: `pytest tests -q` → **1928 passed, 2 skipped, 0 failed** (446.20s, exit 0).
- **گزارش کامل:** `docs/execution_reports/PHASE_12_REPORT.md`

## جمع‌بندی وضعیت این دو قلم

| قلم | شدت | وضعیت | ابزار بستن |
|---|---|---|---|
| GI-DISPATCH-001 | P1 (از دست رفتن کار تا ۱۵ دقیقه) | **FIXED** | `recover_at_startup` + `recover_stale(0)` + ۱ تست |
| GI-DISPATCH-002 | P1 (retry بی‌اثر روی SQLite) | **FIXED** | `claim()` با `synchronize_session=False` + ۱ تست |

## سوئیت کامل پس از این دو اصلاح — **اندازه‌گیری‌شده**

```
cd J:\Documents\GlobalIntelligence
python -m pytest tests -q
→ 1928 passed, 2 skipped, 746 warnings in 446.20s (0:07:26)   exit=0
```

- اجرا روی SQLite (Python 3.14)، working tree شامل هر دو اصلاح dispatch، `0 failed`.
- مبنای مقایسه: آخرین اجرای کامل پیش از این فاز **۱۹۱۲ passed / ۲ skipped** بود؛
  افزایش ۱۶ تست از تست‌های افزوده‌شدهٔ همین دورهٔ کاری است (از جمله دو تست رگرسیون این دو قلم).
- خروجی خام: `.tmp-audit-2026/fullsuite.log` (gitignored).
### لاین PostgreSQL — همان سوئیت، همان working tree

محیط: PostgreSQL **16.16** (alpine) در یک کانتینر ایزولهٔ موقت (`gi_pg_lane_tmp`) روی `127.0.0.1:15434`،
دیتابیس تازهٔ `gi_pg_lane_phase13`، `alembic upgrade head` روی همان DB (rc=0)، سپس:

```
DATABASE_URL=postgresql+psycopg://…@127.0.0.1:15434/gi_pg_lane_phase13
python -m pytest tests -q
→ 1929 passed, 1 skipped, 746 warnings in 1044.22s (0:17:24)   exit=0
```

بعد از اجرا، DB و کانتینر موقت حذف شدند؛ به کانتینرهای `gi_postgres` / `gi_staging_postgres` کاربر
دست نزده شد. خروجی خام: `.tmp-audit-2026/pgsuite.log`.

### مقایسهٔ دو لاین

| لاین | نتیجه | زمان | تفاوت |
|---|---|---|---|
| SQLite | 1928 passed / 2 skipped / 0 failed | 446.20s | سریع‌تر؛ ۱ تست فقط-PG (هم‌زمانی `claim`) اینجا skip می‌شود |
| PostgreSQL 16.16 | 1929 passed / 1 skipped / 0 failed | 1044.22s | تست هم‌زمانی دوسطریِ `claim` فقط اینجا اجرا می‌شود؛ ۱ تست دیگر اینجا skip است |

- مجموع موارد هر دو لاین **۱۹۳۰** است و **هیچ شکستی در هیچ لاینی نیست**.
- اختلاف skip دو لاین یک تست است: تست هم‌زمانی `claim` روی SQLite رد و روی PG اجرا می‌شود
  (نام تست‌های skip در این اجراها ثبت نشده؛ فقط شمارش‌ها اندازه‌گیری شده‌اند).
- دو نقص این بخش (GI-DISPATCH-001/002) روی هر دو لاین پاس‌اند: اصلاح ۰۰۱ مستقل از DB است و
  اصلاح ۰۰۲ (که مخصوص SQLite بود) هیچ رفتاری روی PG را تغییر نمی‌دهد، چون مقایسه در هر دو حالت
  به خود دیتابیس سپرده می‌شود.

**نکتهٔ محیطی (نقص محصول نیست) — تشخیص کامل:** فوروارد پورتِ Docker Desktop برای چند کانتینر
**کهنه** شده است. شاهد اندازه‌گیری‌شده (Docker Engine 29.8.2، همهٔ کانتینرها Up 31h):

| پورت میزبان | کانتینر | از میزبان | از داخل کانتینر |
|---|---|---|---|
| `5678` | `gi_n8n` | ✅ `HTTP/1.1 200 OK` | ✅ سالم |
| `8000` | `gi_backend` | ❌ پذیرش و بستن فوری (`b''`) | ✅ `/health`=200 |
| `15432` | `gi_postgres` | ❌ `b''` | ✅ `pg_isready` سالم |
| `15433` | `gi_staging_postgres` | ❌ `b''` | ✅ سالم |
| `5173` / `8001` | `gi_frontend` / `gi_staging_backend` | ❌ `b''` | — |

- شنوندهٔ هر پورت `com.docker.backend.exe` است (مدل مستند Docker Desktop: شنونده روی میزبان،
  فوروارد از طریق کانال حافظهٔ مشترک به VM). TCP پذیرفته می‌شود ولی هیچ بایتی به کانتینر نمی‌رسد؛
  تأیید قاطع: پس از دو تلاش اتصال، **هیچ خطی** در `docker logs gi_postgres` ثبت نشد (فقط checkpoint)
  و `pg_isready` داخل کانتینر سالم است. پس مسئلهٔ PG، اعتبارنامه، `pg_hba` یا SSL نیست؛ خودِ
  فوروارد کهنه است.
- هر چهار پورت (`8000`, `5173`, `8001`, `5678`) شنوندهٔ یکسانی دارند: **همان**
  `com.docker.backend.exe` با PID 14676؛ پس خودِ فورواردر زنده است و فقط رکورد فورواردِ
  کانتینرهای یادشده مرده. تاریخ ساخت کانتینرها این را توضیح نمی‌دهد: `gi_staging_backend`
  (۲۰۲۶-۱۰-۱۲) از `gi_n8n` (۲۰۲۶-۱۰-۱۶) قدیمی‌تر است ولی پورتش مرده و پورت n8n سالم؛ همچنین
  هر سه اپ داخل کانتینر پاسخ ۲۰۰ می‌دهند (`gi_backend` `/health`، `gi_frontend` `5173`،
  `gi_staging_backend` `/health`). یعنی وضعیت، **per-container** است، نه نسخه یا سن کانتینر.
- شاهد مکانیزم رفع: پس از `docker restart gi_postgres gi_staging_postgres`، دقیقاً همان دو پورت
  سالم شدند و سه کانتینر restart‌نشده مرده ماندند — یعنی رکورد فوروارد در (re)start کانتینر
  بازساخته می‌شود، نه با گذشت زمان یا با خودِ فرآیند فورواردر.
- این کلاس باگ در یادداشت‌های انتشار Docker Desktop ثبت شده است («published ports staying
  unreachable for the life of the container…»). فورواردِ کهنه با restart همان کانتینر یا با
  Restart کردن Docker Desktop بازساخته می‌شود؛ افزودن/تازه‌سازی پورت منتشرشده روی کانتینرِ
  در حال اجرا پشتیبانی نمی‌شود.
- **راه‌حلِ بدون دست‌زدن به داده:** داده در named volume‌های `globalintelligence_pg_data` و
  `gi_staging_pg_data` است، نه در لایهٔ کانتینر؛ پس `docker compose restart postgres` (یا Restart از
  Tray → Troubleshoot برای بازسازی همهٔ فورواردها) هیچ داده‌ای را تغییر نمی‌دهد و فقط چند ثانیه
  قطعی دارد. صحت‌سنجی پس از آن: تست خام سوکت باید به‌جای `b''` پاسخ PG بدهد.
- **اجرا شد و رفع شد (۱۵ نوامبر ۲۰۲۶، با تأیید مالک):** `docker restart gi_postgres gi_staging_postgres`
  در ۲.۷۶s تمام شد؛ هر دو کانتینر `healthy` و نتیجهٔ سنجش:

  | بررسی | قبل | بعد |
  |---|---|---|
  | SSLRequest میزبان → `15432` / `15433` | `b''` | `b'N'` (پاسخ واقعی PG) |
  | اتصال با اعتبارنامهٔ `.env` به DB `globalintelligence` | ❌ | ✅ `current_user=gi_user` |
  | جدول‌ها / head مهاجرت | — | ۵۴ جدول / `a9f1c2d3e4b5` |
  | `job_runs` (شاهدِ نماندن داده) | 533 | **533** (بدون تغییر) |
  | `/health` و `/health/db` از داخل `gi_backend` | 200 / ok | 200 / `{"status":"ok"}` |

  یعنی هیچ داده‌ای جابه‌جا نشد و اپلیکیشن بدون مداخله دوباره به DB وصل شد.
- **`8000` و `5173` هم رفع شدند (همان روز، با تأیید مالک):** `docker restart gi_backend gi_frontend`
  در ۴.۳۰s تمام شد و نتیجه:

  | بررسی | قبل | بعد |
  |---|---|---|
  | میزبان → `8000` | `b''` | `HTTP/1.1 200 OK` |
  | `curl /health` و `/health/db` روی `8000` | — | **۲۰۰ / ۲۰۰** |
  | میزبان → `5173` (curl با Host درست) | `b''` | **۲۰۰** (با سوکت بدون هدر Host، Vite طبق قاعدهٔ خودش ۴۰۳ می‌دهد) |

  نکتهٔ عملیاتی: `docker compose restart frontend` کار نمی‌کند (`no such service: frontend`) چون سرویس
  `frontend` در `docker compose config --services` نیست (profile-gated است)؛ باید با نام کانتینر یا
  `docker restart gi_frontend` عمل کرد.
- **`8001` هم رفع شد (همان روز، با تأیید مالک):** `docker restart gi_backend gi_frontend gi_staging_backend`
  در ۷.۶۳s تمام شد و هر سه کانتینر `healthy`/`Up` شدند:

  | بررسی | قبل | بعد |
  |---|---|---|
  | میزبان → `8000` (`/health`, `/health/db`) | `b''` | **۲۰۰ / ۲۰۰** |
  | میزبان → `5173` (curl با Host) | `b''` | **۲۰۰** |
  | میزبان → `8001` (`/health`) | `b''` | **۲۰۰** |

  **نتیجه:** هر سه پورت ۸۰۰۰/۵۱۷۳/۸۰۰۱ اکنون از میزبان پاسخ می‌دهند. هیچ پورت مردهٔ دیگری
  باقی نمانده است. (سوکت خام بدون هدر Host روی ۵۱۷۳ همچنان ۴۰۳ می‌دهد که رفتار معمول Vite است.)
- پیش از رفع، لاین PG روی یک PG 16.16 ایزولهٔ موقت (`gi_pg_lane_tmp`، پورت ۱۵۴۳۴، بعداً حذف‌شده)
  اجرا شده بود؛ نتیجهٔ سوئیت روی آن معتبر است.

- **باقی‌مانده:** CI راه‌دور هنوز تأیید نشده (`F-04`).

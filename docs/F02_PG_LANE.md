# F02 — لاین PostgreSQL، deadlock دیسپچ و ۱۰ شکست تاریخی

**وضعیت:** VERIFIED · **تاریخ:** 2026-10-29 · **شاخه:** `stage95-pg-ci-verification` + working tree (بدون commit جدید)

## English summary

The PostgreSQL lane now runs end-to-end on an isolated database: `gi_f02_pg` was recreated from
scratch and migrated to head `88a9b2c1d4e5`. The claim deadlock (F-02/F-11) was a test bug — two
sessions held row locks in the same transaction — so the test was rebuilt around committed
transactions plus a two-thread race test. The four `ConnectionTimeout` failures (F-05) came from a
hostname DSN combined with a global `getaddrinfo` patch; the test engine now connects to a literal
IP. The four `ForeignKeyViolation` failures (F-06) are settled by testing the handler contract
directly, because a dispatch row without an article cannot exist under the PG foreign key. The two
hard-coded `sqlite` assertions (F-07) now assert identity with the test bind. The offline promise
(F-08) is real: `source_bot.security` resolves through the module attribute, and reserved test TLDs
never reach the resolver, so no test pays a ~12s DNS stall. Evidence: **PG 1483 passed / 0 failed
(914s)**, **SQLite 1482 passed / 1 PG-only skip (443s)**, `test_claim_is_atomic` **0.36s**,
`ruff` clean. CI now runs the full suite instead of a 4-file subset; the remote CI run itself is
still unverified (local interpreter is Python 3.14.4 / pytest 9.1.1, CI pins 3.12 / pytest<9).

## ۱) محیط و روش

| مورد | مقدار |
|---|---|
| پایگاه داده | `gi_f02_pg` روی کانتینر `gi_postgres` (PostgreSQL 16.15، image alpine) |
| ساخت DB | `DROP DATABASE IF EXISTS` + `CREATE DATABASE` — از صفر، هر بار تکرارپذیر |
| Migration | `alembic upgrade head` → `88a9b2c1d4e5 (head)`؛ بدون تغییر schema در این مرحله |
| اتصال | `postgresql+psycopg://…@127.0.0.1:15432/gi_f02_pg` (IP literal، نه `localhost`) |
| DB زندهٔ dev | `globalintelligence` — **هدف هیچ اجرا نبود**؛ همهٔ اجراها DSN ایزوله داشتند و هیچ تستی از `settings.database_url` استفاده نمی‌کند (فقط `create_engine` صریح یا SQLite موقت) |
| مفسر | Python 3.14.4 / pytest 9.1.1 (محلی) — CI روی 3.12 / pytest<9 |

هیچ dependency، هیچ بررسی تمامیتی و هیچ سیاست production‌ای در این مرحله تغییر نکرد؛ همهٔ
تغییرها در `tests/` و یک import ماژولی در `source_bot/security.py` هستند.

## ۲) F-02 / F-11 — deadlock تست claim

**علامت:** `tests/test_dispatch.py::test_claim_is_atomic` روی PG هرگز تمام نمی‌شد (روی SQLite پاس).

**علت ریشه‌ای:** تست دو `Session` را هم‌زمان باز می‌کرد و `claim` اول ردیف را با `UPDATE` قفل
می‌کرد تا `commit` انتهای تست؛ `claim` دوم روی همان ردیف در `wait_event=transactionid` می‌ماند.
یعنی deadlock در **تست** بود، نه در `DispatchService.claim` (که همان `UPDATE … WHERE id=… AND
status IN (…)` باقی مانده است).

**اصلاح:**
- `test_claim_is_atomic` بازنویسی شد: هر session یک تراکنش واقعی با `commit` دارد؛ claim اول
  `True`، claim دوم روی حالت committed `running` مقدار `False` می‌گیرد و `attempts` دقیقاً ۱
  می‌ماند. هیچ قفل متقاطعی باقی نمی‌ماند.
- تست جدید `test_claim_is_atomic_under_concurrency` (فقط PG؛ روی SQLite skip): دو thread پشت
  `threading.Barrier` هم‌زمان claim می‌کنند؛ نتیجه باید دقیقاً `[False, True]` باشد، هیچ thread
  بعد از ۳۰ ثانیه زنده نماند و `attempts == 1` بماند. این همان شاهد F-11 است.

**شاهد:** `test_claim_is_atomic` روی PG در **0.36s** (قبلاً timeout در ۱۰۰s)، تست هم‌زمانی 0.16s.

## ۳) F-05 — چهار تست Settings با `ConnectionTimeout`

**علت:** `_mock_public_dns()` به‌صورت سراسری `socket.getaddrinfo` را patch می‌کند؛ با DSN شامل
`localhost` و `NullPool` (هر درخواست = اتصال جدید) اتصال DB هم به IP جعلی هدایت و تا ۱۰s
تایم‌اوت می‌شد.

**اصلاح:** `tests/conftest.py` در حالت PG، هاست DSN را با `make_url().set(host="127.0.0.1")` به
IP literal تبدیل می‌کند؛ آدرس عددی هیچ‌وقت DNS صدا نمی‌زند. DSN خود CI بدون تغییر می‌ماند و همین
تبدیل روی آن هم اعمال می‌شود.

**شاهد:** `pytest tests/test_settings.py -q` روی PG → **53 passed** (شامل هر پنج تست `discover`).

## ۴) F-06 — چهار تست «مقالهٔ گمشده» با `ForeignKeyViolation`

**تصمیم صریح:** حالت «dispatch بدون مقاله» در PG قابل ساخت نیست، پس تستِ نوشتن چنین ردیفی
واقعیتی را نمی‌سنجد که در production ممکن است. پوشش به سطح **قرارداد handler** منتقل شد:
یک ردیف `ArticleDispatch` ساخته‌شده در حافظه (بدون insert) به handler داده می‌شود و نتیجه باید
`status == "terminal"` با `detail` شامل `article not found` باشد.

**فایل‌ها:** `tests/test_domain_engines.py` (geopolitics, society)،
`tests/test_domain_routing.py` (routing, claim_independence)، و شاخهٔ مشابه در
`tests/test_dispatch.py` (event_extraction). `_orphan()` دیگر چیزی در DB نمی‌نویسد.

**شاهد:** هر چهار تست روی PG پاس؛ هیچ insert نقض‌کنندهٔ FK باقی نمانده است.

## ۵) F-07 — دو assert سختِ SQLite

| فایل | قبل | بعد |
|---|---|---|
| `tests/test_fullstack_integration.py` | `assert "sqlite" in str(session.get_bind().url)` | `assert session.get_bind() is TestingSession.kw["bind"]` |
| `tests/test_source_bot_validation.py` | `assert seen["driver"] == "sqlite"` | `assert seen["driver"] == TestingSession.kw["bind"].url.drivername` |

هر دو اکنون «همان bind تست» را می‌سنجند، پس روی هر دو لاین معنا دارند.

همچنین `tests/test_news_identity_phase7.py::test_partial_unique_index_is_declared_and_enforced`
بازرسی متن DDL ایندکس را فقط روی SQLite انجام می‌دهد (روی PG متن ایندکس از `pg_indexes` خوانده
نمی‌شود)، اما اعمال واقعی قید در هر دو لاین سنجیده می‌شود.

## ۶) F-08 — «آفلاین» واقعی

**علت:** `source_bot/security.py` تابع `resolve_host_ips` را با import مقداری گرفته بود، پس patch
`conftest` روی آن اثر نداشت. علاوه بر آن، `host_is_private()` و هر مسیر دیگری که مستقیم
`socket.getaddrinfo` می‌زند، برای نام‌های `.test` واقعاً به resolver می‌رفت و روی این ماشین هر
جست‌وجوی ناموجود ~۱۲ ثانیه طول می‌کشید.

**اصلاح:**
1. `source_bot/security.py` اکنون `from domains.news import source_verify` و
   `source_verify.resolve_host_ips(...)` را در زمان فراخوانی صدا می‌زند → patch مؤثر است.
2. `_offline_resolver` در `conftest.py` علاوه بر patch تابع، `socket.getaddrinfo` را برای TLDهای
   رزروشدهٔ RFC 6761 (`.test`، `.invalid`، `.example`، `.localhost`) با `gaierror` فوری می‌بندد؛
   هیچ تستی منتظر resolver نمی‌ماند و سیاست production دست‌نخورده است.
3. تست محافظ `tests/test_security.py::test_source_bot_security_uses_the_offline_resolver_patch`:
   patch روی ماژول `source_verify` باید توسط `connection_check` دیده شود (پاسخ خالی → رد
   fail-closed با `dns_unresolved`)، نه یک resolve تازه.

**شاهد:** اجرای دو فایل `phase5`+`phase6`+`security` از «>۳۰۰ ثانیه بدون خروج» به **66 passed در
91s** رسید؛ کل suite روی SQLite از ~۱۵:۱۲ به **7:22** کاهش یافت.

## ۷) شاهد نهایی

| بررسی | نتیجه |
|---|---|
| `pytest tests -q` روی **PostgreSQL** (DB ایزوله) | **1483 passed, 0 failed** در 914.55s |
| `pytest tests -q` روی **SQLite** | **1482 passed, 1 skipped** در 442.62s (skip = تست هم‌زمانی مخصوص PG) |
| `test_claim_is_atomic` روی PG | **0.36s** (معیار نقشه: زیر ۵ ثانیه) |
| `ruff check backend domains tests scripts source_bot` | **All checks passed** |
| DB زندهٔ dev | هدف هیچ اجرا نبود؛ `article_dispatches` = ۶۲۹ ردیف (بدون ادعای «بدون تغییر» — قبل از شروع اندازه‌گیری نشد) |

## ۸) CI (۹۶-۵)

`.github/workflows/ci.yml` مرحلهٔ «زیرمجموعهٔ ۴ فایلی» را با اجرای کل suite جایگزین کرد:

```yaml
      - name: Full test suite (PostgreSQL)
        timeout-minutes: 30
        run: |
          pytest tests -q --basetemp=.pytest-ci
```

`timeout-minutes` جاب از ۳۰ به ۴۰ رفت، چون suite کامل روی این ماشین ۱۵:۱۴ طول می‌کشد (Linux/CI
معمولاً سریع‌تر است، اما اندازه‌گیری نشده).

**محدودیت صادقانه:** این تغییر فقط محلی اعتبارسنجی شده است. اجرای واقعی CI (Python 3.12،
pytest<9، `postgres:16` سرویس) در این مرحله **انجام نشد**؛ تا آن زمان «سبز بودن CI» ادعای
تأییدشده نیست. همچنین `alembic downgrade base` که CI اجرا می‌کند در این لاین محلی تکرار نشد.

## ۹) آنچه در F02 بسته نشد

- **F-09** (تست وابسته به cwd) و **F-10** (وابستگی به `pytest-current` ویندوز): خارج از دامنه؛
  این اجراها با `--basetemp` صریح انجام شد.
- **F-12** (زنجیرهٔ migration روی SQLite اجرا نمی‌شود): همچنان فقط مستند است.
- **F-13** (ابزار تشخیص شاخهٔ دست‌نیافتنی): نشستی ندارد؛ F-06 دستی حل شد.
- **F-01** (تعیین‌تکلیف ۲۵ فایل commit‌نشده): بدون تغییر؛ هیچ فایلی stash/commit نشد.
- یادآوری F01: هر restart سرویس، ردیف‌های terminal صف `screening@v1` را دوباره وارد چرخه
  می‌کند؛ تصمیم آن به `F09`/`F10` نقشه موکول است و در این مرحله دست نخورد.

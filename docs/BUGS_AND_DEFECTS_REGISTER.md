# ثبت باگ‌ها و نقص‌های GlobalIntelligence

**تاریخ:** ۱۵ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc` + working tree dirty
**قاعده:** هر قلم با شاهد قابل بازتولید. اقلام بدون اجرا با `CODE-INSPECTED` مشخص شده‌اند.

## خلاصهٔ شمارش

| سطح | تعداد |
|---|---|
| P0 | 1 |
| P1 | 5 |
| P2 | 6 |
| P3 | 5 |

---

# P0 — مسدودکننده

## GI-DB-001 · نوشتن در دیتابیس SQLite مهاجرت‌شده شکست می‌خورد (`DEFAULT (now())`)

- **شدت:** P0 (قابلیت اصلی: افزودن منبع/رکورد در مسیر محلی مستندشده)
- **محل:** `backend/database/base.py:29-40` (`TimestampMixin` با `server_default=func.now()`) + DDL تولیدشدهٔ Alembic روی SQLite
- **شاهد (MEASURED):**
  ```
  POST /api/sources -> HTTP 503 {"detail":"database unavailable","code":"DB_UNAVAILABLE"}
  sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unknown function: now()
  [SQL: INSERT INTO sources (...) RETURNING created_at, updated_at]
  ```
  DDL در `dev.db` (ساخته‌شده با Alembic):
  `created_at DATETIME DEFAULT (now()) NOT NULL`
  DDL در تست‌ها (ساخته‌شده با `Base.metadata.create_all`):
  `created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL`
- **دلیل وقوع:** SQLite تابع `now()` ندارد. Alembic روی SQLite همان `now()` را رندر می‌کند، در حالی که dialect SQLite در `create_all` آن را به `CURRENT_TIMESTAMP` تبدیل می‌کند. پس تست‌ها این مسیر را نمی‌بینند.
- **بازتولید:**
  ```bash
  cp dev.db /tmp/a.db   # یا: alembic upgrade head روی فایل خالی SQLite
  DATABASE_URL=sqlite:////tmp/a.db uvicorn backend.main:app --port 18102
  # login → POST /api/sources → 503
  ```
- **تأثیر:** `.env` پیش‌فرض (`sqlite:///./dev.db`) و مسیر «بدون Docker» در README عملاً **نمی‌توانند منبع بسازند** → ingestion واقعی از UI ممکن نیست. این توضیح می‌دهد چرا `dev.db` صفر منبع/سند/مقاله دارد.
- **راهکار پیشنهادی:** یا (الف) `TimestampMixin` به `default=datetime.now(UTC)` سمت Python + `server_default=func.now()` فقط برای PG، یا (ب) helper سازگار: در `db/migrations/env.py`/migrationها برای SQLite `CURRENT_TIMESTAMP` رندر شود، یا (ج) SQLite رسماً «فقط تست» اعلام و `DATABASE_URL` پیش‌فرض به PG تغییر کند و مسیر SQLite از README حذف شود.
- **پیش‌نیاز:** تصمیم مالک که SQLite محیط رسمی local است یا نه.
- **تست لازم:** تست migration-محور: `alembic upgrade head` روی SQLite خالی → سپس `POST /api/sources` → 201 و یک ردیف در DB.

---

# P1 — بالا

## GI-AI-001 · خطای واقعی Provider با `model_not_allowed` پوشانده می‌شود (رگرسیون)

- **شدت:** P1 (7 تست سرخ + رفتار نادرست API در production path)
- **محل:** `backend/ai/gateway/gateway.py` حلقهٔ `generate()`؛ `backend/ai/free_policy.py:160` (`check_model`)
- **شاهد (MEASURED):** اجرای `pytest tests/test_fullstack_integration.py`:
  ```
  provider groq failed (AIErrorKind.rate_limit): rate limited
  ai error | kind=AIErrorKind.model_not_allowed provider=openrouter status=403
  assert 403 == 429   (و 502/503/504 برای تست‌های دیگر)
  ```
- **دلیل وقوع:** پس از شکست Provider اول، زنجیره به `AI_DEFAULT_PROVIDER=openrouter` می‌رود؛ مدل پیش‌فرض آن در آن سناریو در allowlist نیست و `check_model` **بیرون از try/except حلقه** خطا می‌دهد. نتیجه: نوع خطای اصلی (quota/timeout/connection/rate_limit) از بین می‌رود و همه‌چیز 403 می‌شود.
- **بازتولید:** `pytest tests/test_fullstack_integration.py -q` (7 failure).
- **تأثیر:** کلاینت/UI نمی‌تواند «بعداً تلاش کن» (429 + Retry-After) را از «پیکربندی اشتباه» (403) تفکیک کند؛ retry/backoff اشتباه؛ تست‌های قرارداد HTTP سرخ.
- **راهکار:** `check_model` برای هر نامزد داخل همان try باشد و خطای سیاست به‌عنوان `provider_skipped` ثبت شود، نه خطای نهایی زنجیره؛ یا نامزدهای غیرمجاز **قبل از ورود به حلقه** از chain حذف شوند تا `_chain_failure` خطای واقعی را انتخاب کند.
- **تست لازم:** همان 7 تست + تست واحد: «provider اول timeout، provider دوم مدل غیرمجاز → پاسخ باید 504 باشد نه 403».

## GI-OPS-001 · `/api/ingest/all` منابع تازه‌ساخته را بی‌صدا نادیده می‌گیرد

- **شدت:** P1 (قابلیت اصلی ingestion از UI)
- **محل:** `backend/api/routers/ingestion.py:108-130` — فیلتر `Source.collection_method == "rss"`
- **شاهد (MEASURED):** منبع با `feed_url` ساخته شد، سپس:
  ```
  POST /api/ingest/all?limit=5 -> []   (دو بار، بدون خطا و بدون توضیح)
  ```
  پس از `update sources set collection_method='rss'`:
  ```
  POST /api/ingest/all -> [{"fetched":5,"stored":5,"duplicates":0,"errors":[]}]
  ```
- **دلیل وقوع:** `create_source` هیچ‌گاه `collection_method` را از وجود `feed_url` استنتاج نمی‌کند؛ فیلتر هم به‌جای «feed_url موجود» به `collection_method` تکیه می‌کند.
- **تأثیر:** کاربر منبع معتبر می‌سازد، «Ingest all» می‌زند، هیچ اتفاقی نمی‌افتد و هیچ خطایی هم نمی‌بیند.
- **راهکار:** یا در `SourceRegistry.create` مقدار پیش‌فرض `rss` وقتی `feed_url` داده شده، یا فیلتر به `feed_url IS NOT NULL` تغییر کند و `collection_method` فقط override باشد؛ به‌علاوهٔ شمارش «چند منبع رد شد و چرا» در پاسخ.
- **تست لازم:** ساخت منبع فقط با `feed_url` → `ingest/all` باید ≥1 نتیجه بدهد.

## GI-TEST-001 · مجموعهٔ تست پروژه در وضعیت فعلی سرخ است

- **شدت:** P1 (ادعای «تکمیل» را باطل می‌کند)
- **شاهد (MEASURED):** `9 failed, 1900 passed, 1 skipped in 566.86s`
- **اجزا:** GI-AI-001 (7)، GI-TEST-002، GI-DOC-001.
- **تأثیر:** هیچ اعلام «VERIFIED_COMPLETE» با suite سرخ پذیرفتنی نیست؛ CI روی همین SHA هم قطعاً سرخ می‌شود (اگر اجرا شود).
- **راهکار:** رفع سه علت بالا، سپس اجرای مجدد کامل روی SQLite و PG.

## GI-TEST-002 · تست pool فقط روی PostgreSQL معنا دارد ولی روی lane اSQLite اجرا می‌شود

- **شدت:** P1 (شکست دائمی lane پیش‌فرض)
- **محل:** `tests/test_health.py:48`
- **شاهد (MEASURED):**
  ```
  assert None == 10   # captured engine kwargs = {'future': True}
  ```
- **دلیل:** در DSN SQLite، `pool_size` به engine پاس نمی‌شود؛ تست مقدار PG را انتظار دارد و `skipif` ندارد.
- **راهکار:** `@pytest.mark.skipif(sqlite)` یا assert روی dialect؛ همان الگویی که برای تست‌های `pg` استفاده شده.

## GI-OPS-002 · WP-16 (اجرای پایدار ۲۴/۷ روی Windows) پیاده‌سازی نشده

- **شدت:** P1 برای هدف «محصول محلی ۲۴/۷»
- **شاهد (CODE-INSPECTED + سند خود پروژه):** `docs/WP16_WINDOWS_24_7_RUNTIME.md` صریحاً `NOT_VERIFIED/DEFERRED` است؛ هیچ فایل Task Scheduler/service/runbook اجرایی در `scripts/` نیست؛ تنها lock موجود `source_bot.lock` در temp است.
- **تأثیر:** هیچ مسیر رسمی برای «روشن ماندن» سرویس، restart پس از crash، rotation لاگ و پایش دیسک در Windows وجود ندارد.
- **راهکار:** اسکریپت `scripts/install_windows_service.ps1` (NSSM یا Task Scheduler at-startup) + runbook + تست restart وسط job.

---

# P2 — متوسط

## GI-DB-002 · `/health/db` روی SQLite همیشه `degraded` است

- **محل:** `backend/database/session.py:59-82` → `SELECT version()`
- **شاهد (MEASURED):**
  ```
  GET /health/db -> {"status":"degraded"}
  GET /health/db/details -> "OperationalError: no such function: version [SQL: SELECT version()]"
  ```
  در حالی که `/api/ops/status` همان لحظه `database_ok=true` می‌دهد.
- **تأثیر:** readiness probe نادرست؛ مانیتورینگ/داکر/اپراتور فکر می‌کند DB قطع است.
- **راهکار:** بر اساس dialect شاخه بزن (`SELECT sqlite_version()` برای SQLite) یا به `SELECT 1` + خواندن `alembic_version` بسنده کن.

## GI-OPS-003 · اسکریپت backup فقط با `docker exec pg_dump` کار می‌کند

- **محل:** `scripts/db_backup.py:88-130`
- **شاهد (CODE-INSPECTED):** `_container()` و `docker exec ... pg_dump`.
- **تأثیر:** روی نصب محلی Windows با SQLite (یا Docker خاموش) هیچ backup رسمی وجود ندارد؛ در حالی که پروژه ادعای backup/restore دارد.
- **راهکار:** مسیر `sqlite3 .backup` یا `VACUUM INTO` برای SQLite + همان manifest/rotation.

## GI-REPO-001 · 60 تغییر uncommitted شامل کد و migration

- **شاهد (MEASURED):** `git status --porcelain` = 60 ورودی؛ شامل `backend/ai/gateway/gateway.py`، `backend/api/routers/auth.py`، `settings.py`، `backend/static/index.html`، migration جدید `a9f1c2d3e4b5`.
- **تأثیر:** هر `reset/checkout` کار را نابود می‌کند؛ بازبینی PR این تغییرات را نمی‌بیند؛ وضعیت «رسمی» مخزن با دیسک یکی نیست.

## GI-DOC-001 · `docs/ROLE_MATRIX.md` با کد همگام نیست

- **شاهد (MEASURED):** `test_permission_matrix_doc.py` سرخ:
  ```
  این endpointها در docs/ROLE_MATRIX.md نیستند: POST /api/settings/providers/{provider_id}/auto-detect-model -> admin
  ```
- **تأثیر:** سند نقش‌ها مرجع قابل اتکا نیست؛ تست قرارداد سرخ است.

## GI-DOC-002 · ادعاهای عددی مستندات با اندازه‌گیری امروز نمی‌خواند

- **شاهد (MEASURED):** `docs/WP18_LOCAL_PRODUCT_ACCEPTANCE.md` می‌گوید «1908 passed, 1 skipped» روی همین HEAD؛ اندازه‌گیری امروز: **1900 passed / 9 failed / 1 skipped**.
- **تأثیر:** تصمیم‌گیری بر پایهٔ گزارش‌های کهنه؛ دقیقاً همان چیزی که نقشه‌راه v2.2 منع کرده است.

## GI-TEST-003 · پوشش E2E و frontend در CI وجود ندارد

- **شاهد (MEASURED):** `.github/workflows/ci.yml` فقط 3 job دارد؛ `package.json` هیچ script ندارد؛ 7 spec در `tests/e2e/` هست ولی اجرا نمی‌شود.
- **تأثیر:** رگرسیون‌های UI (مثل همین GI-OPS-001 که در UI دیده می‌شود) بدون شکار می‌مانند.

---

# P3 — کم

## GI-OPS-004 · مسیر `/tmp` هاردکد در source_bot روی Windows

- **محل:** `source_bot/runner.py:124` → `os.path.exists("/tmp/source_bot.stop")`
- **تأثیر:** روی Windows این شرط عملاً همیشه false است؛ فقط `STOP_PATH` در temp کار می‌کند. کد مرده/گیج‌کننده، بدون شکست واقعی.

## GI-REPO-002 · پوشهٔ قفل‌شدهٔ `apps/web_leftover_locked`

- **شاهد (MEASURED):** `ls apps` فقط `.tmp-fe-dev.log` و دایرکتوری `web_leftover_locked` را نشان می‌دهد؛ خواندن `apps/web_leftover_locked/.pytest_cache` با Permission denied شکست می‌خورد.
- **تأثیر:** ابزارهای `find`/`grep`/backup با خطای دسترسی مواجه می‌شوند؛ README می‌گوید `apps/web` وجود ندارد ولی یک بازماندهٔ قفل‌شده هست.

## GI-UI-001 · کد مرده و دادهٔ نمونه در UI

- **شاهد (MEASURED):** `metrics()` تعریف شده ولی **0 بار** فراخوانی می‌شود؛ `chartPanel()` با آرایهٔ ثابت `[34,38,35,...]` و tooltip «سری زمانی نمونه» باقی مانده؛ 36 بار واژهٔ «نمونه» در فایل.
- **تأثیر:** ریسک نمایش عدد ساختگی اگر دوباره وصل شود؛ حجم فایل و ابهام برای نگهداری.

## GI-DOC-003 · ناسازگاری مستندات اجرا (frontend/compose/MOCK_MODE)

- **شاهد (MEASURED):** `docker-compose.yml` هدرش از سرویس `frontend` و پورت 5173 حرف می‌زند ولی چنین سرویسی تعریف نشده؛ `.env` روی `MOCK_MODE=false` است در حالی که README «پیش‌فرض true» می‌گوید؛ `AGENTS.md` هم همین ادعاها را تکرار می‌کند.

## GI-AI-002 · مدل واقعیِ تحویل‌شده با مدل درخواستی یکی نیست

- **شاهد (MEASURED):** درخواست با `openrouter/free` انجام شد و پاسخ `model=baidu/ernie-5.5-flash-preview:free` برگشت.
- **تأثیر:** این طراحی free-router است و در پاسخ ثبت می‌شود (خوب)، اما کیفیت/هزینه/رفتار بین اجراها تغییر می‌کند؛ هر تحلیل باید model provenance را نگه دارد (که نگه می‌دارد).

## GI-TEST-004 · هشدارهای Deprecation روی Python 3.14

- **شاهد (MEASURED):** 746 warning در یک اجرا، عمدتاً `asyncio.set_event_loop_policy` از `pytest-asyncio` و `asyncio.iscoroutinefunction` از FastAPI.
- **تأثیر:** آیندهٔ Python 3.16 اجرا را می‌شکند؛ امروز فقط نویز است.


---

## به‌روزرسانی وضعیت — ۱۴ نوامبر ۲۰۲۶

| شناسه | وضعیت جدید | شاهد |
|---|---|---|
| GI-DB-001 | **RESOLVED** | `backend/database/session.py` (`_sqlite_now`, `_install_sqlite_compat`)؛ `tests/test_sqlite_alembic_writes.py` ۴ passed؛ insert واقعی روی DB ساخته‌شده با Alembic |
| GI-DB-002 | **RESOLVED** | `_server_version()` بر اساس dialect؛ `/health/db` ok |
| GI-AI-001 | **RESOLVED** | `backend/ai/gateway/gateway.py`؛ `attempted` + skip نامزد غیرمجاز؛ خطای واقعی Provider حفظ می‌شود |
| GI-OPS-001 | **RESOLVED** | `domains/news/source_registry.py` + `backend/api/routers/ingestion.py` |
| GI-TEST-002 | **RESOLVED** | `tests/test_health.py` با `skipif` لاین SQLite |
| GI-DOC-001 | **RESOLVED** | `docs/ROLE_MATRIX.md` |
| GI-UI-001 | **PARTIALLY RESOLVED** | دکمهٔ «دریافت اکنون» اضافه شد؛ `metrics()`/`chartPanel()` هنوز کد مرده |
| GI-OPS-004 (backup فقط PG) | **PARTIALLY RESOLVED** | مسیر SQLite backup/restore/verify پیاده و با دادهٔ واقعی تست شد؛ مسیر pg_dump در این ماشین تست نشد |
| GI-REPO-002 (`apps/web_leftover_locked`) | **BLOCKED_OWNER_INPUT** | ACL قفل؛ بدون دسترسی/تأیید حذف نشد |
| GI-TEST-004 (warning ها) | **OPEN** | 746 warning در اجرای کامل؛ منشأ کتابخانه‌ای |
| CI راه‌دور | **NOT_VERIFIED** | بدون push |

### نتیجهٔ suite پس از اصلاحات

- SQLite: `1912 passed, 2 skipped, 0 failed` — لاگ `.tmp-audit-2026/pytest_final_sqlite.log`
- PostgreSQL 16.16: `1913 passed, 1 skipped, 0 failed` — لاگ `.tmp-audit-2026/pytest_final_pg.log`
- Ruff: `All checks passed!`

---

## اقلام جدید کشف‌شده در آزمون ارسال زنده — ۱۵ نوامبر ۲۰۲۶

| شناسه | شدت | مشکل | وضعیت | شاهد |
|---|---|---|---|---|
| GI-ALERT-001 | P1 | مسیر Alert فقط `SMTP_USER` را می‌خواند و `SMTP_USERNAME` (نام مستندشده) را نادیده می‌گرفت → login انجام نمی‌شد | **RESOLVED** | `domains/alerts/delivery.py`؛ `tests/test_alert_smtp_transport.py::test_username_falls_back_to_smtp_username` |
| GI-ALERT-002 | P1 | `SMTP_USE_TLS=true` همیشه `SMTP_SSL` (پورت ۴۶۵) را انتخاب می‌کرد؛ ارسال روی ۵۸۷ با `SSLError` شکست می‌خورد | **RESOLVED** | ارسال واقعی موفق پس از اصلاح؛ `test_port_587_uses_starttls_not_implicit_ssl` |
| GI-ALERT-003 | P2 | `delivery.py` از `os.getenv` می‌خواند ولی `.env` در `os.environ` بارگذاری نمی‌شود؛ اجرای مستند محلی کانال Alert را همیشه `skipped` می‌کند | **OPEN (تصمیم مالک)** | `python -c "os.getenv('TELEGRAM_BOT_TOKEN')"` → None با وجود مقدار در `.env` |

نتیجهٔ ارسال واقعی: Telegram `sent` با `message_id=8`؛ SMTP `sent`؛ هر دو در `alert_deliveries` با
`delivered_at` ثبت شدند.

## GI-ARCH-001 — آرشیو برای ردیف‌های پارک‌شدهٔ screening هرگز اجرا نمی‌شد

- **شدت:** P1 (قابلیت حفاظت داده بی‌اثر)
- **شاهد (MEASURED):** در دیتابیس آزمایشی ۱۹ از ۲۰ مقاله `is_eligible → ("active_dispatch",)` داشتند؛
  هر ۱۹ ردیف `screening@v1` با `status=pending` و `last_error="screening_unavailable: LOCAL_DISABLED,..."` بودند.
- **علت ریشه‌ای:** `_active_dispatches` هر `pending` را Job فعال می‌شمرد، ولی `mark_blocked` عمداً ردیف را
  `pending` نگه می‌دارد تا attempts نسوزد.
- **اصلاح:** استثنای ردیف‌های پارک‌شده با مارکر مشخص، صرفاً وقتی `status == "pending"` باشد.
- **وضعیت:** **RESOLVED** — `tests/test_archive_eligibility_blocked.py` (۴ تست)، واجد شرایط ۱→۲۰،
  `gi_audit_archive_2.zip` با ۲۰ مقاله و sha256 `50b5eecc…`.

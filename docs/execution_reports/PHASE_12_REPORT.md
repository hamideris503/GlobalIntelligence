# گزارش فاز ۱۲ — آزمون restart وسط Job

**تاریخ:** ۱۵ نوامبر ۲۰۲۶  
**سرویس:** `GlobalIntelligence-Backend` روی پورت `8010` (Task Scheduler + supervisor)  
**دیتابیس:** `dev.db` (SQLite) — همان DB سرویس نصب‌شده

## ۱. هدف و روش

هدف: اثبات این‌که قطع ناگهانی (kill -9) در میانهٔ یک Job واقعی، نه داده از دست می‌دهد و نه
داده را دوباره می‌سازد.

روش: ingest واقعی (RSS زنده، `MOCK_MODE=false`) → کشتن پروسه با `taskkill /F` در حالی که
Job/ردیف dispatch در وضعیت `running` است → بررسی بازیابی پس از restart supervisor.

پیش‌نیاز: `dev.db` هیچ منبعی نداشت، بنابراین `python -m db.seed.sources` اجرا شد
(**۱۹ منبع جدید، افزودن داده — هیچ چیز حذف/تغییر نکرد**).

## ۲. آزمون الف —kill وسط ingest

| گام | شاهد |
|---|---|
| Job شروع شد | `POST /api/ingest/jobs` → `202`, id `b9d4db2b-…` |
| در T+4s | `jobs_active=1`، `documents=0` (fetch در جریان) |
| kill -9 | `killing_pid=21188 at 20:28:47.622` → `SUCCESS: terminated` |
| بازیابی سرویس | `/health` → 200 پس از **۳ ثانیه** |
| علامت‌گذاری Job | `status=failed`, `message="interrupted: process restarted before completion"` |
| لاگ startup | `interrupted ingest jobs marked failed | n=1` |
| داده‌های ذخیره‌شده | `documents=4`, `articles=4` — **هیچ از دست نرفت** |
| داده تکراری | `documents_dup_groups=0`, `article_dup_groups=0` |

## ۳. آزمون ب — اجرای دوبارهٔ همان ingest (اثبات عدم تکرار)

```
status=completed  message="sources_ok=2 sources_failed=0 fetched=40 stored=8 duplicates=4"
```

| شاهد | مقدار |
|---|---|
| documents بعد از اجرای دوباره | **12** (= ۴ قبل از kill + ۸ جدید) |
| `documents_dup_groups` | **0** |
| `article_dup_groups` | **0** |

۴ آیتمی که پیش از kill ذخیره شده بودند در اجرای دوباره به‌عنوان `duplicates` شناسایی شدند و
**دوباره درج نشدند** (کلید یکتایی per-source `(source_id, hash, content_hash)`).

## ۴. آزمون ج — kill وسط dispatch (زنجیرهٔ تحلیل)

`POST /api/classify/run?limit=12` اجرا شد (طبقه‌بندی واقعی) و در لحظه‌ای که یک ردیف dispatch
واقعاً `running` بود، سرویس کشته شد:

```
running_dispatch_rows=1 at 20:33:53.379
killing_pid=13580 at 20:33:54.575
```

### دو نقص واقعی که همین آزمون آشکار کرد (هر دو رفع شد)

| # | نقص | شاهد | اصلاح |
|---|---|---|---|
| GI-DISPATCH-001 | ردیف `running` بعد از restart تا انقضای lease (**۹۰۰ ثانیه**) قفل می‌ماند؛ `recover_at_startup` با lease پیش‌فرض آن را رها نمی‌کرد | ردیف `event_extraction@v1` دقیقه‌ها `running` ماند، `dispatch recovery` هیچ لاگی نداشت | `recover_at_startup` → `recover_stale(stale_seconds=0)`؛ در `service.recover_stale` مقدار ۰ یعنی «هیچ owner زنده‌ای وجود ندارد» (بدون پنجرهٔ مهلت) |
| GI-DISPATCH-002 | روی SQLite، claim ردیف `retryable` همیشه استثنا می‌داد: `TypeError: can't compare offset-naive and offset-aware datetimes` → هر tick شکست می‌خورد و **هیچ retry اجرا نمی‌شد** | ۱۱ بار `dispatch tick failed` با traceback در `logs/backend-8010.out.log` | `claim()` با `.execution_options(synchronize_session=False)` — مقایسه در DB انجام می‌شود، نه در Python |

### نتیجهٔ آزمون ج پس از رفع

```
[20:36:45] dispatch stale running recovered | n=1
[20:36:45] dispatch recovery | {'stale': 1, 'reenqueued': 0}
row: event_extraction@v1  status=retryable  attempts=1  last_error="stale running recovered after restart"
[20:41:59] dispatch tick | {'claimed': 1, 'completed': 1, 'retryable': 0, 'terminal': 0, 'blocked': 0,
                            'tasks': {'event_extraction': {'completed': 1}}}
row: event_extraction@v1  status=completed  attempts=2
```

## ۵. وضعیت نهایی داده (پس از سه قطع و سه restart)

```
documents: 12                documents_dup_groups: 0
articles: 12                 article_dup_groups: 0
jobs: completed=2 failed=1 (فقط Job قطع‌شده) active=0
dispatch_rows: 10            dispatch_dup_pairs: 0            running: 0
dispatch: همهٔ ۱۰ ردیف completed
```

`failed=1` همان Job قطع‌شده است و **عمداً** failed است تا نیمه‌کاره به‌عنوان موفق جلوه نکند.

## ۶. تست‌های افزوده و اجراشده

- `tests/test_dispatch.py::test_startup_recovery_frees_rows_claimed_just_before_a_crash`
- `tests/test_dispatch.py::test_retryable_row_is_claimable_after_a_db_roundtrip`
  (اعتبارسنجی شد: با برداشتن موقت اصلاح **fail** می‌شود، با اصلاح pass)
- `pytest tests/test_dispatch.py tests/test_domain_routing.py tests/test_domain_engines.py -q`
  → **78 passed, 1 skipped** (۵.۶۲s)
- `ruff check` روی فایل‌های تغییریافته → **All checks passed**
- سوئیت کامل پس از اصلاحات: `python -m pytest tests -q`
  → **1928 passed, 2 skipped, 746 warnings in 446.20s (0:07:26)**، `exit=0`
  (خروجی خام: `.tmp-audit-2026/fullsuite.log`)؛ مبنای قبلی ۱۹۱۲ passed / ۲ skipped بود و
  افزایش ۱۶ تست از تست‌های افزوده‌شدهٔ همین دورهٔ کاری است.
- همان سوئیت روی **PostgreSQL 16.16** در DB تازهٔ `gi_pg_lane_phase13`
  (`alembic upgrade head` → rc=0، سپس `pytest tests -q`)
  → **1929 passed, 1 skipped, 746 warnings in 1044.22s (0:17:24)**، `exit=0`
  (خروجی: `.tmp-audit-2026/pgsuite.log`)؛ کانتینر و DB موقت پس از اجرا حذف شدند.
  مجموع موارد هر دو لاین ۱۹۳۰ و بدون شکست است؛ اختلاف skip همان تست هم‌زمانی `claim`
  (فقط PG) است.

## ۷. آنچه اجرا نشد

- **reboot واقعی ویندوز** (trigger «At startup» تنظیم شده اما آزمون نشده).
- CI راه‌دور (نیازمند push).
- لاین PG روی سرور `gi_postgres` خودِ کاربر اجرا نشد: پورت‌های منتشرشدهٔ آن کانتینر
  (`15432`/`15433`) اتصال از میزبان را می‌بندند (`server closed the connection unexpectedly`)
  هرچند داخل کانتینر سالم است. تست روی یک PG 16.16 ایزولهٔ موقت اجرا و بعد حذف شد؛
  رفع پروکسی پورت نیازمند restart کانتینرهای کاربر است و انجام نشد.

## ۸. فایل‌های تغییریافته در این فاز

- `backend/ai/dispatch/runner.py` — `recover_at_startup` با `stale_seconds=0`
- `backend/ai/dispatch/service.py` — `recover_stale(stale_seconds=0)` و `claim()` با
  `synchronize_session=False`
- `tests/test_dispatch.py` — دو تست رگرسیون
- `.tmp-audit-2026/` — اسکریپت‌های آزمون (gitignored)

**وضعیت فاز:** آزمون restart وسط Job در سطح ingest و dispatch **PASS**، با دو نقص کشف و رفع‌شده.

# نقشه‌راه تکمیل GlobalIntelligence — Stage 96 تا 104

**نسخه:** ۲۸ اکتبر ۲۰۲۶ · **مبنا:** بازنگری نقشه‌راه ۲۸ اکتبر بر اساس راستی‌آزمایی مستقیم مخزن
**وضعیت مبنا:** `main` = `6e6a4b0` · `stage95-pg-ci-verification` = `9292754` (۹ commit جلوتر، PR ادغام نشده)

## English summary

Roadmap v2 replaces the unverified assumptions of the 28-Oct draft with measured facts:
the suite is **green on SQLite (1480/1480, 15m12s)** and **broken on PostgreSQL** (one
deadlock in `test_dispatch.py::test_claim_is_atomic`, 10 failures elsewhere), and CI was
narrowed to **77 of 1480 tests (~5%)** — which is exactly why nobody noticed. Stage 96 is
therefore re-scoped: settle uncommitted work, fix the PostgreSQL deadlock and the 10
failures, make tests genuinely offline, then restore the full suite to CI. Stages 97–104 are
unchanged in order and intent but now reference existing artifacts (labelling harness,
`decided_by` contract, alert engine) instead of assuming greenfield work. Nothing in this
document may be marked complete without a recorded command output.

---

## ۰) روش کار و مرزهای شاهد

این نقشه‌راه فقط بر پایهٔ چیزهایی نوشته شده که در مخزن قابل اجرا و اندازه‌گیری بود:

| سنجه | مقدار اندازه‌گیری‌شده (۲۸ اکتبر) |
|---|---|
| مجموعهٔ تست روی SQLite | **۱۴۸۰ passed / ۰ failed — ۱۵:۱۲** |
| مجموعهٔ تست روی PostgreSQL 16 واقعی | **deadlock** در `test_dispatch.py::test_claim_is_atomic` (۱۶+ دقیقه بلوکه، بازتولید در ۱۰۰s) |
| بقیهٔ مجموعه روی PostgreSQL | **۱۳۰۸ passed / ۱۰ failed — ۷:۴۳** |
| پوشش تست در CI شاخه | ۴ فایل از ۱۰۶ فایل = **۷۷ تست از ۱۴۸۰ (~۵٫۲٪)** |
| پوشش تست در CI شاخهٔ main | کل suite روی `postgres:16` |
| migration روی PG16 | `upgrade head` ✅ · head یکتا `88a9b2c1d4e5` ✅ · `downgrade base` + `upgrade head` ✅ |
| فایل‌های migration | main: ۳۶ · شاخه: ۴۰ (عدد ۴۱ ناشی از شمارش `__pycache__` بود) |
| `ruff check backend domains tests scripts source_bot` | **All checks passed** |
| `.env` در درخت مخزن | ردیابی نمی‌شود |

**تأیید نشده (و نباید مبنای تصمیم شود):** وضعیت PR #1، اجرای راه‌دور CI روی GitHub، افشای کلید در تاریخچه/آرشیوها، دسترسی واقعی VPS.

**قاعدهٔ حاکم:** «فایل ساخته شد» شاهد نیست. هر مرحله فقط با خروجی فرمان، عدد اندازه‌گیری‌شده یا رفتار مشاهده‌شده بسته می‌شود. هر جا مدرکی نیست، وضعیت `NOT_VERIFIED` ثبت می‌شود، نه ✅.

---

## ۱) قواعد ثابت (بدون استثنا)

1. Mock هرگز به‌جای دادهٔ واقعی گزارش نمی‌شود؛ در هر گزارش کیفیت، ستون `mock/real` جدا است.
2. هیچ مقدار secret در سند، گزارش، لاگ یا فایل قابل اشتراک چاپ نمی‌شود.
3. migration فقط با آزمون رفت‌وبرگشت روی PG و پس از backup.
4. Retention: اول dry-run، بعد انتقال، حذف فقط با backup + audit + تأیید سیاست.
5. یک PR = یک هدف؛ تغییر بزرگ یک‌جا ممنوع.
6. شواهد ناکافی ⇒ `INSUFFICIENT_EVIDENCE`، نه عدد ساختگی.
7. شماره‌گذاری Stage فقط در همین سند مرجع است؛ در کد و commit از شناسهٔ تسک (`F-xx`) استفاده شود، نه «Stage NN».
8. پس از هر مرحله: `ROADMAP.md`، `TASKS.md`، `PROGRESS.md` و `PRODUCTION_READINESS.md` با همان نتیجه همگام می‌شوند.

---

## ۲) ترتیب و وابستگی

```
Stage 96 (تثبیت + PG)  ──┬──> Stage 97 (مجموعهٔ طلایی)  ──┬──> Stage 101 (ترجمه)
                         ├──> Stage 98 (تحویل هشدار)      │
                         ├──> Stage 99 (پروفایل کشور)     │
                         ├──> Stage 100 (Retention) ──────┘
                         ├──> Stage 102 (بدهی فنی، PRهای کوچک و موازی)
                         └──> Stage 103 (VPS) — پس از ۹۶ تا ۱۰۰

Stage 104 (کالیبراسیون) — از اولین روز دادهٔ واقعی، مستقل از ۱۰۳
```

---

# Stage 96 — تثبیت نسخه، PostgreSQL و CI

**اولویت:** بحرانی · **وضعیت:** در انتظار اجرا · **دروازهٔ همهٔ مراحل بعدی**

### هدف
شاخه‌ای که می‌خواهیم ادغام شود، باید روی پایگاه‌دادهٔ واقعی (PostgreSQL) سبز باشد، نه فقط روی SQLite؛ و هیچ تغییر ارزشمندی بیرون از commit نمانده باشد.

### کارها

**۹۶-۱ — تعیین‌تکلیف وضعیت کاری (اولین کار، قبل از هر چیز دیگر)**
روی دیسک ۱۱ فایل تغییر‌یافتهٔ commit‌نشده (dispatch runner/router، `database/session.py`، `settings.py`، `db/migrations/env.py`، سه تست) و فایل‌های untracked (`tests/test_screening_recovery.py`، `tests/test_stage96_cost.py`، `domains/news/run_*.py`) وجود دارد که در PR #1 نیستند.
- برای هر فایل تصمیم ثبت شود: commit، stash، یا حذف آگاهانه.
- hash پایه ثبت شود تا امکان بازیابی باشد.
- شاهد: `git status --porcelain` خالی (یا فقط artifacts نادیده‌گرفته‌شده).

**۹۶-۲ — رفع deadlock دیسپچ روی PostgreSQL**
`tests/test_dispatch.py::test_claim_is_atomic` روی PG قفل می‌کند: یک session در `idle in transaction` ردیف `article_dispatches` را قفل کرده و session دوم روی `UPDATE` در `wait_event=transactionid` می‌ماند؛ روی SQLite (تک‌اتصال) این حالت رخ نمی‌دهد.
- تست بازطراحی شود تا «اتمیک‌بودن claim» را واقعاً بسنجد (دو تراکنش واقعی/دو thread با commit، یا سنجش `rowcount` بدون قفل متقابل).
- اختیاری و مرتبط با F-11: استفاده از `SELECT … FOR UPDATE SKIP LOCKED` در مسیر claim تا دو worker پشت یک ردیف نایستند.
- شاهد: همان تست روی PG زیر ۵ ثانیه پاس شود.

**۹۶-۳ — رفع ۱۰ شکست PostgreSQL** (فهرست دقیق در `docs/FIXES_BACKLOG.md`: F-05 تا F-07)
- ۴ تست `test_settings::discover_*`: پچ سراسری `socket.getaddrinfo` + DSN با `localhost` + NullPool باعث `ConnectionTimeout` می‌شود. تأییدشده: با DSN روی `127.0.0.1` هر ۵ تست پاس می‌شوند. تصمیم: یا DSN تست روی IP، یا محدودکردن دامنهٔ پچ DNS، یا pool مناسب.
- ۴ تست `*_missing_article_is_terminal`: روی PG با `ForeignKeyViolation` می‌شکند، چون حالت «dispatch بدون مقاله» با FK قابل ساخت نیست. تصمیم صریح لازم است: یا تست به سطح handler منتقل شود، یا شاخهٔ terminal برای مقالهٔ گمشده به‌عنوان «غیرقابل‌رخداد در PG» مستند و پوشش آن با روش دیگری تأمین شود.
- ۲ تستی که صراحتاً `driver == "sqlite"` را assert می‌کنند: به `same bind as test session` تغییر کنند.
- شاهد: `pytest tests -q` با `DATABASE_URL` پستگرس → `0 failed`.

**۹۶-۴ — آفلاین‌کردن واقعی تست‌ها**
`tests/conftest.py` فقط `domains.news.source_verify.resolve_host_ips` را patch می‌کند، اما `source_bot/security.py` تابع را با import مقداری گرفته است؛ در نتیجه هر تست ingest واقعاً DNS می‌زند و کندترین تست ۲۴ ثانیه است (علت اصلی ۱۵ دقیقه‌ای‌شدن suite).
- patch به `source_bot.security.resolve_host_ips` (یا import ماژولی) گسترش یابد.
- یک تست محافظ اضافه شود: «هیچ resolve واقعی در تست رخ نمی‌دهد».
- شاهد: زمان suite کاهش محسوس + تست محافظ سبز.

**۹۶-۵ — بازگرداندن کل suite به CI**
CI شاخه اکنون فقط ۴ فایل (۷۷ تست، ~۵٪) را اجرا می‌کند و همین، deadlock و ۱۰ شکست PG را پنهان کرده است.
- پس از ۹۶-۲/۳/۴، مرحلهٔ تست CI به `pytest tests -q` روی `postgres:16` برگردد.
- زیرمجموعهٔ سریع می‌تواند به‌عنوان مرحلهٔ *اضافی* بماند، اما جایگزین دائمی کل suite نشود.
- شاهد: لاگ CI با تعداد تست برابر ۱۴۸۰ (یا بیشتر) و `0 failed`.

**۹۶-۶ — بهداشت تست (گیت جدید)**
- تست وابسته به cwd: `tests/test_deploy.py::test_check_local_files` از ریشه پاس و از `backend/` فِیل می‌شود → مسیرها نسبت به `Path(__file__)` ساخته شوند. **✅ F02.5: مسیر از `Path(__file__).resolve().parents[1]`.**
- وابستگی به پوشهٔ temp ویندوز: اجرای موازی/تکرارشده باعث `PermissionError` روی `pytest-current` و ۱۳ فِیل کاذب می‌شود → در مستندات اجرا، `--basetemp` توصیه یا fixture اصلاح شود. **✅ F02.5: ریشهٔ temp اختصاصی هر اجرا در `tests/conftest.py`؛ `--basetemp` فقط workaround.**
- شاهد: suite از هر دو cwd سبز.

**۹۶-۷ — مستندسازی هم‌راستا**
- `ROADMAP.md` از «Phase 52 = پایانی» خارج و به این سند ارجاع دهد.
- `TASKS.md`: ادعای «ruff شامل `source_bot` نیست» حذف شود (اکنون شامل است و lint پاس است).
- `AUDIT_REPORT.md` (متعلق به HEAD `7d7ed17`) و `PRODUCTION_READINESS.md` با وضعیت جدید همگام شوند.
- `AGENTS.md`: «~۶۵ فایل تست» → ۱۰۶ فایل (۱۱۳ فایل در پوشه).
- شاهد: diff مستندات + بازبینی چشمی که هیچ سند دیگری «تکمیل پروژه» اعلام نمی‌کند.

**۹۶-۸ — امنیت و بهداشت مخزن**
- بررسی تاریخچه/آرشیو از نظر کلید؛ در صورت افشا، ابطال و جایگزینی (اقدام مالک).
- `.gitignore`: افزودن `pg*.txt`، `pytest-*.txt`، `.pytest-tmp*/`، `.pytest-pg-tmp/`، `pytest_temp/`، `.freebuff/`.
- حذف/انتقال ۱۵ فایل زبالهٔ ریشه.
- شاهد: `git status --porcelain` تمیز + گزارش «secret یافت نشد/ابطال شد».

**۹۶-۹ — ادغام**
PR پس از سبز شدن CI کامل روی PG ادغام شود؛ سپس CI روی `main` سبز بماند.

### شرط عبور Stage 96
- [ ] `git status` تمیز؛ هیچ تغییر ارزشمند commit‌نشده باقی نمانده.
- [ ] `pytest tests -q` روی PG واقعی: **۰ failed** و بدون deadlock.
- [ ] CI: lint + migration (up/down/up، head یکتا) + **کل suite روی PG** + build فرانت + build هر دو ایمیج.
- [ ] اجرای suite از ریشه و از `backend/` سبز.
- [ ] مستندات هم‌راستا و بدون ادعای تکمیل نادرست.

---

# Stage 97 — مجموعهٔ طلایی و ارزیابی غربالگری

**اولویت:** بحرانی برای اعتمادپذیری AI · **وابستگی:** Stage 96

### وضعیت موجود (بر خلاف فرض نسخهٔ اول نقشه‌راه)
پیش‌نیازها تا حد زیادی ساخته شده‌اند و نباید دوباره ساخته شوند:
- `backend/ai/evaluation/local_screening.py`: `prepare_bundle` / `validate_bundle` / `merge_bundle` / fingerprint + امتیازدهی (`accuracy`, `Brier`, `abstained`).
- `docs/LOCAL_SCREENING.md` صریح ثبت کرده: «۲۰۰ برچسب انسانی — `WAITING_FOR_INPUT_DATA`».
- قرارداد provenance از قبل هست: `Article.decided_by ∈ {rules, ai, small_model, NULL}`.
- `INSUFFICIENT_EVIDENCE` و گیت mock در production پیاده شده است.

### کارها
1. **برچسب انسانی** ۱۰۰–۲۰۰ خبر متنوع (زبان، موضوع، کشور، منبع، تازگی، اهمیت) با راهنمای برچسب‌گذاری مکتوب — این کار مالک/تحلیلگر است، نه کد.
2. جداسازی **dev/tune** از **final test**؛ تنظیم آستانه و prompt فقط روی dev.
3. ارزیابی با ورودی یکسان برای: قواعد قطعی، Kev، Laya، fallback Gateway — و ثبت اینکه کدام اجرا mock بوده.
4. **افزودن متریک‌های جدید** به هارنس موجود: precision/recall/F1 و confusion matrix **per class** (اکنون فقط accuracy و Brier هست)، به‌همراه نرخ `INSUFFICIENT_EVIDENCE`/pending، زمان اجرا، RAM، هزینهٔ واقعی.
5. ثبت provenance هر تصمیم: `decided_by` + احتمال/اعتماد + نسخهٔ مدل + prompt/version + زمان + علت fallback.
6. تفکیک `rejected` / `skipped` / `failed` / `fallback` از موفقیت واقعی مدل در گزارش.
7. اگر دقت مدل کوچک به آستانه نرسید، فقط پیش‌فیلتر بماند و تصمیم پرریسک نگیرد.

### شرط عبور
- [ ] hash مجموعه + برچسب‌ها + راهنمای برچسب‌گذاری قابل بازتولید.
- [ ] گزارش روی دادهٔ کنارگذاشته‌شده (نه dev)، با ذکر محدودیت نمونه.
- [ ] آستانهٔ پیشنهادی ۸۵٪ توافق انسانی؛ پس از دیدن توزیع کلاس‌ها و هزینهٔ خطا بازبینی و ثبت شود.
- [ ] برای هر تصمیم مهم، `decided_by` + احتمال + نسخهٔ مدل + علت fallback قابل بازیابی.
- [ ] هیچ ادعای «دقت production» از چند ده نمونه یا از mock.

---

# Stage 98 — تحویل هشدار و تکمیل Settings

**اولویت:** بالا · **وابستگی:** Stage 96 · **وضعیت فعلی:** `AlertEngine` فقط `evaluate/acknowledge/resolve` دارد؛ هیچ کانال تحویلی وجود ندارد.

### کارها
1. موتور هشدار دست‌نخورده بماند؛ تحویل لایهٔ جدا باشد (تولید هشدار ≠ ارسال).
2. کانال‌های مستقل Telegram و Email؛ توکن/SMTP رمزنگاری‌شده و هرگز در UI/log برنگردد.
3. وضعیت تحویل: `queued / sent / failed / retrying / acknowledged` + شناسهٔ یکتای هر هشدار.
4. retry با backoff، timeout، جلوگیری از ارسال تکراری (idempotency key)، cooldown.
5. Settings: پیکربندی، تست اتصال، ارسال پیام آزمایشی، فعال/غیرفعال، نمایش آخرین خطا (بدون secret).
6. شکست یک کانال، کانال دیگر و موتور تحلیل را از کار نیندازد.

### شرط عبور
- [ ] یک هشدار آزمایشی واقعی به Telegram و Email برسد (شاهد: شناسهٔ پیام + رکورد تحویل).
- [ ] سناریوهای شبکهٔ قطع، credential نامعتبر، rate limit، retry و ارسال تکراری تست شوند.
- [ ] نتیجهٔ ارسال در API/UI دیده شود؛ در صورت شکست، موفقیت جعلی ثبت نشود.

---

# Stage 99 — پروفایل کشور قابل تنظیم

**اولویت:** بالا · **وابستگی:** Stage 96 · **وضعیت فعلی:** `COUNTRY_DOMAINS = {"IR": "iran"}` در `backend/ai/dispatch/routing.py` و ماژول `domains/iran/*` — یعنی حالت ایران هاردکد است.

### کارها
1. «حالت ایران» به مدل پروفایل عمومی تبدیل شود؛ رفتار فعلی = پروفایل پایه (بدون تغییر رفتار).
2. فیلدهای پروفایل: کد کشور، منابع محلی، زبان‌ها، دارایی‌ها/شاخص‌ها، کانال‌های انتقال ریسک، وزن‌های تحلیلی، تنظیمات گزارش.
3. حذف شرط‌های `country == IR` از موتورهای اصلی؛ تصمیم‌گیری از پروفایل.
4. رفتار صریح برای داده ناقص/کشور بدون منبع/وزن ناسازگار (نه سقوط، نه عدد ساختگی).
5. یک کشور دوم فقط برای آزمون (بدون تغییر کد موتورها).
6. نسخهٔ پروفایل در خروجی‌های مهم ثبت شود.

### شرط عبور
- [ ] رفتار ایران قبل/بعد یکسان (تست مقایسه‌ای).
- [ ] کشور دوم فقط با پیکربندی + دادهٔ آزمایشی اضافه شود.
- [ ] تست تداخل وزن‌ها/منابع/دارایی‌ها/دادهٔ گمشده.

---

# Stage 100 — Retention چهارمرحله‌ای و پایش دیسک

**اولویت:** بالا · **وابستگی:** Stage 96 (و برای تحویل هشدار: Stage 98) · **وضعیت فعلی:** هیچ مسیر retention و هیچ `disk_usage` در کد نیست.

### مدل
Hot → Compressed (lossless، قابل بازگردانی) → Summarized (قابل ردیابی) → Deletion (فقط دسته‌های مجاز، با backup + audit).

### کارها
1. اندازه‌گیری واقعی حجم جدول‌ها/فایل‌ها، نرخ رشد، هزینهٔ ایندکس — قبل از انتخاب آستانه.
2. سیاست سن + فشار دیسک با hysteresis (آستانهٔ بالا/پایین) برای جلوگیری از رفت‌وبرگشت.
3. خروجی `dry-run`: ردیف‌های پیشنهادی، حجم آزادشدنی، دلیل تصمیم.
4. حفظ `hash`/`content_hash`/MinHash/`source_id` و پیوندهای ردیابی.
5. عدم حذف: `event`, `claim`, `evidence`, `forecast ledger`, `outcome`, `audit`, لاگ AI و سوابق replay.
6. پایش دیسک: کل/آزاد/روند/فضای backup/خطای نوشتن؛ هشدار ۷۰٪ (آستانهٔ نهایی پس از اندازه‌گیری).
7. انتقال/حذف: idempotent، دسته‌ای، قابل توقف، قابل بازیابی.

### شرط عبور
- [ ] dry-run روی snapshot یک هفته داده، گزارش کامل بدهد.
- [ ] در آزمایش اولیه هیچ حذف واقعی رخ ندهد.
- [ ] انتقال لایه‌ها با backup و restore سنجیده شود.
- [ ] صفر حذف ناخواسته از event/claim/evidence/forecast/outcome/audit.
- [ ] هشدار دیسک از مسیر Stage 98 برسد و شکست تحویل، شکست ثبت شود.

---

# Stage 101 — ترجمهٔ آفلاین (فقط نمایش)

**اولویت:** متوسط · **وابستگی:** Stage 97 (مجموعهٔ طلایی) + Stage 100

1. مقایسهٔ Argos Translate و OPUS-MT روی ≥۲۰ خبر فارسی/انگلیسی متنوع.
2. ثبت RAM/CPU، زمان، کیفیت اصطلاحات اقتصادی/ژئوپلیتیک، مجوز نرم‌افزار و مدل.
3. ترجمه lazy و فقط برای نمایش؛ تحلیل و طبقه‌بندی روی متن اصلی.
4. cache بر پایهٔ hash متن اصلی + زبان مبدأ/مقصد + نسخهٔ مدل؛ invalidation با تغییر مدل/متن.
5. خطای ترجمه، دریافت خبر و تحلیل اصلی را متوقف نکند؛ نبودِ ترجمه شفاف نمایش داده شود.
6. مقایسهٔ طبقه‌بندی متن اصلی با متن ترجمه‌شده روی مجموعهٔ Stage 97 (بدون جایگزینی متن اصلی).

**شرط عبور:** بازبینی انسانی کیفیت + مجوز مستند؛ مصرف توکن AI = صفر؛ cache/invalidation تست‌شده؛ متن اصلی همیشه در دسترس.

---

# Stage 102 — بدهی فنی و مقیاس‌پذیری (PRهای کوچک و اندازه‌گیری‌شده)

**اولویت:** متوسط تا بالا بر اساس اندازه‌گیری · **وابستگی:** Stage 96

اقلام مشخص (جزئیات در `docs/FIXES_BACKLOG.md`):

| # | قلم | شاهد فعلی |
|---|---|---|
| F-11 | `claim` بدون `SKIP LOCKED` — دو worker پشت یک ردیف | deadlock تست در PG |
| F-13 | race ساخت JobRun (check-then-insert، بدون ایندکس یکتای جزئی) | TASKS (بازآزمایی شود) |
| F-14 | Adaptive Router بی‌اثر؛ `record` مصرف‌کننده ندارد | TASKS |
| F-15 | ETag/Last-Modified بی‌اثر (adapter در هر fetch نو می‌شود) | TASKS |
| F-16 | قفل ربات با فایل temp → تک‌هاست؛ job نیمه‌کاره resume نمی‌شود | TASKS |
| F-17 | N+1 و load تمام‌جدولی (adjacency گراف، replay، macro context) | PRODUCTION_READINESS |
| F-18 | endpointهای سنگین در request thread | TASKS |
| F-19 | `topics`/`entities` به‌صورت Text (پیشنهاد JSONB) | TASKS |
| F-22 | rate limit تک‌فرایندی | PRODUCTION_READINESS |
| F-23 | آستانه/confidence کالیبره‌نشده | PRODUCTION_READINESS |

### شرط عبور
- [ ] برای هر قلم، خط مبنای عددی (زمان/تعداد query/حافظه) **قبل از تغییر**.
- [ ] رفتار API و نتیجهٔ کسب‌وکاری پیش/پس یکسان (تست مقایسه‌ای) مگر تغییر هدف باشد.
- [ ] بهبود با اندازه‌گیری ثبت شود؛ «بهتر شد» بدون عدد پذیرفته نیست.
- [ ] تست race/retry/idempotency/migration/failure-isolation.

---

# Stage 103 — استقرار VPS، TLS و عملیات پیوسته

**اولویت:** پس از ۹۶–۱۰۰ · **وضعیت:** BLOCKED تا دسترسی واقعی

1. VPS/DNS/دسترسی امن؛ هیچ secret در repo یا دستور ثبت‌شونده در log.
2. مسیر `scripts/deploy_vps.py` (dry-run پیش‌فرض) + `docs/VPS_DEPLOYMENT.md`؛ `.env` هرگز منتقل نشود.
3. TLS (Caddy/Nginx + گواهی معتبر)، firewall، محدودیت دسترسی، health check.
4. backup زمان‌بندی‌شده، چرخش نسخه، انتقال امن، آزمون restore.
5. n8n: یک workflow در هر بار، بعد از مشاهده و ثبت رفتار.
6. داشبورد عملیاتی: وضعیت job، خبر دریافت/تکراری/ناموفق، خطای provider، quota، **فضای دیسک**، وضعیت backup، آخرین موفقیت workflow.
7. پس از deploy: smoke، بررسی log بدون secret، restart/recovery، restore آزمایشی.

**شرط عبور:** `deploy_vps.py --live` موفق + smoke سبز + restore واقعی تأییدشده + ≥۷ روز عملیات بدون خطای بحرانی. تا آن زمان ادعای production-ready ممنوع.

---

# Stage 104 — کالیبراسیون و ارزیابی پیش‌بینی (پیوسته، چندماهه)

**شروع:** با اولین دادهٔ واقعی (نیازی به Stage 103 ندارد)

1. برای هر پیش‌بینی: هدف، افق، زمان ثبت، بازه، احتمال، فرض‌ها، شواهد، نسخهٔ داده/مدل.
2. موعد بسته‌شدن و منبع واقعیت **از پیش** تعریف شود (بدون cherry-picking).
3. متریک: MAE/RMSE برای عددی؛ Brier/LogLoss برای احتمالی؛ نمودار calibration؛ مقایسه با baseline ساده.
4. گزارش بر اساس هدف/افق/رژیم بازار/مدل؛ با نمونهٔ کم: بازهٔ عدم قطعیت + هشدار.
5. تغییر خودکار routing/وزن ممنوع، مگر با معیار، حداقل نمونه، نسخه‌بندی، امکان بازگشت و تست خارج از نمونه.
6. `superseded/expired/resolved` در audit باقی بمانند؛ تاریخچه بازنویسی نشود.

**شرط عبور:** چند ماه دادهٔ واقعی قابل ردیابی + مقایسهٔ خارج از نمونه با baseline + اعلام صادقانهٔ نتیجه + قابلیت replay برای هر تغییر وزن.

---

## پیوست الف — چک‌لیست بستن هر مرحله

- [ ] کد در شاخهٔ درست؛ بدون تغییر ناخواسته/فایل حساس.
- [ ] تست unit + regression مربوطه سبز.
- [ ] تست integration در محیط واقعی مربوطه (PostgreSQL برای ویژگی‌های PG).
- [ ] migration بررسی‌شده (up/down/up، head یکتا) در صورت تغییر schema.
- [ ] تست failure/retry/idempotency برای قابلیت‌های شبکه‌ای/کاری.
- [ ] لاگ و گزارش بدون secret؛ mock از real تفکیک‌شده.
- [ ] ROADMAP/TASKS/PROGRESS/PRODUCTION_READINESS هم‌گام.
- [ ] شاهد قابل اشاره برای شرط عبور (خروجی فرمان/عدد).

## پیوست ب — تصمیم‌های مالک پروژه

1. **Stage 96:** اجازهٔ commit/stash تغییرهای فعلی و اصلاح تست‌های PG.
2. **امنیت:** تعیین اینکه آیا `.env` یا کلید واقعی در Drive/RAR/backup/تاریخچه بوده؛ در صورت بله، ابطال و تولید مجدد.
3. **Stage 97:** تأمین برچسب انسانی (۱۰۰–۲۰۰ خبر) و تأیید آستانهٔ ۸۵٪.
4. **Stage 99:** انتخاب کشور دوم.
5. **Stage 103:** تأمین VPS و دسترسی امن در زمان لازم.
6. **Stage 104:** انتخاب اهداف پیش‌بینی (طلا، ارز، تورم، نفت) و افق‌ها.

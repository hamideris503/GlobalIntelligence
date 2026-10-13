# Source Bot — ربات مرکزی استخراج، dedup و اولویت‌بندی

مالک واحد استخراج خبری؛ تحلیل‌ها (اقتصاد/بازار/ژئوپلیتیک/رویداد/ادعا/پیش‌بینی) بدون تغییر ادامه می‌یابند.

## اجرا

```bash
python -m source_bot.run_bot --once              # یک‌باره (فقط منابع due)
python -m source_bot.run_bot --source "BBC Business"   # تک‌منبع
python -m source_bot.run_bot --forever --poll 300       # مستمر
python -m source_bot.scheduler                       # مستمر (پیش‌فرض ۳۰۰ ثانیه)
```

توقف کنترل‌شده: ساخت فایل `%TEMP%/source_bot.stop` (روی لینوکس `/tmp/source_bot.stop`).
جلوگیری از اجرای هم‌زمان: قفل `%TEMP%/source_bot.lock`.

## جریان

```
Fetch (adapter) -> Extract -> Normalize (موجود) -> Deduplicate (موجود) -> Prioritize (قواعد + AI fallback)
  -> NewsIngestionPipeline.store_item (قرارداد فعلی، RawItem) -> تحلیل‌های موجود
```

- آداپتورها مستقیم در DB نمی‌نویسند؛ فقط `RawItem` برمی‌گردانند.
- `Article.importance` تحلیلی دست‌نخورده؛ اولویت دریافت در `documents.ingestion_priority/score/reason/source/status` + `doc_metadata` است.

## انتخاب آداپتور از رجیستری (تک‌مالک هر منبع)

| وضعیت منبع | مالک | رفتار ربات |
|---|---|---|
| RSS با feed_url | ربات (`rss`) | دریافت واقعی (wrapper روی `RSSFetcher` موجود) |
| api_url ثبت‌شده | ربات (`rest_json`) | JSON با ETag/pagination؛ بدون credential -> `AUTH_REQUIRED` |
| data_download_url با .csv | ربات (`csv`) | دانلود محدود، نگاشت ستون، خطای سطر ایزوله |
| data_download_url غیر-csv | ربات (`xml`) | پارسر امن؛ اگر RSS بود -> هدایت به مسیر RSS |
| scrape با homepage_url | ربات (`html`) | Scrapy دریافت + Trafilatura استخراج (بدون دانلود مجدد) |
| dataset/api بدون endpoint ثبت‌شده | موتور تخصصی macro/market (حفظ‌شده) | ربات دخالت نمی‌کند (`specialized`) |
| scrape بدون homepage | — | `skip` صادقانه تا homepage ثبت شود |

مسیر قدیمی مستقلی برای RSS خبری وجود ندارد که حذف شود: `NewsIngestionPipeline` و `RSSFetcher` حفظ و reuse شدند (نه بازنویسی). موتورهای تخصصی `domains/macro` و `domains/markets` حفظ شدند.

## اولویت P0..P4

قواعد قطعی (`priority_engine.py`) با نرمال‌سازی فارسی (ی/ک/نیم‌فاصله) روی کپی نرمال؛ متن خام تغییر نمی‌کند.
آستانه‌ها از env: `SOURCE_BOT_TH_P0/P1/P2/P3` (پیش‌فرض ۹۰/۷۵/۵۰/۲۵).
AI Gateway (`task=source_priority`) فقط وقتی `needs_ai` (confidence پایین، نزدیکی به مرز، تعارض، کمبود اطلاعات)؛ پاسخ با schema اعتبارسنجی می‌شود و نامعتبر هرگز اعمال نمی‌شود. قطع AI -> `RULES_FALLBACK_AI_UNAVAILABLE` یا `PRIORITY_PENDING`؛ retry بدون دریافت مجدد.

## امنیت

فقط http/https، بدون userinfo، مسدودسازی loopback/خصوصی/link-local/metadata ابری، بررسی redirect، سقف حجم/timeout/retry/نرخ، رعایت robots.txt (Scrapy `ROBOTSTXT_OBEY`)، بدون secret در لاگ (`redact_headers`)، متن وب = داده غیرقابل‌اعتماد (هیچ exec از پاسخ AI).

## متغیرها

`SOURCE_BOT_TIMEOUT/MAX_BYTES/MAX_CSV_BYTES/MAX_PAGES/MAX_DEPTH/CONCURRENCY/DELAY/MAX_REDIRECTS/MAX_RETRIES/INTERVAL/TH_P0..P3/AI_MIN_CONF/AI_MARGIN/AI_ENABLED` — جزئیات در `.env.example`.

## تست‌ها

```bash
python -m pytest tests/test_source_bot_extract.py tests/test_source_bot_priority_dedup.py tests/test_source_bot_integration.py -q
```

واقعاً اجرا شد: ۲۵ تست سبز (بدون شبکه) + اجرای زنده تک‌منبع BBC (‏fetched=20 واقعی، duplicates=20) + migration زنده `f7a8b9c0d1e2`.

## ضمیمه مرحله دوم (2026-10-12)

اشکالات واقعی پیدا و رفع شد:

1. **Mock به‌جای تصمیم AI (بحرانی):** mock برای schema اولویت همیشه `P0` معتبر می‌ساخت و runner آن را `AI_DECIDED` می‌کرد. رفع: `ai_prioritize` پرچم `is_mock` برمی‌گرداند؛ mock فقط `RULES_MOCK_AI` می‌شود و سطح قواعد می‌ماند.
2. **Route سایه‌خورده:** `ROLE=fast_extraction` باعث می‌شد route خالی `source_priority` هرگز درگیر نشود. رفع: `ROLE=source_priority`.
3. **پیش‌بررسی ناسازگار با pipeline:** runner فقط `content_hash` را چک می‌کرد ولی pipeline یکتایی `(source, url, content)` دارد. رفع: هم‌سو شد؛ محتوای یکسان با URL متفاوت ذخیره و بعد با `DedupService` خوشه‌بندی می‌شود (تست `exact_pairs>=1`).
4. **deliver رکورد اشتباه را تگ می‌کرد:** جست‌وجوی latest. رفع: یافتن دقیق با کلید یکتا.
5. **تکراری‌ها بی‌رد بودند:** لاگ `canonical_id/key` اضافه شد.
6. **ETag/Last-Modified ذخیره نمی‌شد؛ `max_redirects` سیم‌کشی نبود:** رفع در `rest_json`.
7. **csv/xml میزبان پس از redirect را چک نمی‌کردند:** `assert_public_host` روی `resp.url` اضافه شد.
8. **خطاها فقط type داشتند:** جزئیات کوتاه و امن (`Type:detail`) در metrics و `last_error` ثبت می‌شود.

تأیید زنده: BBC دوباره `20/20 duplicate` و شمارش ثابت ۲۷ (کل ۲۵۳) — بدون رکورد تکراری.
CBI ریشه‌یابی شد: DNS سالم (217.218.78.26) ولی TCP ناموفق (`dns_or_connect`) — محدودیت شبکه محیط، نه باگ کد؛ هیچ URL ساختگی ساخته نشد.
Docker: build با mirror پیش‌فرض `.env` به‌علت `SSL WRONG_VERSION_NUMBER` شکست می‌خورد (مشکل پیکربندی mirror، نه کد)؛ با `PIP_INDEX_URL=https://pypi.org/simple` ایمیج ساخته و import ربات داخل آن تأیید شد (`bot-ok 2.13.4`). ایمیج در حال اجرای فعلی قدیمی است (بدون source_bot) و پس از تصمیم کاربر باید redeploy شود.
قرارداد مشترک موتورهای تخصصی: `output.attach_priority` — بدون استخراج موازی.
## زمان‌بندی (مرحله سوم — آماده، غیرفعال)

- endpoint جدید `POST /api/ingest/bot` با بدنه `{source_name?, limit}` خروجی metrics می‌دهد؛
  احراز هویت از `include_router` اصلی می‌آید، منبع ناموجود 404، اجرای هم‌زمان 409 (قفل).
- workflow جدید `integrations/n8n/workflows/sourcebot-hourly.json` (id `gi-sourcebot-hourly`):
  تریگر ساعتی → یک POST به `/api/ingest/bot` (معادل `--once`، نه `--forever`)،
  با `active:false` و اعتبارسنجی تست‌های موجود سبز است.
- یافته هماهنگی: هر ۶ workflow فعلی n8n در production فعال‌اند (از جمله ingest نیم‌ساعته و
  hourly-intelligence)؛ بنابراین زمان‌بندی ربات تا تصمیم کاربر فعال نشده تا پردازش دوگانه
  پیش نیاید. از نظر فنی هم‌پوشانی بی‌خطر است (یکتایی + idempotency)، ولی مالکیت نهایی منابع
  RSS با کاربر است.
- فعال‌سازی (فقط با اجازه): import فایل در n8n و روشن‌کردن schedule؛ rollback = خاموش‌کردن workflow.

## تأیید staging (مرحله چهارم — محیط ایزوله gi_staging)

- بیلد ایمیج staging با ایندکس رسمی (بدون تغییر فایل، بدون دست‌کاری TLS): موفق.
- `up` staging (پورت‌ها 8001/5433، volume جدا): هر دو healthy؛ `/health` → ok.
- seed ۱۹ منبع؛ اجرای ربات تک‌منبع BBC: `fetched=20, stored=20, duplicates=0` با اولویت `P1×2/P2×4/P3×3/P4×11`، `ai_used=0/ai_fallback=10` (mock اعمال نشد).
- ستون‌های اولویت روی هر ۲۰ رکورد پر؛ `duplicate_status=new`؛ `priority_status` شامل `RULES_MOCK_AI`؛ `Article.importance` untouched.
- اجرای دوباره: `fetched=20, stored=0, duplicates=20` — بدون رکورد ناخواسته.
- زنجیره پایین‌دست روی ردیف‌های ربات: classify=20، events=20، claims=20، evidence=20.
- production در این مرحله restart/redeploy نشد.

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
آستانه‌ها از env: `SOURCE_BOT_TH_P0/P1/P2/P3` (پیش‌فرض ۹۰/۷۵/۵۰/۲۵). هر مقدار باید عددی در `[0, 100]` و ترتیب اکیداً نزولی باشد (`TH_P0 > TH_P1 > TH_P2 > TH_P3`)؛ در غیر این صورت `BotConfigError` صریح داده می‌شود (بدون بازگشت بی‌صدا به پیش‌فرض). سطح نهایی هم فقط از مجموعهٔ `P0..P4` است: `deliver()` سطح نامعتبر را ذخیره نمی‌کند و خروجی API با نوع `PriorityLevel` محدود شده است. پیکربندی نامعتبر **پیش از هر fetch** تشخیص داده می‌شود: `run_once` پیش از قفل/دریافت، و `ingest_source_async` پیش از fetch، با خطای صریح متوقف می‌شوند (هیچ سندی با `priority=NULL` ناشی از خطای پیکربندی ذخیره نمی‌شود)؛ در Job وضعیت `failed` و در `POST /api/ingest/bot` کد `500` با پیام `priority configuration invalid` برمی‌گردد.
گروه‌های واژگانی (`urgent_fa`/`urgent_en`/`high_fa`/`high_en`/`conflict`) از `config/priority_keywords.toml` خوانده می‌شوند — منبع واحد واژه‌ها، بارگذاری مستقل از CWD، و خطای صریح (`PriorityKeywordsError`) در فایل خراب یا ناقص (بدون fallback بی‌صدا).
AI Gateway (`task=source_priority`) فقط وقتی `needs_ai` (confidence پایین، نزدیکی به مرز، تعارض، کمبود اطلاعات)؛ پاسخ با schema اعتبارسنجی می‌شود و نامعتبر هرگز اعمال نمی‌شود. قطع AI -> وضعیت عملیاتی `RULES_FALLBACK_AI_UNAVAILABLE` (و برای پاسخ mock: `RULES_MOCK_AI`) حفظ می‌شود و «کم‌اطمینانی» وضعیت را بازنویسی نمی‌کند؛ retry بدون دریافت مجدد.

### provenance تصمیم اولویت (مشترک مسیر عادی ingestion و Source Bot)

تک‌منبع منطق: `source_bot/priority_engine.py:priority_provenance` — کلیدها در `doc_metadata`:

| کلید | معنا |
|---|---|
| `priority_decision_source` | `rules` (قواعد با confidence کافی) / `ai` (پاسخ معتبر و پذیرفته‌شدهٔ AI) / `pending` (قواعد زیر آستانه، بدون تصمیم معتبر AI) |
| `priority_score_source` | همیشه `rules` |
| `priority_confidence` | confidence تصمیم نهایی؛ در `pending` = `null` |
| `rules_priority_confidence` | confidence موتور قواعد (مستقل از AI) |
| `ai_priority_confidence` | فقط پاسخ معتبر و پذیرفته‌شدهٔ AI؛ mock/نامعتبر/unavailable = `null` |

- `priority_score` همیشه امتیاز deterministic قواعد است، حتی وقتی سطح نهایی از AI آمده باشد (تفاوت سطح در `ingestion_priority` دیده می‌شود).
- آستانهٔ مشترک: `UNRELIABLE_CONFIDENCE = 0.3` در `source_bot/priority_engine.py` (تک‌تعریف؛ مسیر عادی ingestion همان را import می‌کند).
- `priority_status` فقط وضعیت عملیاتی است (`RULES_ONLY`/`AI_DECIDED`/`RULES_MOCK_AI`/`RULES_FALLBACK_AI_UNAVAILABLE` در مسیر بات و `RULES_ONLY`/`PRIORITY_PENDING` در مسیر عادی ingestion) و از منشأ معنایی تصمیم مستقل است ⇒ **مصرف‌کننده برای تشخیص «تصمیم قطعی» از «نامطمئن» باید `priority_decision_source` را بخواند، نه `priority_status` را.**
- mock یا AI unavailable هیچ تصمیم/confidence ساختگی AI نمی‌سازد؛ فقط وضعیت عملیاتی خود را نگه می‌دارد.

## امنیت

فقط http/https، بدون userinfo، مسدودسازی loopback/خصوصی/link-local/metadata ابری، بررسی **هر hop** redirect در برابر allowlist دامنهٔ منبع (مسیر full-text)، سقف حجم/timeout/retry/نرخ، رعایت robots.txt (Scrapy `ROBOTSTXT_OBEY` و `RobotFileParser` پیش از استخراج متن مقاله — مرحلهٔ ۲۵)، بدون secret در لاگ (`redact_headers`)، متن وب = داده غیرقابل‌اعتماد (هیچ exec از پاسخ AI).

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
> وضعیت فعلی (2026-10-19): `attach_priority` (`source_bot/output.py:147`) هنوز **caller تولیدی ندارد** (فقط در تست فراخوانی می‌شود؛ مسیر تولیدی از `deliver` استفاده می‌کند) و کلیدهای provenance جدید را نمی‌نویسد. ستون `canonical_id` هم هنوز **نویسندهٔ تولیدی ندارد**؛ لاگ `runner.py:278` مقدار id سند موجود را با برچسب `canonical_id` چاپ می‌کند، نه این ستون.

## زمان‌بندی (مرحله سوم — آماده، غیرفعال)

- endpoint جدید `POST /api/ingest/bot` با بدنه `{source_name?, limit}` خروجی metrics می‌دهد؛
  احراز هویت از `include_router` اصلی می‌آید، منبع ناموجود 404، اجرای هم‌زمان 409 (قفل).
- workflow جدید `integrations/n8n/workflows/sourcebot-hourly.json` (id `gi-sourcebot-hourly`):
  تریگر ساعتی → یک POST به `/api/ingest/jobs` (معادل `--once`، نه `--forever`)؛
  از مرحلهٔ پانزدهم به endpoint دارای `JobRun` تغییر کرد تا وضعیت/تاریخچهٔ هر اجرا ثبت شود،
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

## پایش روزانه و اجرای کنترل‌شده (مرحله پانزدهم)

### ۱. آماده‌سازی — فقط گزارش و آمار (بدون fetch)
```bash
python -m scripts.bot_daily_report --day 2026-10-18
python -m scripts.bot_daily_report --days 7 --out data/cache/bot_reports/week.json
```
منبع حقیقت: `JobRun(job_name="ingest").payload.result.by_source` (تفکیک هر منبع، از مرحلهٔ پانزدهم).
شاخصی که اندازه‌گیری نمی‌شود در `unavailable_fields` صریحاً ناموجود اعلام می‌شود (مثل `ai_cost_usd`/`ai_http_attempts`؛
توکن‌ها از مرحلهٔ شانزدهم اندازه‌گیری می‌شوند) و اجراهای قدیمیِ بدون دادهٔ تفکیکی در
`history_gap.runs_without_per_source` شمرده می‌شوند — هیچ صفر جعلی ساخته نمی‌شود.
مسیر خروجی باید گیت‌ایگنور باشد (`data/cache/…` یا `logs/…`)؛ پوشهٔ `reports/` داخل Git است و برای خروجی تولیدشده مناسب نیست.

### ۲. اجرای یک‌بارهٔ کنترل‌شده (یک منبع)
با seed محلی و `MOCK_MODE=true`: یک درخواست `POST /api/ingest/bot` با بدنه `{"source_name": "<name>", "limit": 5}` و هدر `X-API-Key`.
پاسخ شامل `by_source` است (`fetch_attempts/fetch_ok/fetched/stored/duplicates/rejected_keyless/by_priority/pending/ai_*/duration_ms`).
این مسیر `JobRun` ثبت نمی‌کند (تست دستی)؛ برای تاریخچه از مسیر Job استفاده کن.

### ۳. زمان‌بندی ساعتی (فقط با اقدام صریح اپراتور)
- `SOURCE_BOT_INTERVAL` فاصلهٔ هر منبع (ثانیه، پیش‌فرض 3600 = ساعتی)؛ `due_sources` منبع موعدرسیده را انتخاب می‌کند.
- حلقهٔ tick محلی: `python -m source_bot.scheduler` یا `python -m source_bot.run_bot --forever --poll 300`.
- مسیر دارای تاریخچه: `POST /api/ingest/jobs` (پاسخ 202 + `JobRun` با وضعیت `pending/running/completed/partial/failed`).
  workflow `sourcebot-hourly.json` (`active:false`) به همین endpoint می‌زند؛ فعال‌سازی فقط با import و روشن‌کردن schedule در n8n.
- اجرای هم‌زمان: قفل فایل (`%TEMP%\source_bot.lock`) → اجرای دوم 409/RuntimeError؛ خطای یک منبع بقیه را متوقف نمی‌کند.

### ۴. تفکیک «fetch شد / فقط ثبت شد / تکراری»
- `fetch_attempts=0` → fetch انجام نشد (skip/specialized/پلان نامعتبر).
- `fetched>0` و `stored=0` → آیتم آمد ولی ذخیره نشد: `duplicates` (تکراری واقعی) یا `rejected_keyless` (بی‌هویت).
- `duration_ms` مدت واقعی همان منبع و `retries = fetch_attempts - 1`. dedup پس از ingest (`duplicate_cluster`) در این اعداد نیست.

### ۵. توقف کنترل‌شده
ساخت فایل stop (`%TEMP%\source_bot.stop` در ویندوز، `/tmp/source_bot.stop` در لینوکس) → اجرای جاری در مرز امن می‌ایستد؛
`--once` خودش تمام می‌شود. برای اجرای بعدی فایل stop را حذف کن. قفل رها می‌شود (finally).
نتیجه `stopped=true` است و در مسیر Job وضعیت `partial` ثبت می‌شود (جزئیات: بخش «اجرای کنترل‌شده و ایمن»).

### ۶. شواهد لازم برای تأیید یک روز عملیات
خروجی `python -m scripts.bot_daily_report --day <YYYY-MM-DD>` (JSON، ذخیرهٔ گیت‌ایگنور) +
`GET /api/ingest/jobs/{id}` برای هر اجرا (started/finished/duration/result) + لاگ بک‌اند.
اگر `history_gap.runs_without_per_source > 0` بود، آن اجراها در آمار هر منبع نیامده‌اند و باید در گزارش ذکر شوند.

### ۷. معیار آزمون هفت‌روزه (هنوز اجرا و تأیید نشده)
هفت روز اجرای ساعتی؛ هر روز: `runs.failed_without_result` ناشی از پیکربندی صفر، هیچ سند با `ingestion_priority=NULL`
از خطای پیکربندی، `sum(by_priority) == stored` برای هر منبع، و خطاهای هر منبع با پیام امن (بدون secret).
هر بخشی از این معیار که اندازه‌گیری نشود، به‌عنوان تأییدنشده گزارش می‌شود.

## مصرف AI — معنای شمارنده‌ها (مرحلهٔ شانزدهم)

مسیر واقعی: `runner.py` → `ai_prioritize()` → `AIGateway.generate()` → provider.
`AIResponse.usage` (توکن ورودی/خروجی/مجموع) از خود provider می‌آید و پیش‌تر در
`ai_priority_fallback` دور ریخته می‌شد؛ حالا همان مقدار در `result["usage"]` برمی‌گردد و
`SourceMetrics.record_ai()` آن را برای **همان منبع** ثبت می‌کند (بدون جدول/ستون جدید؛ در همان
`JobRun.payload.result.by_source`).

| شمارنده | معنی (قرارداد) |
|---|---|
| `ai_used` | تصمیم Priority واقعاً از AI پذیرفته شد (معنای قبلی، بدون تغییر) |
| `ai_fallback` | تصمیم روی قواعد ماند: خطا/timeout/خروجی نامعتبر **یا** پاسخ mock (معنای قبلی) |
| `ai_calls` | فراخوانی‌های سطح Source Bot (هر آیتم حداکثر یک‌بار) |
| `ai_ok` / `ai_failed` / `ai_mock` | پاسخ واقعی قابل‌استفاده / بی‌نتیجه / mock — همیشه `ai_calls = ok + failed + mock` |
| `ai_usage_events` / `ai_usage_missing` | پاسخ دارای usage کامل (ورودی+خروجی) / بدون usage کامل |
| `ai_tokens_in` / `ai_tokens_out` / `ai_tokens_total` | فقط مقادیر گزارش‌شدهٔ provider؛ مجموع = in + out وقتی total نیامده باشد |
| `ai_cost_usd` + `ai_cost_events` | فقط اگر خود پاسخ `cost_estimate` معتبر داشته باشد؛ وگرنه `null` |
| `ai_providers` | تعداد پاسخ موفق به تفکیک provider (برای تشخیص تخمین Cloudflare) |

گزارش روزانه: `ai_usage` (جمع بازه) و `sources[].ai` با `status` =
`available` / `partial` / `missing` / `mock_only` / `not_instrumented`.
`mock_only` یعنی همهٔ تماس‌های آن منبع mock بوده‌اند (مصرف واقعی صفر نیست، ناموجود است).
`not_instrumented` یعنی اجرای قبل از این مرحله — اعداد آن `null` است، نه صفر.
`history_gap.runs_without_ai_usage` تعداد اجراهای بدون دادهٔ مصرف را می‌شمارد.

محدودیت‌های شناخته‌شده: retry/fallback داخلی Gateway به‌صورت تلاش‌های HTTP جدا دیده نمی‌شود
(فقط پاسخ نهایی یک usage دارد، پس دوباره‌شماری نمی‌شود)؛ mock مصرف واقعی ندارد و شمرده نمی‌شود؛
Cloudflare توکن را با تخمین chars/4 می‌دهد و فقط از `ai_providers` قابل تشخیص است؛
هیچ provider واقعی نرخ/هزینه گزارش نمی‌کند، پس `ai_cost_usd` عملاً `null` است
(هزینه فقط با قیمت نسخه‌دار و معتبر، در مرحله‌ای جدا).

## اجرای کنترل‌شده و ایمن (مرحلهٔ هجدهم)

### ۱. `--limit` در برابر `--items`
| گزینه | معنی | پیش‌فرض | بازه |
|---|---|---|---|
| `--limit N` (بدون تغییر) | حداکثر تعداد **منبع** در اجرای خودکار | 50 | هر عدد (برش بعدی) |
| `--items N` | حداکثر آیتم **پردازش‌شده از هر منبع** در همین اجرا | نامشخص = بدون سقف (رفتار قبلی) | عدد صحیح 1..200 |

```bash
python -m source_bot.run_bot --once --source "BBC Business" --items 3
```
- مقدار نامعتبر (`0`، `201`، غیرعدد) در CLI **پیش از هر fetch** با exit code 2 رد می‌شود.
- مسیر API: فیلد اختیاری `max_items_per_source` در `BotRunRequest` (`ge=1, le=200`)؛ درخواست بدون این فیلد دقیقاً مثل قبل است و 422 فقط برای مقدار نامعتبر.
- مسیر Job همان مقدار را در `JobRun.payload.spec` نگه می‌دارد و به `run_once` می‌دهد.
- `run_once` خودش هم ورودی را اعتبارسنجی می‌کند (`ValueError` پیش از قفل و پیش از هر fetch) تا مسیر مستقیم/Job هم محافظت شود.

### ۲. محل و معنای سقف آیتم
- اعمال در `source_bot/runner.py` (`run_source`) **بعد از fetch و پیش از dedup/ذخیره**؛ آیتم‌های اضافی هرگز به `deliver` و DB نمی‌رسند.
- `fetched` همان خروجی adapter است (معنای قبلی حفظ شده). شمارندهٔ افزایشی `items_skipped_limit` (در `by_source` و جمع اجرا) تعداد آیتم‌هایی است که به‌خاطر سقف وارد پردازش نشدند.
- آیتم ردشده به‌خاطر سقف نه `duplicates` است نه خطای fetch؛ رابطهٔ قابل‌بررسی:
  `stored + duplicates + rejected_keyless ≤ fetched - items_skipped_limit`.
- سقف فقط مرحلهٔ پردازش را محدود می‌کند؛ محدودیت اندازهٔ پاسخ، صفحه‌بندی و محافظ‌های adapter مستقل و فعال می‌مانند (دانلود شبکه می‌تواند بزرگ‌تر از سقف باشد).
- گزارش روزانه: `sources[].items_skipped_limit`، `sources[].partial_runs` (تعداد اجراهای با وضعیت `partial`: توقف کنترل‌شده یا شکست بخشی از منابع) و جمع `items_skipped_limit`.

### ۳. منبع غیرفعال در انتخاب صریح
- `--source`/`source_name` پیش از هر درخواست خارجی هم وجود منبع و هم `Source.active` را بررسی می‌کند.
- منبع غیرفعال: `ValueError("source is inactive: <name>")`؛ در API همان قرارداد قبلی → HTTP 404 با `detail` امن (بدون secret). هیچ fetch/stored رخ نمی‌دهد و رکورد منبع تغییر نمی‌کند.
- انتخاب خودکار (`due_sources`) و رفتار منابع active/due بدون تغییر است.

### ۴. توقف کنترل‌شده: `stopped` / `partial`
- نقاط بررسی: ابتدای هر منبع (پیش از fetch) و بین آیتم‌ها (قبل از پردازش آیتم بعدی).
- خروجی اجرا: `stopped: true` در `BotMetrics` و `POST /api/ingest/bot` (HTTP 200 با آمار جزئی) — اجرای ناقص هرگز «کامل» گزارش نمی‌شود.
- مسیر Job: `JobRun.status="partial"` (از وضعیت‌های موجود، بدون وضعیت جدید)، `message` با پیشوند `stopped: partial run | ...` و `payload.result` شامل همان آمار جزئی (`fetched/stored/duplicates/by_priority/by_source/stopped`).
- `sources_ok` افزایش نمی‌یابد و `by_source[name].ok=false` می‌ماند؛ اسناد ذخیره‌شدهٔ قبل از توقف حذف نمی‌شوند.
- فایل stop تکراری، حذف‌شده یا ناموجود باعث خطای کنترل‌نشده نمی‌شود؛ قفل در `finally` آزاد می‌شود و اجرای بعدی پس از حذف فایل stop کار می‌کند.
- dedup پس از ingest حتی پس از توقف اجرا می‌شود: کاملاً محلی است، شبکه ندارد و فقط خوشه‌بندی می‌کند (حذف نمی‌کند).
- خطای پیکربندی Priority همچنان پیش از fetch اجرا را متوقف می‌کند (مرحلهٔ ۱۴).

### ۵. انتساب زمانی اسناد به `JobRun` (موقت، بدون `run_id`)
در این مرحله ستون/جدول جدیدی اضافه نشده است. برای آزمون کنترل‌شده:
1. هر اجرا فقط **یک منبع** (`source_name`) و یک `JobRun`.
2. بازهٔ UTC را از `started_at`/`finished_at` همان `JobRun` بردار.
3. در بازهٔ آزمون هیچ ingestion موازی اجرا نکن: scheduler/`--forever`/n8n خاموش، و قفل فایل (`%TEMP%\source_bot.lock`) مانع اجرای دوم است.
4. اسناد را با `source_id` + `retrieved_at BETWEEN started_at AND finished_at` بشمار.
5. این **انتساب زمانی** است، نه رابطهٔ قطعی سند→Job. اگر در همان بازه مسیر دیگری (pipeline دستی، classify، n8n) سند بسازد، شمارش آلوده می‌شود؛ به همین دلیل هم‌زمانی باید صفر باشد و این محدودیت در گزارش آزمون ذکر شود.

### ۶. بیشینهٔ تلاش‌های شبکه (retry تو‌در‌تو)
دو لایه وجود دارد و هر دو محدود و قابل‌پیش‌بینی‌اند:
- لایهٔ runner: `SOURCE_BOT_MAX_RETRIES` (پیش‌فرض 2) → حداکثر **3** فراخوانی `_fetch_plan`؛ backoff `2×(attempt+1)` ثانیه، بدون jitter.
- لایهٔ adapter/`safe_get`: تلاش داخلی adapter × hopهای redirect (`max_redirects=3` → حداکثر 4 GET برای هر تلاش).

| مسیر | تلاش داخلی هر `_fetch_plan` | بیشینهٔ GET در هر اجرا (runner=3) |
|---|---|---|
| RSS (`RSSFetcher.fetch`) | 2 × 4 hop | 24 |
| CSV | 1 × 4 hop | 12 |
| XML | 1 × 4 hop | 12 |
| REST-JSON | تا `max_pages` صفحه × 4 hop (پیش‌فرض 3 صفحه) | پیش‌فرض 36؛ با 20 صفحه 240 |
| HTML (crawl) | تا 20 صفحه × 3 تلاش (`RETRY_TIMES=2`) | 180 |
| HTML (تک‌صفحه) | 1 × 4 hop | 12 |
| `source_verify.fetch_url` (اعتبارسنجی منبع، نه ingest) | `MAX_RETRIES=1` → 2 تلاش | — |

- `429` در REST-JSON بدون retry برمی‌گردد (`http_429 rate limited`)؛ `5xx` در RSS یک retry داخلی دارد و سپس runner می‌تواند دوباره تلاش کند. هیچ حلقهٔ نامحدود یا jitter وجود ندارد.
- مسیر full-text (مرحلهٔ ۲۵) به‌ازای هر origin **یک** درخواست اضافه برای `robots.txt` دارد (کش‌شده در همان اجرا) و تنها پس از اجازهٔ آن یک GET برای هر مقاله انجام می‌شود.
- تست‌های `tests/test_bot_controlled_run.py` این سقف‌ها را با HTTP جعلی قفل می‌کنند (بدون درخواست واقعی).

### ۷. دامنهٔ این مرحله
این مرحله فقط کد و تست محلی است: هیچ منبع زنده، DNS/HTTP خارجی، provider واقعی، PostgreSQL اصلی، scheduler/n8n فعال، migration/ستون/جدول/dependency جدید، و هیچ آزمون ۱۰۰ خبر واقعی انجام نشده است.

## مرحلهٔ ۲۲ — متن اصلی مقاله از RSS و منشأ صریح داده

### ۱. خلاصهٔ RSS در برابر متن اصلی مقاله
- `raw_text` یک آیتم RSS همان **خلاصه/`description`** فید است (یا `content:encoded` اگر فید بدهد) — نه بدنهٔ کامل صفحهٔ مقاله.
- `raw_payload` نسخهٔ خام و دست‌نخوردهٔ entry فید است (شامل `summary`) و در استخراج متن اصلی هرگز تغییر نمی‌کند.
- متن اصلی (اگر استخراج شود) جای `raw_text` را می‌گیرد؛ خلاصهٔ RSS در `raw_payload` می‌ماند. یعنی دو چیز از هم قابل‌تفکیک‌اند.
- سه سند تاریخی مرحلهٔ ۲۰ (خلاصه‌محور، بدون `text_status`) عمداً دست‌نخورده ماندند.

### ۲. مسیر استخراج متن اصلی (`source_bot/fulltext.py`)
- **پیش‌فرض خاموش است.** فقط وقتی منبع دامنهٔ مقاله را اعلام کرده باشد فعال می‌شود:
  - `sources.endpoint_config` → `{"article_domains": ["bbc.co.uk", ...]}` (همان ستون JSON موجود؛ بدون migration)، یا
  - `SOURCE_BOT_ARTICLE_DOMAINS=bbc.co.uk,example.com` در همان فرایند، یا
  - `sources.homepage_url` / `sources.canonical_url` / `sources.domain` (host همان مقدار).
- فقط برای adapter `rss` اجرا می‌شود و **پس از اعمال سقف `--items`** — یعنی فقط آیتم‌های منتخب واجد شرایط‌اند.
- برای هر آیتم **حداکثر یک GET**: `HtmlAdapter.fetch_url` صفحه را با همان transport محافظت‌شده می‌گیرد و **همان HTML** را به Trafilatura می‌دهد (دانلود دوم برای extraction وجود ندارد). بین درخواست‌ها `SOURCE_BOT_DELAY` رعایت می‌شود.
- متن فقط وقتی جایگزین می‌شود که از خلاصهٔ فعلی **بلندتر** باشد؛ وگرنه خلاصه می‌ماند.
- استخراج هیچ‌وقت HTML خام را به‌عنوان متن تمیزشده ذخیره نمی‌کند (خروجی Trafilatura متن پاک است).

### ۳. وضعیت fallback در metadata
کلید `text_status` در `doc_metadata` (فقط وقتی قابلیت فعال باشد):
- `full_text_extracted` — متن مقاله جایگزین شد (`full_text_chars` هم ثبت می‌شود).
- `rss_summary_only` — فقط خلاصهٔ RSS داریم (host مجاز نیست، fetch خطا داد، یا استخراج کوتاه/خالی بود).
- `extraction_failed` — نه متن استخراج شد و نه خلاصه‌ای وجود داشت.
- از مرحلهٔ ۲۵، علت دقیق fallback در کلید `text_reason` ثبت می‌شود (پایین‌تر).

### ۴. منشأ داده: `real` / `mock` / `unknown`
- `provenance_of()` بدون کلید `mock` مقدار `unknown` می‌دهد؛ `unknown` هرگز مدرک real بودن نیست.
- پارس فید واقعی (`RSSFetcher.parse`) اکنون صریحاً `"mock": false` می‌گذارد → `real`.
- `MockFetcher` از قبل `"mock": true` می‌گذارد → `mock`.
- رکوردهای قدیمی بدون کلید، مطابق قرارداد **`unknown`** می‌مانند و تغییر نمی‌کنند.

### ۵. اثر بر Priority
- آستانه‌ها و کلیدواژه‌ها تغییر نکرده‌اند. با همان ورودی قبلی (بدون استخراج) امتیاز و وضعیت دقیقاً مثل قبل است.
- وقتی متن کامل بیاید، موتور اولویت همان متن را می‌بیند (بدنهٔ > ۲۰۰ نویسه `COMPLETE` می‌گیرد) — این رفتار مطلوب و مستند است، نه تغییر سیاست.

### ۶. محدودیت‌ها و نیازمندی‌های فعال‌سازی زنده
- **BBC Business در seed هیچ دامنهٔ مقاله اعلام نکرده** (`domain=feeds.bbci.co.uk` و `homepage_url`/`canonical_url` تهی)؛ پس تا وقتی `article_domains: ["bbc.co.uk"]` (یا `SOURCE_BOT_ARTICLE_DOMAINS=bbc.co.uk` برای همان فرایند) ست نشود، خروجی `rss_summary_only` است. این یک تغییر تنظیمات مجاز است، نه dependency جدید.
- `identity_hash` شامل `raw_text` است؛ برای اینکه جایگزینی خلاصه با متن کامل هویت خبر را عوض نکند، enrichment متنِ اولیهٔ فید را زیر کلید `identity_text` در metadata ثبت می‌کند و `normalize()` هویت را روی همان می‌بندد (پایین‌تر، مرحلهٔ ۲۳).
- استخراج متن روی `allowed_domains` سطح crawl اعمال نمی‌شود (آن مخصوص Scrapy crawl است)؛ گاردهای فعلی هر درخواست = `validate_url`/`target_allowed` (طرح/یوزر‌اینفو/loopback/شبکهٔ خصوصی/metadata)، pin کردن IP و بازبینی هر redirect + timeout/`max_bytes`/`max_redirects`. allowlist دامنهٔ مقاله و robots.txt در مسیر full-text از مرحلهٔ ۲۵ اضافه شده‌اند (پایین‌تر).
- آزمون زندهٔ این مسیر (fetch واقعی یک صفحهٔ مقاله) انجام نشده و باید در مرحلهٔ جداگانه و با مجوز اپراتور دیده شود.

## مرحلهٔ ۲۳ — پایداری هویت خبر در برابر استخراج متن کامل

### ۱. مشکل
هویت محتوایی (`content_hash`) از `title|raw_text` ساخته می‌شد. با enrichment، `raw_text` از خلاصهٔ RSS به متن کامل تغییر می‌کرد و برای همان URL یک `content_hash` دوم ساخته می‌شد؛ چون یکتایی `(source_id, hash, content_hash)` بود، دوباره برخورد نمی‌کرد و `store_item` آن را revision جدید (ردیف دوم) می‌دانست. نتیجه: یک خبر، دو `Document`/`Article` مستقل و شمارندهٔ `stored` بادکرده.

### ۲. قرارداد فعلی (بدون تغییر ساختار)
ترتیب هویت همان است: `external_id` (ردیف بدون URL) → canonical URL (`hash`) → محتوای اعلام‌شده. تغییر فقط این است که «محتوای هویت‌بخش» می‌تواند به‌صراحت توسط آداپتور اعلام شود:

- کلید `identity_text` در metadata: متنی که هویت خبر روی آن بسته می‌شود.
- `domains/news/normalizer.py::identity_body()` — اگر کلید حاضر باشد (حتی با مقدار تهی) همان مبناست، وگرنه `raw_text` فعلی. «حضور کلید» ملاک است تا سند خلاصه‌محور و متن‌کامل یک هش بدهند.
- `normalize()` همان را در `content_hash` به کار می‌برد؛ `raw_text` ذخیره‌شده دست‌نخورده (متن کامل) می‌ماند.
- `source_bot/fulltext.py` فقط وقتی متن را واقعاً جایگزین می‌کند `identity_text` = متن قبلی (خلاصهٔ فید) را ثبت می‌کند.
- `source_bot/runner.py::run_source` همان لنگر را در پیش‌بررسی دیتابیس به کار می‌برد تا با مقدار ذخیره‌شدهٔ `store_item` یکی باشد.

### ۳. رفتار نتیجه
| سناریو | نتیجه |
|---|---|
| خلاصه ذخیره شده، اجرای بعد متن کامل | duplicate؛ ردیف دوم ساخته نمی‌شود، متن قبلی حفظ می‌شود |
| متن کامل ذخیره شده، اجرای بعد fallback خلاصه | duplicate؛ متن کامل قبلی حفظ می‌شود |
| فید خلاصه/عنوان را واقعاً عوض کند (همان URL) | طبق قرارداد قبلی revision جدید (`revision+1`) |
| دو URL مستقل با متن یکسان | دو سند مستقل (هویت URL-محور) |
| ردیف بدون URL با `external_id` | همان قرارداد قبلی: `external_id` هویت است |
| ردیف بدون URL/عنوان/متن/payload | بی‌هویت؛ رد می‌شود (بدون ادغام) |

### ۴. محدودیت‌های باقی‌مانده
- تغییر فقط-بدنهٔ مقاله با خلاصهٔ ثابت در فید دیده نمی‌شود؛ چون هویت روی متن اعلام‌شدهٔ فید بسته شده است. برای revision بدنه‌محور باید تصمیم جدا گرفته شود (نیازمند تغییر قرارداد).
- رکوردهای قدیمی که پیش از این مرحله با خلاصه ذخیره شده‌اند، `identity_text` ندارند؛ اولین اجرای متن‌کامل برای آن‌ها ممکن است یک revision بسازد (رفتار قبلی، بدون اصلاح دادهٔ موجود).
- `identity_text` یک کلید metadata است (بدون migration/ستون جدید) و تنها در سندهای enriched دیده می‌شود.

## مرحلهٔ ۲۵ — allowlist روی تمام hopهای redirect + robots.txt پیش از full-text

### ۱. allowlist دامنه روی هر hop (نه فقط URL اولیه)
- `domains/news/source_verify.py::host_allowed()` تنها نقطهٔ حقیقت تطابق دامنه است: برابری دقیق یا زیردامنهٔ معتبر؛ `evilbbc.co.uk` و `bbc.co.uk.evil.com` رد می‌شوند.
- `_request_policy(url, allowed_hosts)` **اول** allowlist را می‌سنجد و **بعد** گارد IP/SSRF (`target_allowed`). پس مقصد خارج از فهرست حتی resolve هم نمی‌شود و public بودن IP مجوز عبور از allowlist نیست.
- پارامترهای جدید (پیش‌فرض تهی = رفتار قبلی، بدون اثر روی سایر adapterها):
  - `safe_get(..., allow_hosts=())` — روی **هر** hop قبل از `client.get`؛
  - `GuardedTransport(allowed_hosts=())` و `GuardedSyncTransport(allowed_hosts=())` — در نقطهٔ ارسال، پس redirect خودکار HTTPX هم نمی‌تواند از فهرست بیرون بزند؛
  - `fetch_url(..., allow_hosts=())` — `error_kind=host_not_allowed` برای hop غیرمجاز.
- `HtmlAdapter.fetch_url(url, allowed_hosts=...)` همان فهرست را به `safe_get` و transport می‌دهد؛ مسیر full-text آن را از `article_allowlist(source)` می‌گیرد.
- رد شدن مقصد redirect یعنی همان آیتم به `rss_summary_only` برمی‌گردد؛ URL اولیه **دوباره** دانلود نمی‌شود (حلقهٔ آیتم ادامه می‌یابد).
- گاردهای موجود دست‌نخورده‌اند: userinfo/scheme/loopback/شبکهٔ خصوصی/metadata، DNS pinning، TLS، `timeout`، `max_bytes`، `max_redirects`، رد پروکسی/uds.

### ۲. robots.txt پیش از دریافت متن مقاله
- برای هر article URL، اول `scheme://host[:port]/robots.txt` از **همان** مسیر محافظت‌شده (`GuardedTransport` + `safe_get` + allowlist روی هر hop) خوانده می‌شود؛ parser استاندارد `urllib.robotparser.RobotFileParser` (بدون dependency جدید) با UA `GlobalIntelligenceBot`.
- سیاست **fail-closed**: وضعیت غیر‑`200` (شامل 404)، بدنهٔ بیش از `min(max_bytes, 512KB)`، پاسخ بدون اعلان `user-agent` (HTML خطا/متن خالی/ناقص)، خطای fetch یا خطای parse ⇒ robots «نامعلوم» = «ممنوع» ⇒ هیچ GET برای مقاله و خلاصهٔ RSS حفظ می‌شود.
- `robots.txt` هر origin فقط **یک‌بار در همان اجرا** کش می‌شود (dict محلی `enrich_rss_items`)؛ هیچ کش بین‌اجرایی یا ستون جدیدی ساخته نمی‌شود.
- redirect خود robots.txt هم از allowlist عبور می‌کند؛ robots نمی‌تواند به دامنهٔ خارج از فهرست بپرد.
- رفتار RSS (خود فید) تغییر نکرده: کنترل robots فقط برای درخواست صفحهٔ مقاله است.

### ۳. ردگیری وضعیت (بدون ستون جدید)
- `text_status` همان سه مقدار قبلی است؛ کلید افزودنی `text_reason` در `doc_metadata` علت را ثبت می‌کند:
  `host_not_allowed` | `robots_disallowed` | `robots_unavailable` | `extraction_empty`.
- `full_text_extracted` تنها وقتی ثبت می‌شود که متن واقعاً استخراج و جایگزین شده باشد؛ در حالت‌های robots به‌طور پیش‌فرض دیده نمی‌شود.

### ۴. تست‌ها و دامنهٔ مرحله
- `tests/test_source_bot_redirect_robots.py` (۲۶ تست، شامل parametrize): زیردامنهٔ مجاز، مقصد عمومی خارج از فهرست، lookalike، IP خصوصی/metadata، چندمرحله‌ای با خروج در hop آخر، رد پیش از اتصال با شمارش درخواست‌ها، transport با `follow_redirects=True` (سرور loopback محلی)، robots مجاز/ممنوع/ناموجود/نامعتبر/خطا/redirect غیرمجاز، کش per-origin، و حفظ خلاصه و `raw_payload`.
- `tests/test_source_bot_fulltext.py` و `tests/test_source_bot_identity.py` با seam آفلاین `robots_fetch` (بدون درخواست واقعی) به‌روز شدند.
- این مرحله فقط کد و تست محلی است: هیچ اجرای زنده، DNS/HTTP خارجی، AI، migration، dependency، تغییر دادهٔ موجود یا تغییر سیاست dedup/Priority انجام نشده است.

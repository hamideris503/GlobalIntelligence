# DECISIONS.md

> ثبت تصمیمات معماری (Architecture Decision Records)
> قالب: Date / Context / Decision / Alternatives / Why selected / Consequences

---

## ADR-0031 — Geopolitical Engine: تنش وزنی شفاف به تفکیک بازیگر
**Date:** 2026-10-09
**Context:** Phase 22 باید تنش ژئوپلیتیک را از داده‌های موجود (رویداد + گراف) بدون AI بسنجد.
**Decision:**
- فرمول وزنی مستند v1 (حجم/غافلگیری/مناقشه/تحریم)؛ بازیگر بدون رویداد assessment ندارد.
- assessment ماهانه و idempotent؛ یال گراف یک‌بار برای هر موجودیت شمرده می‌شود.
**Alternatives:** score کشوری ثابت؛ تحلیل متنی LLM در همین فاز
**Why selected:** شفاف، قابل آزمون، Deterministic Core.
**Consequences:** با mock تک‌بازیگری؛ تطبیق نام رشته‌ای است.

---

## ADR-0030 — Macro Engine: تحلیل سری بدون score تجمیعی جعلی
**Date:** 2026-10-09
**Context:** Phase 21 باید سری‌های macro را تحلیل کند بدون اینکه «امتیاز کل» بی‌پشتوانه بسازد.
**Decision:**
- هر سری مستقل تحلیل می‌شود (yoy/شتاب/z-score/momentum)؛ z-score معیار واحد-آزاد momentum است.
- بدون score تجمیعی کشوری؛ overview فقط آخرین assessment هر شاخص را نشان می‌دهد.
- داده‌ی کم → فیلد تهی + confidence پایین (نه حدس)؛ upsert idempotent.
**Alternatives:** score وزنی کشوری؛ تفسیر LLM در همین فاز
**Why selected:** صداقت آماری، Deterministic Core؛ تفسیر به فازهای بعد.
**Consequences:** outlook کشوری بر عهده‌ی مصرف‌کننده (WorldState/Forecast) است.

---

## ADR-0029 — اصلاحات ممیزی: cosine مرکزدهی‌شده، پوشش no_data، پنجره‌ی drawdown
**Date:** 2026-10-09
**Context:** ممیزی مستقل سه ایراد مهم در Phase 18/20 یافت: (۱) cosine روی مقادیر خام 0..1 اختلاف سطح را نادیده می‌گیرد؛ (۲) ابعاد no_data به‌عنوان خنثی واقعی مقایسه می‌شدند؛ (۳) drawdown نسبت به سقف کل تاریخچه بود و کل جدول را load می‌کرد.
**Decision:**
- cosine فقط روی بردارهای مرکزدهی‌شده حول 0.5 (نقطه‌ی خنثی دامنه)؛ مرکزدهی داخل `cosine_distance` تا سوءاستفاده ناممکن باشد. خنثی↔خنثی → فاصله 0؛ خنثی↔جهت‌دار → فاصله 1.0 (نبود جهت، نه شباهت)؛ NaN هرگز.
- مقایسه فقط روی ابعاد معتبر مشترک (metadata موجود، method != no_data، confidence ≥ 0.3)؛ نبود metadata = نامعتبر (strict). اقلیدسی با sqrt(9/n) نرمال می‌شود. هر hit دارای compared_dims/coverage؛ مرجع با <۳ بُعد معتبر → 422 صریح.
- drawdown = افت از سقف ۲۵۲ روز اخیر با query محدود (۳۰۰ رکورد مرتب)؛ <۲ مقدار → None.
**Alternatives:** cosine خام (گمراه‌کننده)؛ حذف ابعاد بدون نرمال‌سازی؛ سقف کل تاریخچه؛ وزن‌دهی تطبیقی (به آینده موکول شد)
**Why selected:** صداقت آماری، قابل آزمون بودن، بدون AI، سازگار با قرارداد موجود.
**Consequences:** schema پاسخ `/api/analogues` دو فیلد افزوده دارد (compared_dims/coverage) + دو فیلد سطح outcome (valid_dims/min_valid_dims)؛ تست‌ها/مستندات به‌روز شدند.

---

## ADR-0028 — Historical Analogue: فاصله‌ی برداری فقط‌خواندنی + aftermath
**Date:** 2026-10-08
**Context:** Phase 20 باید «وضعیت فعلی ↔ وضعیت‌های تاریخی مشابه» را بدون AI و بدون داده‌ی جدید بسازد.
**Decision:**
- بردار ۹ سیگنال با ترتیب ثابت؛ دو متریک (euclidean پیش‌فرض، cosine)؛ شباهت 0..1؛ واگرایی هر سیگنال.
- فقط snapshotهای قدیمی‌تر از مرجع (گذشته، نه آینده)؛ مرجع پیش‌فرض آخرین snapshot.
- `aftermath`: snapshotهای بعدی + رویدادهای حافظه (layer=event) بعد از آنالوگ.
- فقط خواندنی: بدون migration، بدون AI.
**Alternatives:** embedding/AI similarity؛ وزن‌دهی سیگنال‌ها؛ لحاظ آینده
**Why selected:** قطعی، ساده، قابل ردیابی، Deterministic Core.
**Consequences:** وزن یکسان سیگنال‌ها (v1)؛ با تاریخچه‌ی کوتاه آنالوگ بدیهی است و با هر build بهتر می‌شود.

---

## ADR-0027 — Historical Memory: بایگانی ارجاعی با Point-in-Time timeline
**Date:** 2026-10-08
**Context:** Phase 19 باید «historical events, states, snapshots» را به حافظه‌ی قابل پرس‌وجو تبدیل کند (ورودی Phase 20 Analogue).
**Decision:**
- جدول `memory_records`: ارجاع سبک (layer/ref_type/ref_id) + importance + observed_at/recorded_at + متادیتا؛ یکتایی (layer, ref_type, ref_id).
- Enum `MemoryLayer` با هر ۷ لایه (۴ لایه‌ی آینده رزرو).
- گزینش قطعی: event_score آستانه‌ی 0.3، importance≥7، همه‌ی snapshotها.
- پرس‌وجوی `timeline(as_of)` با observed_at (نه recorded_at) برای صداقت Point-in-Time.
**Alternatives:** کپی کامل رکوردها (حجیم)؛ بایگانی بدون آستانه (نویز)؛ timeline بر recorded_at
**Why selected:** سبک، idempotent، قابل توسعه به لایه‌های بعد، بدون AI.
**Consequences:** رکوردها ارجاع‌اند؛ حذف موجودیت اصلی نیازمند سیاست retention در آینده است.

---

## ADR-0026 — World State: سیگنال‌های قطعی بدون AI و snapshot تاریخی
**Date:** 2026-10-08
**Context:** Phase 18 باید وضعیت فعلی جهان را به‌صورت ساختاریافته و قابل ردیابی بسازد (ورودی فازهای Forecast/Scenario/Risk).
**Decision:**
- ۹ سیگنال 0..1 با توابع خالص و نگاشت‌های مستند v1؛ نبود داده → 0.5 کم‌اعتماد (نه عدد جعلی).
- رژیم کلان از ربع‌بندی رشد×تورم؛ رژیم بازار از استرس×نقدینگی.
- هر build یک snapshot جدید (State Memory) با value_metadata کامل (value/timestamp/source/method/confidence).
- YoY فقط درون یک کشور (ترجیح USA).
- بدون AI و بدون migration (مدل/جدول از Phase 3 کامل بود).
**Alternatives:** تفسیر LLM برای وضعیت؛ تک‌snapshot بازنویسی‌شونده؛ میانگین چندکشوری
**Why selected:** قطعی، قابل ردیابی، تاریخچه‌دار، Deterministic Core.
**Consequences:** با mock کم‌اطلاع؛ نیازمند Provider واقعی برای سیگنال‌های رویدادی معنادار.

---

## ADR-0025 — Market Data: چندمنبعی رایگان با زنجیره‌ی fallback
**Date:** 2026-10-08
**Context:** Phase 17 باید FX/طلا/نفت/سهام/اوراق/کالا را بدون کلید و پایدار جمع‌آوری کند.
**Decision:**
- FX: open.er-api.com (primary) + ECB eurofxref XML (fallback رسمی).
- طلا/نقره: gold-api.com؛ نفت/سهام/اوراق/کالا: Yahoo Finance v8 chart.
- کاتالوگ ۱۳ نماد (`SYMBOLS`) با asset_class/unit/currency.
- زنجیره‌ی primary→fallback برای هر نماد + ایزولاسیون خطا؛ upsert idempotent در `MarketObservation` موجود (بدون migration).
- Frankfurter (Cloudflare block) و Stooq (JS challenge) رد شدند و مستند شدند.
**Alternatives:** تک‌منبع؛ FRED/EIA/AlphaVantage (نیازمند کلید)
**Why selected:** رایگان، بدون کلید، زنده تأییدشده، Free-First، Everything Replaceable.
**Consequences:** Yahoo بدون قرارداد رسمی است؛ fallback و mock برای پایداری. داده‌ی intraday实时 نیست (daily close).

---

## ADR-0024 — Economic Data: World Bank API و upsert idempotent
**Date:** 2026-10-08
**Context:** Phase 16 باید داده‌ی اقتصادی (inflation/GDP/unemployment/rates/trade/liquidity) را از منبع رایگان و بدون کلید جمع‌آوری کند.
**Decision:**
- استفاده از API رایگان بانک جهانی (`api.worldbank.org`) بدون نیاز به کلید (Free-First).
- نگاشت شاخص‌ها به کدهای استاندارد بانک جهانی (`FP.CPI.TOTL.ZG` و…).
- بازاستفاده از مدل `MacroObservation` با افزودن `series_id` و `meta` (JSON) برای ردیابی.
- upsert idempotent بر اساس UniqueConstraint (indicator, country, period, source_name).
- در حالت Mock، `MockFetcher` با داده‌ی deterministic.
**Alternatives:** FRED (نیازمند کلید)، اسکرپ وب (پرنوسان)، داده‌ی دستی (غیرقابل توسعه)
**Why selected:** رایگان، بدون کلید، ساختار استاندارد، پوشش همه‌ی شاخص‌های موردنیاز.
**Consequences:** فرکانس بیشتر شاخص‌ها `annual` است؛ داده‌ی ماهانه/فصلی در فازهای بعدی. نیازمند اینترنت برای داده‌ی واقعی.

---

## ADR-0001 — انتخاب معماری Modular Monolith + Workers
**Date:** 2026-10-07
**Context:** پروژه باید سریع قابل توسعه باشد و تیم/عامل به‌تنهایی آن را بسازد. Microserviceها هزینه عملیاتی و پیچیدگی زودهنگام ایجاد می‌کنند.
**Decision:** شروع با Modular Monolith (Backend واحد) + Workers برای پردازش پس‌زمینه. مرزهای ماژولار رعایت می‌شوند.
**Alternatives:** (1) Microservices کامل، (2) سرورلس، (3) Monolith بدون Workers
**Why selected:** Rule Against Premature Complexity (بند 105). Workers برای jobs زمان‌بندی‌شده ضروری است اما استخراج سرویس هنوز لازم نیست.
**Consequences:** امکان استخراج سرویس در آینده با حفظ مرزها؛ اجتناب از سربار عملیاتی.

---

## ADR-0002 — PostgreSQL به‌عنوان منبع اصلی داده
**Date:** 2026-10-07
**Context:** به یک منبع داده تراکنشی، رابطه‌ای و قابل اتکا برای اخبار، رویدادها، حافظه و پیش‌بینی‌ها نیاز داریم. TimescaleDB برای سری‌های زمانی در آینده ممکن است لازم شود.
**Decision:** PostgreSQL به‌عنوان Single Source of Truth. TimescaleDB در صورت نیاز بعداً به‌عنوان extension اضافه می‌شود.
**Alternatives:** MongoDB، ClickHouse، SQLite، TimescaleDB از روز اول
**Why selected:** بلوغ، قابلیت‌های JSONB، پشتیبانی geospatial/زمانی، و مسیر ارتقا به TimescaleDB.
**Consequences:** Redis از روز اول اضافه نمی‌شود مگر نیاز واقعی (Queue/Cache/RateLimit) اثبات شود.

---

## ADR-0003 — AI Gateway مستقل و Provider-Agnostic (Mock-First)
**Date:** 2026-10-07
**Context:** پروژه نباید به یک مدل یا Provider خاص (مثلاً Ollama یا یک شرکت) وابسته باشد، و باید بدون API پولی هم قابل توسعه باشد.
**Decision:** ساخت لایه AI Gateway با Provider Adapter. Mock Provider به‌عنوان Provider پیش‌فرض/توسعه. نام Providerها در منطق اصلی Hard-code نمی‌شود.
**Alternatives:** اتصال مستقیم به یک SDK، استفاده از LangChain به‌عنوان هسته، Ollama اجباری
**Why selected:** Free-First، قابلیت جایگزینی، تست بدون هزینه، انطباق با MOCK_MODE.
**Consequences:** همه‌ی فراخوانی‌های AI باید از Gateway عبور کنند. Gateway مسئول Fallback/Retry/Cost/Tracking است.

---

## ADR-0004 — محاسبات آماری Deterministic، تفسیر با LLM
**Date:** 2026-10-07
**Context:** Brier، Log Loss، VaR، Monte Carlo و … نباید به LLM سپرده شوند.
**Decision:** محاسبات کمّی در Python (کتابخانه‌های آماری) انجام و صرفاً تفسیر آن‌ها به LLM واگذار می‌شود.
**Alternatives:** واگذاری محاسبات به LLM، تولید اعداد توسط LLM
**Why selected:** دقت، تکرارپذیری، اجتناب از No Fake Precision.
**Consequences:** تفکیک صریح لایه «compute» از لایه «interpret».

---

## ADR-0005 — رعایت Point-in-Time Integrity از ابتدا
**Date:** 2026-10-07
**Context:** خطر look-ahead / future leakage در backtest و تحلیل.
**Decision:** ثبت زمان‌های published_at / retrieved_at / available_at / observed_at / revision_at برای داده‌ها؛ ممنوعیت Random Shuffle در backtest.
**Alternatives:** اصلاح بعدی داده‌ها، نادیده گرفتن زمان انتشار
**Why selected:** جلوگیری از نتایج گمراه‌کننده و غیرقابل‌اعتماد.
**Consequences:** طراحی مدل داده از Phase 3 این فیلدها را الزامی می‌کند.

---

## ADR-0023 — Knowledge Graph: Entity Resolution نام‌محور و روابط جهت‌دار
**Date:** 2026-10-08
**Context:** Phase 15 باید از مقالات/رویدادها موجودیت‌ها و روابط بسازد (Knowledge Graph). مدل‌های `Entity`/`EntityRelationship` از Phase 3 موجود بودند.
**Decision:**
- هویت موجودیت بر اساس **نام نرمال‌شده** (`casefold` + فشرده‌سازی فاصله) است، نه نوع؛ نوع از `other` به نوع مشخص ارتقا می‌یابد و نام‌های متفاوت در `aliases` ثبت می‌شوند.
- روابط جهت‌دار با AI از `actors` + `Article.entities` + متن رویداد استخراج می‌شوند؛ `relation` محدود به `RelationType`.
- رابطه‌ی نامعتبر/موجودیت ناشناخته بی‌صدا حذف نمی‌شود؛ شمارش (`rejected`) و لاگ می‌شود.
- در نبود رابطه‌ی معتبر، fallback هم‌رویدادی (`affects`) بین موجودیت‌های رویداد ساخته می‌شود.
- idempotency با `Event.graph_extracted`؛ یال تکراری وزن/اعتماد را تقویت و شاهد رویداد را اضافه می‌کند.
- فیلد `confidence` به `EntityRelationship` اضافه شد.
**Alternatives:** entity resolution نوع‌محور (تکرار موجودیت)؛ حذف بی‌صدا؛ ذخیره‌ی گراف بدون idempotency
**Why selected:** یکپارچگی موجودیت‌ها، قابلیت ردیابی، تکرارپذیری و جلوگیری از یال تکراری.
**Consequences:** گراف با Mock معنادار نیست (همه `"mock"`)—نیازمند Provider واقعی؛ resolution پیشرفته (fuzzy/embedding) به فاز بعد موکول شد.

---

## ADR-0022 — استقلال منابع: تفکیک mention از تأیید مستقل
**Date:** 2026-10-08
**Context:** Phase 14 باید وابستگی منابع را تشخیص دهد؛ «تعداد mention ≠ تعداد تأیید مستقل» (DATA_SOURCES.md). اگر رسانه‌های متعدد یک خبر را از یک منبع مرجع بازنشر کنند، شمردن آن‌ها به‌عنوان تأیید مستقل اشتباه است.
**Decision:**
- جدول `source_dependencies` یال‌های وابستگی را نگه می‌دارد (`source_id`, `depends_on_id`, `kind`, `weight`, `detected_by`) با یکتایی جفت.
- گراف وابستگی = یال‌های ثبت‌شده + heuristic هم‌دامنه؛ منابع وابسته با Union-Find به یک **منبع مستقل** فروکاسته می‌شوند. نماینده = بالاترین credibility سپس independence (deterministic).
- روی `Claim` سه فیلد: `supporting_source_count` (mention)، `independent_source_count` (مستقل)، `source_independence` (نسبت 0..1).
- `verification_status=corroborated` فقط با **≥۲ منبع مستقل**؛ mentionهای اضافی از منابع وابسته آن را تصدیق نمی‌کنند.
- یال دستی از طریق API/سرویس پشتیبانی می‌شود تا داده‌ی بیرونی (syndication/ownership) بعداً تغذیه شود.
**Alternatives:** شمردن صرف mention؛ استفاده از مدل زبانی برای تشخیص وابستگی؛ نادیده‌گرفتن وابستگی
**Why selected:** دقت‌بخشی به «تأیید مستقل»، deterministic بودن، قابلیت بازبینی و افزودن یال دستی.
**Consequences:** `corroborated` سخت‌گیرانه‌تر می‌شود؛ صحت وابستگی‌ها به کیفیت یال‌های ثبت‌شده بستگی دارد؛ heuristic هم‌دامنه ممکن است نیازمند تنظیم باشد.

---

## ADR-0021 — Evidence اتمی، idempotent و قطعی per Claim
**Date:** 2026-10-08
**Context:** Phase 13 باید برای هر Claim شواهد موافق/مخالف را از متن مقالات همان Event استخراج کند و وضعیت تأیید را به‌صورت قابل‌بازتولید تعیین کند.
**Decision:**
- Evidence در سطح Claim و فقط یک‌بار (`claims_extracted`/`evidence_extracted`) استخراج می‌شود تا تکرار پیش نیاید.
- هر Evidence دارای `direction` (supports/contradicts)، `summary`، `weight`، `confidence` و ارجاع به `document_id` و `source_id` است (منبعِ مبنا).
- موارد نامعتبر (direction غیرمجاز) بی‌صدا حذف نمی‌شوند؛ شمارش (`rejected`) و لاگ می‌شوند.
- `verification_status` با ماتریس قطعی `verify_status(supports, contradicts)` تعیین می‌شود، نه با مدل زبانی.
- خروجی Mock Provider باید برای `EVIDENCE_SCHEMA` معتبر باشد (رعایت enum در `_mock_from_schema`).
**Alternatives:** حذف بی‌صدا؛ تعیین status با LLM؛ ذخیره‌ی source_id نکردن
**Why selected:** idempotency، قابلیت ردیابی، حفظ ورودی Phase 14 (استقلال منابع)، و No Fake Precision.
**Consequences:** `source_id` باید در Evidence پر شود؛ Mock باید schema-driven بماند؛ فیلد `rejected` در پاسخ API و CLI گزارش می‌شود.

---

## ADR-0016 — ذخیره‌ی همه‌ی اسناد و یکتایی درون‌منبعی
**Date:** 2026-10-08
**Context:** بازبینی نشان داد ingestion سندهای منابع دیگر با content_hash یکسان را دور می‌ریخت؛ این با بند ۱۸ (تفاوت mention و تأیید مستقل) و فاز ۱۴ (Source Independence) در تناقض بود.
**Decision:** یکتایی سند فقط درون یک منبع و بر اساس `(source_id, hash, content_hash)` است (`uq_document_source_url_content`). همه‌ی اسناد منابع مختلف ذخیره می‌شوند. اگر همان URL با محتوای متفاوت بیاید، `revision` افزایش می‌یابد. تکراری‌بودن فقط با `duplicate_cluster` بیان می‌شود.
**Alternatives:** یکتایی سراسری بر اساس content_hash
**Why selected:** حفظ اطلاعات «چه کسی چه چیزی را گزارش کرد»، امکان محاسبه‌ی استقلال منابع.
**Consequences:** حجم ذخیره بیشتر؛ dedup نقش «تشخیص» را دارد نه «حذف».

---

## ADR-0017 — جلوگیری از mock در production
**Date:** 2026-10-08
**Context:** زنجیره‌ی Gateway همیشه با mock شروع می‌شد، پس گذاشتن API Key بی‌اثر بود و داده‌ی جعلی در DB ذخیره می‌شد.
**Decision:**
- Routeها به‌صورت پیش‌فرض خالی‌اند و زنجیره از تنظیمات ساخته می‌شود.
- در `MOCK_MODE=true` فقط mock استفاده می‌شود.
- در غیر آن، mock از زنجیره حذف و در نبود Provider واقعی خطا پرتاب می‌شود.
- فیلد `is_mock` روی پاسخ؛ classifier نتیجه‌ی mock را در production رد می‌کند.
**Alternatives:** حفظ mock به‌عنوان آخرین fallback سراسری
**Why selected:** جلوگیری از آلودگی داده و ادعای نادرست تحلیل واقعی.
**Consequences:** در production باید حداقل یک Provider واقعی پیکربندی شود.

---

## ADR-0020 — Claim اتمی و idempotent per Event
**Date:** 2026-10-08
**Context:** Phase 12 باید از Event/Article، Claim استخراج کند.
**Decision:** استخراج در سطح Event و فقط یک‌بار (`claims_extracted`)؛ Claimها به‌صورت subject-predicate-object با `claim_type` و confidence. در نبود AI، یک Claim پایه از فیلد action رویداد ساخته می‌شود. Evidence در Phase 13 جدا می‌شود.
**Alternatives:** استخراج در سطح هر Article (تکرار زیاد)؛ استخراج هم‌زمان Evidence
**Why selected:** کاهش تکرار، سادگی، تکیه بر رویداد به‌عنوان واحد معنایی.
**Consequences:** تفکیک Claim از Evidence نگه داشته می‌شود؛ تکرار Claims یکسان در رویدادهای مختلف در فاز ۱۳/۱۴ ادغام می‌شود.

---

## ADR-0019 — یک خوشه = یک Event (نسخه اول)
**Date:** 2026-10-08
**Context:** Phase 11 باید چند مقاله‌ی مرتبط را به یک Event تبدیل کند.
**Decision:** در نسخه اول، هر خوشه‌ی dedup → یک Event. استخراج فیلدها با AI؛ در نبود AI یک Event سبک از خود مقاله ساخته می‌شود. مقالات با `event_id`/`event_cluster` وصل می‌شوند.
**Alternatives:** splitting یک خوشه به چند رویداد با AI؛ خوشه‌بندی مستقل رویدادمحور
**Why selected:** سادگی و تکیه بر خوشه‌بندی موجود؛ جلوگیری از پیچیدگی زودهنگام (بند ۱۰۵).
**Consequences:** ممکن است یک خوشه شامل چند رویداد فرعی باشد؛ در فازهای بعدی می‌توان splitting افزود.

---

## ADR-0018 — احراز هویت حداقلی از ابتدا
**Date:** 2026-10-08
**Context:** بند ۶۹ امنیت را از ابتدا می‌خواهد؛ endpointها باز بودند.
**Decision:** هدر `X-API-Key` برای همه‌ی endpointها به‌جز `/health`. در production، `validate_production()` در startup نبود/ضعیف‌بودن `SECRET_KEY`/`API_KEY`/`MOCK_MODE` را رد می‌کند (fail-fast). `metadata` (مدل/timeout) از API عمومی حذف شد و روی طول پیام‌ها/tokens سقف گذاشته شد.
**Alternatives:** افزودن auth فقط در فاز ۴۴
**Why selected:** جلوگیری از مصرف اعتبار API توسط اشخاص ثالث و انتخاب مدل گران.
**Consequences:** n8n باید کلید را در credential خود نگه دارد؛ این احراز هویت حداقلی است و در فاز ۴۴ کامل می‌شود.

---

## ADR-0015 — Importance ترکیبی ولی Deterministic
**Date:** 2026-10-08
**Context:** بند 22 می‌گوید Importance نباید فقط بر اساس نظر LLM باشد.
**Decision:** LLM ابعاد (impact/scope/novelty/…) را در خروجی structured تخمین می‌زند، اما **محاسبه‌ی نهایی importance از ترکیب وزنی deterministic** در `compute_importance` انجام می‌شود و به بازه‌ی ۱..۱۰ نگاشت می‌شود.
**Alternatives:** واگذاری کامل importance به LLM؛ فرمول صرفاً rule-based بدون ورودی LLM
**Why selected:** تفکیک «compute» از «interpret» (ADR-0004)، تکرارپذیری، اجتناب از No Fake Precision.
**Consequences:** پارامترهای وزن قابل تنظیم‌اند؛ در Phase 51 می‌توان وزن‌ها را از داده‌ی واقعی یاد گرفت.

---

## ADR-0014 — Dedup بدون وابستگی خارجی (MinHash/LSH دست‌ساز)
**Date:** 2026-10-08
**Context:** بند 18 (Source Independence) و Phase 9 نیازمند تشخیص near-duplicate هستند. کتابخانه‌هایی مثل datasketch/minhashlsh وجود دارند اما وابستگی جدید می‌آورند.
**Decision:** پیاده‌سازی shingling + MinHash + LSH + Union-Find با stdlib. آستانه و پارامترها قابل تنظیم.
**Alternatives:** datasketch، simhash، embeddings + ANN
**Why selected:** Free-First و Rule 9 (دپندنسی فقط با دلیل)؛ الگوریتم کوچک و قابل نگهداری است. در صورت نیاز به دقت/مقیاس بیشتر، در فازهای بعدی می‌توان به embeddings مهاجرت کرد.
**Consequences:** برای دیتاست‌های بسیار بزرگ، اجرا باید دوره‌ای/پنجره‌ای باشد؛ dedup سبک در ingestion (content_hash) همچنان اول خط دفاع است.

---

## ADR-0013 — Raw-first و Point-in-Time در Ingestion
**Date:** 2026-10-08
**Context:** بند 19 (ذخیره raw) و بند 45 (Point-in-Time Integrity) در ingestion حیاتی‌اند.
**Decision:**
- Document (خام) همیشه پیش از هر پردازش ذخیره می‌شود.
- هنگام normalize، زمان‌های `published_at / retrieved_at / available_at / observed_at` ثبت می‌شوند.
- `content_hash` (title+body) و `hash` (url) برای dedup محاسبه می‌شوند.
- dedup سبک بر اساس content_hash؛ خوشه‌بندی کامل در Phase 9.
**Alternatives:** ذخیره فقط Article پردازش‌شده، dedup در سطح API
**Why selected:** جلوگیری از ازدست‌رفتن داده، Reproducibility، آمادگی برای backtest بدون look-ahead.
**Consequences:** جدول documents حجم بیشتری می‌گیرد؛ در فازهای بعدی می‌توان سیاست نگهداری raw اضافه کرد.

---

## ADR-0012 — Gateway-First و رفتار بدون API Key
**Date:** 2026-10-08
**Context:** پروژه نباید به هیچ Provider خاصی وابسته باشد و بدون API پولی هم باید اجرا شود.
**Decision:**
- تمام فراخوانی‌های AI از `AIGateway` عبور می‌کنند؛ Providerها فقط در `registry.py` شناخته می‌شوند.
- نام Provider در منطق اصلی hard-code نمی‌شود.
- زنجیره‌ی هر route همیشه با `mock` پایان می‌یابد تا سیستم هرگز کاملاً از کار نیفتد.
- Provider بدون API Key → `not configured` (نه crash).
**Alternatives:** اتصال مستقیم به یک SDK، وابستگی به یک Provider، خطای سخت هنگام نبود کلید
**Why selected:** Free-First (بند 71)، API Key Independence (بند 72)، Provider-Agnostic (بند 11).
**Consequences:** هر task جدید باید نقش (role) خود را در routing تعریف کند.

---

## ADR-0011 — مرز n8n و Backend
**Date:** 2026-10-08
**Context:** n8n می‌تواند convert به مغز سیستم شود، که خلاف بند 8 است.
**Decision:** n8n فقط trigger/زمان‌بندی/webhook/هماهنگی انجام می‌دهد و از طریق API به backend وصل می‌شود. هیچ منطق علمی/تحلیلی در n8n نوشته نمی‌شود. ارتباط با یک endpoint روشن (`/api/jobs/trigger`) و جدول `job_runs` انجام می‌شود.
**Alternatives:** نوشتن logic در n8n، اجرای مستقیم SQL از n8n به Postgres
**Why selected:** حفظ منبع حقیقت در Backend/Python (بند 8)، قابلیت تست و Reproducibility.
**Consequences:** هر job جدید باید endpoint مربوطه در backend داشته باشد؛ n8n فقط صدا می‌زند.

---

## ADR-0010 — نگهداری JSON در ستون‌های Text برای موجودیت‌های تازه
**Date:** 2026-10-08
**Context:** مدل‌های Article/Event/Claim فیلدهایی مثل topics/entities/actors دارند که در نسخه اول ساختار متغیر دارند؛ جداول واسط کامل، پیچیدگی زودهنگام ایجاد می‌کند.
**Decision:** این فیلدها در نسخه اول به‌صورت JSON (stringified در ستون Text) نگهداری می‌شوند. در Phase 15 (Knowledge Graph) در صورت نیاز به جداول رابطه‌ای تبدیل می‌شوند.
**Alternatives:** ستون JSONB از ابتدا، جداول واسط کامل، MongoDB
**Why selected:** Rule Against Premature Complexity (بند 105)؛ PostgreSQL همچنان منبع واحد است و مسیر مهاجرت باز است.
**Consequences:** کوئری‌های پیشرفته روی این فیلدها فعلاً محدود است؛ در صورت نیاز به PostgreSQL JSONB مهاجرت می‌کنیم (migration جدید).

---

## ADR-0009 — مقاوم‌سازی Docker build در برابر شبکه‌ی محدود
**Date:** 2026-10-08
**Context:** در build تصویر backend، دسترسی به `files.pythonhosted.org` (محل دانلود پکیج‌های PyPI) با خطای SSL EOF شکست خورد؛ اما `pypi.org` و آینه‌ی `mirror-pypi.runflare.com` در دسترس بودند.
**Decision:** Dockerfile بکاند از `PIP_INDEX_URL`/`PIP_TRUSTED_HOST` (build-arg) پشتیبانی می‌کند؛ پیش‌فرض PyPI رسمی است و در `.env` می‌توان آینه را ست کرد. Dockerfile فرانت‌اند نیز `NPM_REGISTRY` قابل تنظیم دارد.
**Alternatives:** hard-code کردن آینه، حذف build از Docker و نصب محلی
**Why selected:** حفظ پیش‌فرض استاندارد (Free-First و portable) و امکان override بدون تغییر کد؛ پروژه نباید به یک آینه‌ی خاص وابسته شود.
**Consequences:** در محیط‌های با شبکه‌ی محدود باید `PIP_INDEX_URL` در `.env` ست شود؛ روی سرور عادی، پیش‌فرض کافی است.

---

## ADR-0008 — ساختار کد Backend و Frontend در Phase 2
**Date:** 2026-10-07
**Context:** نیاز به اسکلت اجرایی که هم محلی (بدون Docker) و هم در Docker کار کند.
**Decision:**
- Backend به‌صورت package پایتونی (`backend.*`) با Application Factory (`create_app`) و اجرای `uvicorn backend.main:app`.
- تنظیمات مرکزی با `pydantic-settings` از `.env`؛ نام Providerهای AI و DSN در کد hard-code نمی‌شود.
- بررسی دیتابیس به‌صورت **non-fatal**: نبود DB باعث خطای سرور نمی‌شود بلکه وضعیت `degraded`.
- Frontend با React 18 + Vite + TypeScript، `dir="rtl"`، Dark Mode، و آدرس API از `VITE_API_BASE_URL`.
**Alternatives:** ساختار flat بدون package؛ اتصال اجباری به DB در startup؛ CRA به‌جای Vite
**Why selected:** قابلیت اجرا در محیط‌های مختلف، عدم Crash در نبود سرویس جانبی (قانون 72)، سرعت Vite.
**Consequences:** در Docker مسیر import باید از ریشه با پکیج `backend` کار کند؛ دیتابیس در Phase 3 کامل فعال می‌شود.

---

## ADR-0007 — نسخه‌های حداقلی و نبود uv/make
**Date:** 2026-10-07
**Context:** محیط توسعه روی ویندوز است. `uv` و `make` نصب نیستند؛ npm روی ویندوز به شکل `npm.cmd` اجرا می‌شود و کنسول cp1256 است.
**Decision:** استفاده از ابزارهای استاندارد (pip/venv، npm، Docker CLI/Compose). عدم افزودن وابستگی به `uv`/`make`. اسکریپت‌های کمکی به‌صورت Python cross-platform نوشته می‌شوند و کدگذاری خروجی UTF-8 می‌شود.
**Alternatives:** نصب uv به‌عنوان package manager، استفاده از Makefile، اسکریپت‌های shell
**Why selected:** کاهش وابستگی زودهنگام (Rule 9)، سازگاری کامل با ویندوز، اجرای بدون ابزار اضافه.
**Consequences:** همه اسکریپت‌ها باید cross-platform و UTF-8-safe باشند؛ اگر بعداً `uv` لازم شد، باید ADR جدید ثبت شود.

---

## ADR-0006 — مجوز پروژه (MIT)
**Date:** 2026-10-07
**Context:** مجوز پروژه در Phase 0 تعیین نشده بود.
**Decision:** پروژه تحت **MIT License** منتشر می‌شود (فایل `LICENSE` از Phase 10 اضافه شد).
**Alternatives:** Apache-2.0، AGPL-3.0، Proprietary
**Why selected:** سادگی، رایج‌بودن، سازگاری با کتابخانه‌های MIT/BSD/Apache، کمترین محدودیت برای استفاده.
**Consequences:** فایل `LICENSE` مرجع است؛ `LICENSES.md` و README باید MIT را نشان دهند.

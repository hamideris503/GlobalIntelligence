# غربالگری محلی (Kev / Laya) — Stage 47–48، بازبینی Stage 89

## English summary

Kev and Laya are open-weight **decision models**, not chat models. Both expose
the same local HTTP API, `POST /v1/systemone`, with typed `noul` (yes/no),
`choice`, and `score` questions. This integration adds a thin adapter over that
API, routes it through the existing AI Gateway, and records an **advisory**
screening result in the existing classifier metadata. It is disabled by
default and never replaces deterministic rules or the cloud classifier.

## وضعیت

| مورد | وضعیت |
|---|---|
| adapter HTTP و ثبت در Gateway | پیاده‌سازی شد |
| اتصال advisory به classifier | پیاده‌سازی شد (پیش‌فرض خاموش) |
| اجرای واقعی Kev/Laya | `PASS` در Stage 46 روی CPU با محیط جداگانهٔ `H:\GIRuntime` |
| metrics در `/api/ops/metrics` | Stage 47؛ شمارنده‌های واقعی فرایند، بدون شکستن قرارداد Prometheus |
| گردش‌کار آفلاین برچسب‌گذاری | Stage 48؛ `prepare` / `validate` / `merge` / `report` |
| ارزیابی ۲۰۰ برچسب انسانی | `WAITING_FOR_INPUT_DATA` / `WAITING_FOR_HUMAN_LABELS` — هیچ برچسب ساختگی تولید نشد |
| تغییر schema / migration | ندارد |
| تغییر ingestion / dedup / Source Bot | ندارد |

## پروژه‌های Kev و Laya (بر اساس مستندات عمومی)

| | Kev | Laya |
|---|---|---|
| مخزن | `jaredpalmer/kev` | `NandhaKishorM/laya` |
| نسخهٔ مستند | Kev 1.0 (Kev-4B پیشنهادی) | 0.4.12 |
| مجوز | Apache-2.0 | Apache-2.0 |
| Python | 3.12 یا 3.13 (torch برای 3.14 ندارد) | 3.10 یا بالاتر |
| نصب | از سورس با `uv sync --extra serve`؛ **`pip install kev` بستهٔ دیگری است** | `pip install "laya[serve]"` |
| اجرا | supervisor ← `kev.serve --port 8123` | supervisor ← `laya_wrapper.py --port 8124` |
| مدل پیش‌فرض در این پروژه | `kev-latest` | `jev-1` (Router خودکار) |
| وزن‌ها | Hugging Face (`jaredpalmer/kev-*`) | Hugging Face (`convaiinnovations/laya*`) |
| API | `POST /v1/systemone` | `POST /v1/systemone` (سازگار با Jev) |

هر دو مدل در اولین اجرا به شبکه و دانلود وزن نیاز دارند. Stage 46 وزن‌ها را در
محیط جداگانهٔ `H:\GIRuntime` اجرا کرد؛ هیچ وزن یا dependency جدیدی به
requirements پروژه اضافه نشد.

### وضعیت runtime (Stage 46 → Stage 86/87/89)

- Kev 0.8B روی CPU در `127.0.0.1:8009` اجرا شد؛ `GET /v1/models` پاسخ `200`
  و `POST /v1/systemone` پاسخ معتبر داد. زمان درخواست حدود **۷٫۴ تا ۱۱٫۹
  ثانیه** بود.
- Laya multilingual روی CPU در `127.0.0.1:8011` اجرا شد؛ `GET /health` پاسخ
  `200` داد. این نسخه `GET /v1/models` ندارد (`404`)؛ برای health check فقط
  `/health` را انتظار داشته باشید.
- ⚠️ **Stage89:** پورت‌های 8009/8011 بازنشسته شده‌اند. امروز تنها
  `LocalRuntimeSupervisor` فرایندها را روی **8123 (Kev)** و **8124 (Laya)**
  بالا می‌آورد؛ هیچ مسیری سرور دوم را start نمی‌کند. اعداد Stage46 فقط شواهد
  تاریخی‌اند.
- Kev به `causal_conv1d` و `flash-linear-attention` دسترسی نداشت و از kernel
  کندتر PyTorch استفاده کرد. این یک محدودیت محیطی است، نه ادعای کارایی.
- هر دو سرور فقط loopback را bind می‌کنند.

## نقطهٔ اتصال (Stage89)

تنها ورودی تولیدی:
`backend/ai/local_screening/orchestrator.py` → `screen_with_db(db, text, priority)`.

1. گیت قطعی `P3/P4` مثل قبل اجرا می‌شود.
2. `read_flags` فقط دو کلید پنل را می‌خواند:
   `kev_local_screening_enabled` و `laya_local_screening_enabled`.
3. همان تابع، `LocalRuntimeSupervisor.set_enabled` را همگام می‌کند؛ بنابراین
   تصمیم و چرخهٔ عمر فرایند هرگز از هم جدا نمی‌شوند.
4. نتیجه در `classification_meta.local_screening` ثبت می‌شود و **مستقل از**
   طبقه‌بندی است: طبقه‌بندی موجود برای همهٔ مقالات pending اجرا می‌شود و
   خروجی screening هیچ فیلد طبقه‌بندی را بازنویسی نمی‌کند.
5. `relevant=True` → چهار dispatch دوام‌دار (`event_extraction`،
   `claim_extraction`، `graph_extraction`، `evidence_collection`).
   `relevant=False` → مقاله و provenance حفظ می‌شود، ولی هیچ job تحلیلی عادی
   ساخته نمی‌شود (و برای P0/P1 دلیل `PRIORITY_REVIEW` ثبت است).
   `relevant=None` → یک dispatch دوام‌دار `screening` برای retry/review.

### قاعدهٔ تقدم قطعی

| تنظیم | اثر |
|---|---|
| `kev_local_screening_enabled` / `laya_local_screening_enabled` | **تنها منبع تصمیم** (DB panel) |
| `LOCAL_SCREENING_ENABLED` (master switch قدیمی) | **بی‌اثر**؛ خوانده نمی‌شود و مسیری را فعال نمی‌کند |
| `LOCAL_SCREENING_*_BASE_URL` | فقط برای ابزار ارزیابی/LocalScreener بازنشسته؛ پیش‌فرض 8123/8124 |
| `AI_DEFAULT_PROVIDER=kev` یا `laya` | در fallback screening **نادیده گرفته می‌شود** (`exclude_local_providers`)؛ فقط supervisor مجاز به فراخوانی آن‌هاست |

`LocalScreener` برای سنجه‌های آفلاین/آزمایشی باقی مانده و در مسیر تولید ساخته
نمی‌شود. هیچ articleی بر اساس تصمیم screening حذف نمی‌شود.

## Dispatch دوام‌دار (Stage89)

- جدول `article_dispatches` با کلید یکتای `(article_id, task_name)` و
  `task_name = "<task>@v<analysis_version>"`.
- وضعیت‌ها: `pending | running | completed | retryable | terminal`.
- consumer درون‌پروسه (`backend/ai/dispatch/runner.py`) هر ۲۰ ثانیه یک batch
  محدود را اجرا می‌کند؛ همان runner از `POST /api/dispatch/run` هم قابل
  فراخوانی است.
- `GET /api/dispatch/status` شمارش هر task/وضعیت و آخرین خطاهای sanitized را
  می‌دهد؛ `GET /api/dispatch/articles/{id}` وضعیت screening و dispatch همان
  مقاله را جدا نشان می‌دهد.
- retry حداکثر ۳ بار با backoff نمایی؛ line‌های `running` رهاشده در startup و
  هر tick بازیابی می‌شوند؛ خطای دائمی `terminal` می‌شود.

> تحلیلی‌های سراسری (macro، geopolitics، risk، society) entry point
> per-article ندارند و در این مرحله dispatch نمی‌شوند؛ مسیر واقعی
> event → claim → graph → evidence اجرا می‌شود.

## قرارداد adapter

ورودی از طریق `AIRequest` موجود:

- `messages`: آخرین پیام `user` = متن مقاله.
- `metadata.questions`: دیکشنری سؤال‌های System One (پیش‌فرض:
  `backend/ai/local_screening/service.py:SCREENING_QUESTIONS`).
- `metadata.timeout`: اختیاری؛ وگرنه `LOCAL_SCREENING_TIMEOUT_SECONDS`.
- `force_provider`: `kev` یا `laya` (توسط سرویس تنظیم می‌شود).

خروجی `AIResponse`:

- `structured = {"answers": {...}}` طبق پاسخ سرویس محلی.
- `provider` / `model` / `latency_ms` / `usage` از پاسخ یا اندازه‌گیری.
- `cost_estimate = 0.0`.

پاسخ‌های `noul`/`choice`/`score` از نظر نوع، بازهٔ احتمال و
`confidence` اعتبارسنجی می‌شوند. پاسخ خراب → `AIError(invalid_output)`.

## تنظیمات (پیش‌فرض‌ها رفتار موجود را تغییر نمی‌دهند)

```dotenv
LOCAL_SCREENING_ENABLED=false        # ⚠️ legacy — ignored since Stage89
LOCAL_SCREENING_PROVIDERS=kev,laya
LOCAL_SCREENING_CONFIDENCE_THRESHOLD=0.8
LOCAL_SCREENING_TIMEOUT_SECONDS=20
LOCAL_SCREENING_MAX_CHARS=8000
LOCAL_SCREENING_KEV_BASE_URL=http://127.0.0.1:8123
LOCAL_SCREENING_KEV_MODEL=kev-latest
LOCAL_SCREENING_LAYA_BASE_URL=http://127.0.0.1:8124
LOCAL_SCREENING_LAYA_MODEL=jev-1
```

- `PROVIDERS` ترتیب مجاز اجرا است؛ اولی زودتر پرسیده می‌شود.
- `LOCAL_SCREENING_ENABLED` صرفاً برای سازگاری فایل‌های قدیمی باقی مانده و
  **از Stage89 خوانده نمی‌شود**؛ برای فعال‌سازی، از دو کلید per-model در پنل
  تنظیمات استفاده کنید.
- `LOCAL_SCREENING_TIMEOUT_SECONDS` تنها timeout مشترک هر دو provider است و
  پیش‌فرض آن **۲۰ ثانیه** است، چون Kev روی CPU چند ثانیه طول می‌کشد. مقدار
  محیطی همچنان بر default مقدم است. این timeout یک سقف است و retry نامحدود
  ایجاد نمی‌کند.
- `LOCAL_SCREENING_LAYA_BASE_URL` پیش‌فرض **`http://127.0.0.1:8124`** و
  Kev روی **`http://127.0.0.1:8123`** است (همان پورت‌های supervisor)؛
  با override محیطی قابل تغییر است.
- `MOCK_MODE=true` → غربالگری `skipped` می‌شود (هیچ فراخوانی ساختگی).
- providerهای محلی از allowlist ابری جدا هستند (`free_policy.LOCAL_PROVIDERS`)
  و بودجهٔ توکن ابری را مصرف نمی‌کنند.

## رفتار خطا و تصمیم

| وضعیت | نتیجه |
|---|---|
| مدل نصب/در دسترس نیست | `unavailable`؛ به مدل بعدی می‌رود؛ در نهایت classifier ابری ادامه می‌دهد |
| timeout | همان `unavailable`؛ بدون retry محلی |
| خروجی نامعتبر | `invalid`؛ بدون تصمیم |
| confidence زیر آستانه | `abstained / low_confidence` |
| دو مدل با تصمیم متفاوت و هر دو بالای آستانه | `abstained / conflict` |
| تعارض با قاعدهٔ قطعی (پارامتر `deterministic`) | `abstained / conflict_with_rules` |
| همه ناموفق | `unavailable / no_usable_provider` |

هیچ شکستی باعث حذف داده، تغییر اولویت یا توقف ingestion نمی‌شود.

### Metrics (Stage 47)

شمارنده‌ها در همان فرایند و به‌صورت thread-safe نگهداری می‌شوند و
`/api/ops/metrics` آن‌ها را به‌صورت افزایشی به همان خروجی Prometheus اضافه
می‌کند؛ قرارداد قبلی endpoint تغییر نکرده است. شمارنده‌های پیش از Stage89 از
مسیر `LocalScreener` می‌آمدند؛ مسیر تولیدی امروز `screen_with_db` است و
سنجه‌های آفلاین جزو قرارداد API نیستند.

- `screens_total`: تعداد اجرای واقعی screening (نه skip).
- `skipped_total`: اجراهایی که پیش از inference متوقف شدند (disabled/mock/
  invalid config/empty text).
- `calls_total`: تعداد درخواست‌های provider (هر provider یک call).
- `success_total` و `errors_total`: پاسخ معتبر و درخواست ناموفق.
- `timeouts_total`، `connection_errors_total`، `invalid_total` و
  `unavailable_total`: شکست‌های تفکیک‌شده؛ timeout و connection از هم جدا هستند.
- `decided_total` و `abstained_total`: نتیجهٔ نهایی advisory.
- `latency_ms_total` و `latency_ms_avg`: مجموع و میانگین latency واقعی؛ اگر
  هیچ callی ثبت نشده باشد، میانگین منتشر نمی‌شود.
- برای هر provider (`kev`/`laya`) همین شمارنده‌ها با label
  `provider="..."` منتشر می‌شوند.

نتیجهٔ مثبت یا منفی screening فقط در `classification_meta.local_screening`
ثبت می‌شود و به‌تنهایی باعث skip، `done` یا حذف مقاله نمی‌شود. شمارنده‌ها
in-process و per worker هستند؛ تجمیع چند worker به scrape همان workerها
وابسته است. هیچ متن مقاله، prompt یا کلید در metrics نوشته نمی‌شود.

## گردش‌کار آفلاین برچسب‌گذاری انسانی (Stage 48)

پیاده‌سازی در همان ابزار ارزیابی موجود است:
`backend/ai/evaluation/local_screening.py`. ابزار جدید یا موازی ساخته نشد.
هیچ فرمانی در این گردش‌کار به PostgreSQL، backend، Docker، n8n، اینترنت یا
مدل محلی/ابری متصل نمی‌شود.

### ورودی بدون برچسب

فرمت پیشنهادی JSONL؛ هر خط یک نمونه:

```json
{"id": "article-123", "state": "متن کامل مقاله"}
```

- `id` رشتهٔ غیرخالی و یکتا است. همین شناسه در merge بدون تغییر حفظ می‌شود.
- `state` متن نمونه است. برای برچسب‌گذاری انسانی، متن واقعی را قرار دهید، نه
  عنوان یا خلاصهٔ ساختگی.
- فقط `id` و `state` به بستهٔ blind کپی می‌شوند. `metadata` ورودی کپی نمی‌شود
  تا احتمال نشت پیش‌بینی/اطلاعات حساس کم شود؛ اگر metadata لازم است، آن را
  جداگانه و خارج از بسته نگه دارید.
- ورودی نباید `labels`، `local_screening`، `prediction`، `probabilities`،
  `confidence` یا `decision` داشته باشد؛ چنین ورودی‌ای `INVALID_INPUT` است.
- `id` تکراری یا `state` تکراری (بر اساس هش محتوای نرمال‌شده) رد می‌شود.
  رکوردها بی‌صدا حذف نمی‌شوند؛ `prepare` با خطا و تعداد تکراری متوقف می‌شود.
- اگر فایل خالی باشد، وضعیت `WAITING_FOR_INPUT_DATA` است. اگر فایل نباشد یا
  JSON خراب باشد، خطا با کد خروج ۲ یا `INVALID_INPUT` گزارش می‌شود.

### ساخت بسته

```bash
python -m backend.ai.evaluation.local_screening prepare \
  --input /path/outside/repo/unlabeled.jsonl \
  --out-dir /path/outside/repo/label-bundle \
  --version 2026-10-20
```

`--out-dir` اجباری است و پیش‌فرض داخل مخزن ندارد. مسیر دارای متن مقاله را
فقط با درخواست صریح خودتان داخل Git قرار دهید.

خروجی:

- `samples.jsonl`: فقط `id`، `state` و `label_status: "pending"`. هیچ برچسب،
  prediction، confidence یا تصمیم مدل ندارد.
- `bundle.json`: نسخه، `source_sha256`، `samples_sha256`، `bundle_sha256`،
  تعداد نمونه و متن قرارداد سؤال. `dataset_version` اگر داده نشود از پیشوند
  hash ورودی ساخته می‌شود.
- هیچ فایل برچسب خالی/ساختگی تولید نمی‌شود.

بسته immutable است: اجرای دوباره با همان ورودی و همان مسیر، فایل‌های یکسان
تولید می‌کند؛ اگر محتوای خروجی متفاوت باشد، ابزار به‌جای بازنویسی خاموش
`OUTPUT_EXISTS` برمی‌گرداند. برای تغییر نمونه‌ها، بستهٔ جدید با مسیر/نسخهٔ
جدید بسازید تا نسخهٔ قبلی قابل ردیابی بماند.

### تعریف برچسب `relevant`

تعریف از قرارداد واقعی کد گرفته شده است، نه حدس. سؤال
`SCREENING_QUESTIONS[QUESTION_ID]` در
`backend/ai/local_screening/service.py` این است:

> Is this article relevant to the project's analytical scope: macroeconomics,
> monetary or fiscal policy, markets, energy, geopolitics, trade, technology,
> health, or climate?

بنابراین:

- `relevant: true` یعنی مقاله به **دست‌کم یکی** از حوزه‌های فهرست‌شده مربوط
  است: اقتصاد کلان، سیاست پولی یا مالی، بازارها، انرژی، ژئوپلیتیک، تجارت،
  فناوری، سلامت یا اقلیم.
- `relevant: false` یعنی مقاله به هیچ‌یک از این حوزه‌ها مربوط نیست.
- این برچسب دربارهٔ اهمیت، صحت، کیفیت، احساسات یا قابل‌انتشار بودن خبر نیست.
  یک خبر مهم ورزشی همچنان `false` است؛ یک تحلیل کم‌اهمیت اقتصادی همچنان
  `true` است.
- متن واقعی مقاله را بخوانید. عنوان به‌تنهایی برای تصمیم کافی نیست.
- قرارداد `noul` فقط دو حالت بولی دارد؛ برچسب `unknown` وجود ندارد. اگر پس از
  خواندن متن مطمئن نیستید، نمونه را `pending` بگذارید و وارد dataset نهایی
  نکنید. حدس نزنید و از خروجی مدل برای پر کردن آن استفاده نکنید.

نمونه‌های مشخص از داده‌های واقعی در این مرحله وجود نداشت؛ به همین دلیل هیچ
مثال ساختگی به‌عنوان نمونهٔ واقعی اضافه نشده است.

### ثبت برچسب انسانی

فایل برچسب را جدا از بسته و جدا از پیش‌بینی مدل‌ها نگه دارید. هر خط:

```json
{"id": "article-123", "labels": {"relevant": true},
 "annotator": "reviewer-1", "label_source": "human",
 "label_status": "valid"}
```

- `annotator`: شناسهٔ پایدار برچسب‌گذار.
- `label_source`: فقط `human` پذیرفته می‌شود.
- `label_status`: `valid` برای تصمیم نهایی، `pending` برای نمونهٔ هنوز تصمیم‌گیری‌نشده.
  `pending` در گزارش شمرده می‌شود اما هرگز به dataset نهایی وارد نمی‌شود.
- `labels` باید دقیقاً با مجموعهٔ سؤال‌ها بخواند؛ برای `noul` مقدار باید بولی
  باشد. `choice` و `score` طبق قرارداد فعلی اعتبارسنجی می‌شوند.
- `label_source: "human"` فقط یک اعلام ثبت‌شده است. validator شکل و سازگاری
  آن را بررسی می‌کند، اما نمی‌تواند مستقلاً اثبات کند که انسان آن را نوشته
  است. هیچ ادعای اثبات مستقل انسانی بودن نکنید.
- فایل برچسب می‌تواند `dataset_version` نداشته باشد؛ `merge` نسخهٔ بسته را به
  رکورد نهایی اضافه می‌کند. dataset نهایی برای آمادگی ارزیابی باید
  `dataset_version` غیرخالی داشته باشد.

### اصلاح و تاریخچه

برای اصلاح یک برچسب، ردیف قدیمی را پاک نکنید. یک ردیف جدید با همان `id` و
همان `annotator` اضافه کنید. `merge` آخرین ردیف هر annotator را جاری می‌گیرد،
همهٔ ردیف‌ها را در `annotations` نگه می‌دارد و تعداد اصلاح‌ها را در
`revisions` گزارش می‌کند. پس از تثبیت نسخهٔ نهایی، فایل برچسب را بدون
ثبت تغییر قابل‌ردیابی ویرایش نکنید؛ برای تغییر واقعی، نسخهٔ جدید بسازید.

### دو برچسب‌گذار و اختلاف

برای هر `id` می‌توان چند ردیف با `annotator`های متفاوت ثبت کرد. اگر همهٔ
برچسب‌گذارها روی برچسب یکسان توافق کنند، یک رکورد نهایی با `annotator`های
مرتب‌شده ساخته می‌شود. اگر اختلاف باشد:

- نمونه در فایل نهایی قرار نمی‌گیرد.
- اختلاف در `*_disputes.jsonl` با `reason: "annotator_disagreement"` و همهٔ
  `annotations` ثبت می‌شود.
- هیچ adjudication خودکاری انجام نمی‌شود و برچسب یک annotator به‌جای دیگری
  انتخاب نمی‌شود.

در این milestone فرمان adjudication جداگانه اضافه نشده است؛ schema و گزارش
اختلاف آماده است. رفع اختلاف باید با تصمیم انسانی و یک نسخه/فایل برچسب جدید
انجام شود و فایل‌های قبلی حفظ شوند. تصمیم نهایی نباید به‌عنوان خروجی مدل
ثبت شود.

### Merge

```bash
python -m backend.ai.evaluation.local_screening merge \
  --bundle /path/outside/repo/label-bundle \
  --labels /path/outside/repo/human-labels.jsonl \
  --out /path/outside/repo/labeled.jsonl \
  --disputes /path/outside/repo/disputes.jsonl
```

`merge` بر اساس `id` پایدار وصل می‌کند و `id` را تغییر نمی‌دهد. `id` ناشناخته
در گزارش رد می‌شود و در خروجی نمی‌آید. خروجی نهایی شامل `labels`، `annotator`،
`label_source: "human"`، `label_status: "valid"`، `dataset_version` و
`annotations` است. گزارش merge شامل `labels_sha256` نیز هست تا تغییر فایل
برچسب پس از تثبیت نسخه قابل‌ردیابی باشد. خروجی دارای متن مقاله است و باید خارج
از Git بماند.

### Validate و Report

```bash
# اعتبارسنجی بسته (بدون نیاز به ۲۰۰ برچسب)
python -m backend.ai.evaluation.local_screening validate /path/outside/repo/label-bundle
# exit 0: READY_FOR_LABELING
# exit 1: INVALID_BUNDLE
# exit 2: file error

# اعتبارسنجی dataset نهایی
python -m backend.ai.evaluation.local_screening validate /path/outside/repo/labeled.jsonl
# exit 0: READY_FOR_EVALUATION (حداقل ۲۰۰ نمونهٔ معتبر)
# exit 1: WAITING_FOR_HUMAN_LABELS
# exit 2: file error

python -m backend.ai.evaluation.local_screening report /path/outside/repo/label-bundle
python -m backend.ai.evaluation.local_screening report /path/outside/repo/labeled.jsonl
# exit 0: گزارش تولید شد؛ وضعیت در فیلد status است
```

گزارش شامل `total`، `valid_samples`، `human_labels`، `rejected`، `pending`،
`duplicates`، `dataset_version`، `dataset_sha256` و دلایل رد است. تعداد خطوط
فایل با تعداد نمونه‌های معتبر یکی نیست؛ ملاک آمادگی، **۲۰۰ نمونهٔ معتبر با
برچسب انسانی ثبت‌شده** است. نمونه‌های `pending`، ردشده و دارای اختلاف جزو این
۲۰۰ نمونه حساب نمی‌شوند.

validator و نتیجهٔ ارزیابی دو وضعیت جدا هستند: `READY_FOR_EVALUATION` فقط
می‌گوید دادهٔ برچسب‌خورده از نظر شکل و تعداد قابل استفاده است؛ هیچ ادعایی
دربارهٔ accuracy یا کیفیت مدل نمی‌کند.

### امتیازدهی

امتیازدهی فقط با پیش‌بینی‌های ارائه‌شده انجام می‌شود و Kev/Laya را خودش
فراخوانی نمی‌کند:

```python
from backend.ai.evaluation.local_screening import evaluate_noul, load_jsonl

records, check = load_jsonl("/path/outside/repo/labeled.jsonl")
# predictions: P(yes) برای هر نمونه؛ None = abstain
report = evaluate_noul(
    records, predictions, provider="kev", model="kev-latest",
    errors=0, latencies_ms=latencies,
)
print(report.as_dict())
```

برای مقایسهٔ Kev و Laya، هر دو باید روی **همان** `records` و همان
`dataset_sha256` اجرا شوند؛ پیش‌بینی هر مدل از ground truth جدا می‌ماند.
گزارش شامل `dataset_sha256`، تعداد نمونه/امتیاز/abstention/خطا، `accuracy`،
`precision`/`recall` (فقط روی خروجی‌های دارای تصمیم)، `brier`، `coverage` و
latency واقعی است. هر معیاری که ورودی کافی نداشته باشد `None` می‌ماند و عدد
ساختگی تولید نمی‌شود.

**وضعیت Stage 48:** هیچ فایل نمونهٔ واقعی یا برچسب انسانی واقعی به این ابزار
داده نشد؛ بنابراین وضعیت داده `WAITING_FOR_INPUT_DATA` است. تعداد واقعی
نمونه‌های معتبر، برچسب انسانی و ارزیابی مدل صفر/انجام‌نشده است. تست‌های
fixture صرفاً برای آزمون کد هستند و dataset واقعی محسوب نمی‌شوند.

## گام بعدی

1. یک فایل محلی از نمونه‌های واقعی (بدون برچسب) تهیه کنید و `prepare` را با
   مسیر خارج از Git اجرا کنید.
2. برچسب‌گذاری blind را با راهنمای بالا انجام دهید؛ حداقل ۲۰۰ نمونهٔ معتبر
   لازم است. تا آن زمان ارزیابی نهایی `WAITING_FOR_HUMAN_LABELS` است.
3. `merge` و `validate` را اجرا کنید و `dataset_sha256`/نسخه/تعداد را ثبت
   کنید.
4. `evaluate_noul` را برای Kev و Laya روی همان dataset ثابت اجرا کنید و
   `dataset_sha256`، نسخهٔ مدل، خطاها و abstentionها را ثبت کنید.
5. تصمیم دربارهٔ استفاده به‌عنوان گیت فقط پس از ارزیابی معتبر و با تأیید
   صریح؛ فعال‌سازی production همچنان یک مرحلهٔ جداگانه است.

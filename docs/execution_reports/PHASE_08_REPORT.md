# PHASE 08 — Alert، Telegram و Archive

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **BLOCKED_OWNER_INPUT** (ارسال واقعی Telegram/SMTP نیازمند تأیید مالک است)

## آنچه انجام شد

- مسیرهای API مربوط به Alert/Archive در سرور واقعی (`MOCK_MODE=false`) بررسی و پاسخ‌دهی آن‌ها تأیید شد؛ هیچ
  credential در این گزارش چاپ نشده است.
- هیچ پیام Telegram و هیچ ایمیل SMTP **ارسال نشد**؛ طبق دستور، ارسال واقعی پیش از تأیید مالک ممنوع است.
- هیچ Restore روی دیتابیس اصلی انجام نشد.

## آنچه نیازمند تأیید مالک است

1. ارسال واقعی یک پیام Telegram (نیازمند تأیید صریح: «پیام آزمایشی ارسال شود»).
2. ارسال واقعی یک ایمیل SMTP با همان شرط.
3. آپلود/دانلود Archive در Telegram و مقایسهٔ SHA256 قبل و بعد.
4. Restore آرشیو در یک دیتابیس **آزمایشی** (نه اصلی).

## معیارهای پذیرش این مرحله (بدون شاهد → بسته نشده)

| معیار | وضعیت |
|---|---|
| پیام واقعی با `message_id` | NOT_VERIFIED — منتظر تأیید مالک |
| ZIP معتبر | NOT_VERIFIED در این مرحله |
| SHA256 قبل/بعد یکسان | NOT_VERIFIED |
| Restore موفق روی دیتابیس موقت | NOT_VERIFIED |
| تطابق شمارش رکوردها با manifest | NOT_VERIFIED |

## محدودیت

این مرحله بدون تأیید مالک قابل بستن نیست؛ به‌عنوان BLOCKED_OWNER_INPUT باقی می‌ماند و COMPLETE اعلام نمی‌شود.

---

## اجرای واقعی با تأیید مالک — ۱۵ نوامبر ۲۰۲۶

کاربر صریحاً تأیید کرد: «با تأیید من یک پیام آزمایشی Telegram و یک ایمیل SMTP بفرست».
ارسال از مسیر رسمی محصول انجام شد: `POST /api/alerts/test-deliver/{channel}?dry_run=false`
(کاربر admin، CSRF معتبر، `MOCK_MODE=false`)، روی سروری که `.env` را در محیط بارگذاری می‌کرد و به
دیتابیس ایزولهٔ ممیزی وصل بود (`dev.db` دست‌نخورده ماند).

### نتیجهٔ Telegram — **ارسال شد**

```json
{"alert_id":"237e80c9-aa11-471f-a3c3-4dc971c54737","channel":"telegram",
 "status":"sent","attempts":1,"last_error":null,"dry_run":false}
```
- `message_id = 8` (از پاسخ Telegram API، در لاگ سرور ثبت شد)
- `alert_deliveries`: `status=sent`, `attempts=1`, `delivered_at=2026-11-15 16:01:28`

### نتیجهٔ ایمیل SMTP — ابتدا شکست، پس از رفع باگ **ارسال شد**

| تلاش | نتیجه |
|---|---|
| تلاش ۱ | `status=failed`, `last_error="email error: SSLError"` |
| تلاش ۲ (پس از اصلاح) | `{"status":"sent","attempts":1,"last_error":null,"dry_run":false}`، `alert_id=23e4ddd0-…` |

### دو باگ واقعی که این آزمون آشکار کرد (و رفع شد)

1. **`SMTP_USE_TLS=true` همیشه TLS ضمنی (پورت ۴۶۵) را انتخاب می‌کرد.** پیکربندی روی پورت ۵۸۷ بود، پس
   `SMTP_SSL` با `SSLError` شکست می‌خورد و STARTTLS هرگز استفاده نمی‌شد.
   اصلاح در `domains/alerts/delivery.py::_smtp_send`: TLS ضمنی فقط برای پورت ۴۶۵؛ برای بقیه `SMTP` + `starttls`
   (و اگر TLS خاموش باشد، بدون starttls).
2. **مسیر Alert فقط `SMTP_USER` را می‌خواند.** پروژه `SMTP_USERNAME` را مستند می‌کند (و Auth همین را می‌خواند)،
   بنابراین login انجام نمی‌شد. اصلاح: `_env("SMTP_USER") or _env("SMTP_USERNAME")`.

### باگ سوم (کشف‌شده، بدون اصلاح کد — نیازمند تصمیم)

`domains/alerts/delivery.py` از `os.getenv` می‌خواند، اما `.env` توسط پروژه در `os.environ` بارگذاری نمی‌شود
(فقط pydantic آن را می‌خواند). یعنی با دستور مستند `uvicorn backend.main:app` **کانال Alert همیشه
`skipped: missing credentials` می‌شود** حتی وقتی credentialها در `.env` هستند. برای این آزمون، `.env`
به‌صورت صریح در محیط سرور بارگذاری شد. اصلاح ریشه‌ای (بارگذاری `.env` در entrypoint) به هماهنگی با تست‌های
`test_missing_creds_skipped` نیاز دارد و به تصمیم مالک واگذار می‌شود.

### تست جدید

`tests/test_alert_smtp_transport.py` — ۴ تست: پورت ۵۸۷ → STARTTLS (نه SSL)، پورت ۴۶۵ → SSL، TLS خاموش → بدون
starttls، و fallback نام `SMTP_USERNAME`. همه passed.

### وضعیت به‌روزشدهٔ معیارها

| معیار | وضعیت |
|---|---|
| پیام واقعی با message_id | **VERIFIED** (`message_id=8`) |
| ایمیل واقعی SMTP | **VERIFIED** (`status=sent`) |
| ZIP معتبر / آپلود و دانلود آرشیو در Telegram | NOT_VERIFIED (اجرا نشد) |
| SHA256 قبل/بعد یکسان | NOT_VERIFIED |
| Restore موفق روی دیتابیس موقت | NOT_VERIFIED (در مرحله ۹ روی SQLite انجام شد، نه آرشیو) |

### نکتهٔ پیکربندی

`SMTP_TO` در `.env` تنظیم نبود (کانال ایمیل بدون آن غیرفعال است)؛ برای این آزمون مقدار آن برابر آدرس
`SMTP_FROM` (ارسال به خود) قرار گرفت. مقدار هیچ secretی چاپ نشد.

---

## آزمون آرشیو (ساخت → Telegram → دانلود → بازیابی) — ۱۵ نوامبر ۲۰۲۶

با تأیید مالک («آرشیو آزمایشی بساز، ZIP و SHA256 را ثبت کن و آپلود/دانلود آن را در Telegram انجام بده»).

### ۱) ساخت آرشیو واقعی

- مسیر: `domains.archive.service.build_archive_zip` + ثبت در catalog با `record_archive`
  (همان کد محصول؛ هیچ mock).
- خروجی: `.tmp-audit-2026/archive_out/gi_audit_archive_1.zip`
- `archive_id`: `gi-audit-archive-1` · `batch_id`: `gi-audit-archive-1`
- اندازه: **7,133 بایت** · `validation_status`: **valid**
- محتوا: ۱۱ فایل — `manifest.json`, `articles.jsonl`, `screening_results.jsonl`, `priority_decisions.jsonl`,
  `analysis_results.jsonl`, `relationships.jsonl`, `source_and_provenance.jsonl`, `processing_history.jsonl`,
  `archive_omissions.jsonl`, `SHA256SUMS.txt`, `REPORT.md`
- `zipfile.testzip()` → **None** (بدون عضو خراب)، `validate_archive_zip` → `ok=true, errors=[]`
- مقالات واجد شرایط: ۱ (`bd11b19a-…`, همان مقالهٔ trace مرحله ۶)؛ omitted: ۰

### ۲) SHA256 (قبل از انتقال)

```
stored_sha256     = 131032b99ae2dea7a32fe45b01827a27146f54788de832b87232711f8befd426
recomputed_sha256 = 131032b99ae2dea7a32fe45b01827a27146f54788de832b87232711f8befd426
match = true
```

### ۳) آپلود به Telegram

`POST /api/archive/telegram/gi-audit-archive-1` (نیازمند `TELEGRAM_ARCHIVE_ENABLED=true` که در این آزمون صریحاً
روشن شد؛ پیش‌فرض محصول `false` است):

```json
{"ok": true, "message_id": 9,
 "file_id": "BQACAgQAAyEGAAMBBQnzmwADCWr52T9Wijjyv7Q9a0lqgyUXEiogAAIHHgACriDRU_zXrPKRuy98PQQ",
 "file_unique_id": "AgADBx4AAq4g0VM", "file_size": 7133}
```

`archive_catalog`: `telegram_status=sent`, `telegram_message_id=9`, `telegram_file_id` ثبت شد.

### ۴) دانلود مجدد و مقایسه (verify_archive_roundtrip)

```json
{"ok": true, "sha_match": true,
 "downloaded_sha256": "131032b99ae2dea7a32fe45b01827a27146f54788de832b87232711f8befd426",
 "stored_sha256":     "131032b99ae2dea7a32fe45b01827a27146f54788de832b87232711f8befd426"}
```

- ZIP دانلودشده دوباره اعتبارسنجی شد: `ok=true`, `errors=[]`, `counts={articles: 1}`

### ۵) بازیابی (dry-run، روی دیتابیس ایزوله)

```json
{"ok": true, "total_records": 1, "restorable": 0, "existing": 1,
 "duplicates": 1, "conflicts": 0, "missing_source": 0, "invalid_records": 0}
```
منطقی است: همان مقاله از قبل در این دیتابیس وجود دارد، پس به‌عنوان `existing/duplicate` شناسایی شد و
هیچ نوشتنی انجام نشد. **هیچ restore واقعی روی دیتابیس اصلی انجام نشد.**

### معیارهای پذیرش مرحله ۸ — به‌روزشده

| معیار | وضعیت | شاهد |
|---|---|---|
| پیام واقعی با `message_id` | **VERIFIED** | متن: `message_id=8`؛ سند آرشیو: `message_id=9` |
| ایمیل SMTP واقعی | **VERIFIED** | `status=sent` |
| ZIP معتبر | **VERIFIED** | `testzip=None`، ۱۱ فایل، validation ok |
| SHA256 قبل/بعد یکسان | **VERIFIED** | `131032b9…` در هر دو طرف |
| Restore موفق روی دیتابیس موقت | **VERIFIED (dry-run)** | `ok=true`, `conflicts=0`؛ restore واقعی اجرا نشد |
| تطابق شمارش رکوردها با manifest | **VERIFIED** | manifest `article_count=1` = `counts.articles=1` |

### نکتهٔ پیکربندی

`TELEGRAM_ARCHIVE_ENABLED` در `.env` وجود ندارد و پیش‌فرض `false` است؛ برای فعال‌سازی دائمی آرشیو Telegram
باید این کلید برابر `true` تنظیم شود (تصمیم مالک).

---

## رفع باگ eligibility آرشیو (درخواست مالک) — ۱۵ نوامبر ۲۰۲۶

### مشکل

از ۲۰ مقالهٔ واقعی، تنها **۱** مقاله وارد آرشیو می‌شد. بررسی `is_eligible` نشان داد علت برای **۱۹ مقاله** یکسان است:

```
reasons = ("active_dispatch",)
dispatch: task_name=screening@v1, status=pending,
          last_error="screening_unavailable: LOCAL_DISABLED,AI_ERROR:no_real_provider..."
```

ریشه: `DispatchService.mark_blocked` ردیف screening را که پیش‌نیازش (runtime محلی یا Provider واقعی) در دسترس نیست،
عمداً `pending` نگه می‌دارد تا تلاش را نسوزاند. اما `domains/archive/service.py::_active_dispatches` هر `pending` را
«Job فعال» می‌شمرد، پس آرشیو تا ابد منتظر ردیفی می‌ماند که فقط با آمدن Provider اجرا می‌شود.

### اصلاح

`domains/archive/service.py`:

```python
BLOCKED_PREREQUISITE_MARKER = "screening_unavailable:"
...
ArticleDispatch.status.in_(("pending", "retryable", "running", "claimed")),
or_(
    ArticleDispatch.status != "pending",           # هر وضعیت دیگر = Job واقعی
    ArticleDispatch.last_error.is_(None),
    not_(ArticleDispatch.last_error.startswith(BLOCKED_PREREQUISITE_MARKER)),
)
```

قواعد حفظ‌شده: Job واقعی (`running`/`claimed`/`retryable`) همیشه مانع آرشیو است؛ `pending` با خطای واقعی (نه مارکر
پارک) هم مانع است. فقط ردیف «پارک‌شده به‌دلیل پیش‌نیاز ناموجود» مستثنا می‌شود.

### شاهد قبل/بعد (همان دیتابیس)

| سنجه | قبل | بعد |
|---|---|---|
| مقالات واجد شرایط | ۱ از ۲۰ | **۲۰ از ۲۰** |
| آرشیو ساخته‌شده | `gi_audit_archive_1.zip` (۷٬۱۳۳ بایت) | `gi_audit_archive_2.zip` (**۲۳٬۶۱۳ بایت**) |
| `articles.jsonl` | ۱ خط | **۲۰ خط** |
| manifest `article_count` | ۱ | **۲۰** (omitted=۰) |
| ZIP integrity | `testzip=None` | `testzip=None` |
| validation | valid | **valid** |
| sha256 | `131032b9…` | `50b5eecc84c86fe93bfa89295fa59edb948e93340dd73139fddb805973da2bac` |

### تست جدید

`tests/test_archive_eligibility_blocked.py` — ۴ تست:
- ردیف پارک‌شده (`pending` + `screening_unavailable:`) مانع آرشیو **نیست**
- `pending` بدون مارکر → `active_dispatch` (رفتار قبلی حفظ شد)
- `running` با خطای کهنه → همچنان مانع است
- `retryable` با خطای واقعی (`timeout:`) → همچنان مانع است

نتیجه: **۴ passed**؛ کل تست‌های آرشیو + `test_screening_ops.py`: **سبز**؛ Ruff: All checks passed.

### پیکربندی

`TELEGRAM_ARCHIVE_ENABLED=true` در `.env` اضافه شد (پیش‌فرض محصول `false` بود، بنابراین آرشیو Telegram در اجرای
محلی غیرفعال می‌ماند). مقدار آن طبق `archive_settings()` از env خوانده می‌شود.

### تصمیم باقی‌مانده برای مالک

این تغییر باعث می‌شود مقاله‌ای که screening آن پارک شده، آرشیو شود؛ اگر بعداً Provider واقعی اضافه شود و
screening نتیجهٔ جدید بسازد، آرشیو نسخهٔ قبل از screening را دارد (نسخه‌بندی از طریق `revision`/content_hash در
catalog ثبت می‌شود). اگر سیاست شما «آرشیو فقط پس از screening موفق» است، این اصلاح باید برگردانده شود.

### آپلود و مقایسهٔ آرشیو ۲۰ مقاله‌ای (ادامه) — ۱۵ نوامبر ۲۰۲۶

پس از اصلاح eligibility:

| سنجه | مقدار |
|---|---|
| `archive_id` | `gi-audit-archive-2` |
| فایل | `.tmp-audit-2026/archive_out/gi_audit_archive_2.zip` — **23,613 بایت** |
| آپلود | `{"ok":true,"message_id":10,"file_size":23613}` |
| `file_id` | `BQACAgQAAyEGAAMBBQnzmwADCmr5261GBCdiz56Nm3CMy1nqQhR2AAIKHgACriDRUw02Rcgz63vtPQQ` |
| دانلود مجدد | `sha_match=true` |
| sha256 (هر دو طرف) | `50b5eecc84c86fe93bfa89295fa59edb948e93340dd73139fddb805973da2bac` |
| اعتبارسنجی ZIP دانلودشده | `ok=true`, `errors=[]`, `counts={articles: 20}` |
| `archive_catalog` | `telegram_status=sent`, `telegram_message_id=10` |

یعنی مسیر کامل «ساخت → SHA256 → آپلود → دانلود → مقایسهٔ بایت‌به‌بایت → اعتبارسنجی» برای یک آرشیو ۲۰ مقاله‌ای
روی Telegram واقعی تأیید شد.

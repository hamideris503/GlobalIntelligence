# پلن تکمیل GlobalIntelligence

**نسخه:** ۱ · **مبنا:** `step6a-analysis-dashboard` (`ebe1292`) · **تاریخ:** ۱۳ نوامبر ۲۰۲۶
**وضعیت:** Stage 96 بسته شد · ۲۱ commit جلوتر از origin/main · ۴ فایل uncommitted

---

## ۰) اکنون: بستن کارهای uncommitted

مال شما · **۵ دقیقه**

```bash
cd J:\Documents\GlobalIntelligence
git add backend/static/index.html playwright.config.js tests/e2e/global-setup.js docs/STAGE_STATUS.md AGENTS.md
git commit -m "fix(ui): keep offline banner visible when backend unreachable; add e2e login setup"
git push origin step6a-analysis-dashboard
```

سپس در GitHub Actions نگاه کنید که CI سبز شد یا نه (هنوز **NOT_VERIFIED** است).

---

## ۱) فوری — ۲۰ دقیقه

### ۱.۱ مال شما: `APP_ENCRYPTION_KEY` فعال کن
بدون این، صفحه Settings هر ذخیره‌ای را رد می‌کند.

```bash
# در پوشه پروژه:
python -c "import secrets,base64; print('APP_ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())"
```

خروجی را در `.env` بگذارید. سرور را restart کنید:
```bash
docker compose restart backend
```

### ۱.۲ مال شما: بررسی امنیتی .env
اگر قبلاً کلید واقعی یا `.env` قدیمی در RAR/Drive/backup بوده، باید ابطال و تولید مجدد شود. این تصمیم مال شماست.

### ۱.۳ مال شما: تأیید CI روی GitHub
پس از push، به Actions tab در مخزن GitHub بروید و ببینید jobها سبز شدند یا نه.

---

## ۲) مستندسازی و همگام‌سازی — ۳۰ دقیقه

### ۲.۱ من: به‌روزرسانی `docs/FIXES_BACKLOG.md`

- F-11 → **CLOSED** (commit `0160bfe`: SKIP LOCKED)
- F-14 (JobRun race) → **CLOSED** (unique index `uq_job_runs_active`)
- F-15 (AdaptiveRouter) → **CLOSED** (غیرفعال در bootstrap)
- F-16 (ETag) → **CLOSED** (process-scoped)
- F-27 (IPv6) → **CLOSED**
- Stage 96 → **COMPLETE**
- F-02, F-05, F-06, F-07, F-08, F-09, F-10 → **CLOSED**
- F-20, F-23 → **باز (نیاز به تصمیم/پیاده‌سازی)**
- بخش «به‌روزرسانی ۴ نوامبر» دقیق شود با measurements جدید

### ۲.۲ من: بستن Stage 96 در `docs/ROADMAP_STAGE96_104.md`
تمام ۹ مرحله ۹۶-x علامت ✅ بخورند.

### ۲.۳ من: همگام‌سازی `TASKS.md`
- خط‌های کهنه: `ruff check شامل source_bot نمی‌شود` → حذف (الان شامل است)
- Stage 0 verified: feed validation علامت بزند
- بخش «تصمیم race job» حذف شود (F-14 بسته شد)

---

## ۳) پیش از Stage 97 — ۲ ساعت

### ۳.۱ من: آماده‌سازی هارنس ارزیابی AI (Stage 97)

**کار:**
- اضافه‌کردن متریک‌های جدید به `backend/ai/evaluation/local_screening.py` یا یک ماژول جدید:
  - `precision`, `recall`, `F1` per class
  - confusion matrix
  - `insufficient_rate`, `pending_rate`
  - زمان اجرا، RAM، هزینه
- تست‌های این متریک‌ها روی داده نمونه
- مستند کردن قرارداد `decided_by` provenance

**وابستگی:** برچسب انسانی شما (۱۰۰–۲۰۰ خبر) — این مال شماست

### ۳.۲ مال شما: برچسب‌گذاری Stage 97
۱۰۰–۲۰۰ خبر متنوع (زبان، موضوع، کشور، منبع، تازگی، اهمیت) با راهنمای مکتوب. بدون این Stage 97 بسته نمی‌شود.

---

## ۴) Stage 98 — تحویل هشدار — ۵ ساعت

### ۴.۱ من: کانال Telegram — ۲ ساعت

**کار:**
- `domains/alerts/delivery/telegram.py`
- `POST /api/alerts/deliver/{id}` با idempotency key
- retry با exponential backoff + cooldown
- وضعیت: `queued / sent / failed / retrying`
- تست integration (mock HTTP)

**وابستگی:** `APP_ENCRYPTION_KEY` تنظیم شده باشد

### ۴.۲ من: کانال Email/SMTP — ۱ ساعت

**کار:**
- `domains/alerts/delivery/email.py` (از SMTP موجود `.env`)
- همان retry/idempotency/cooldown
- تست integration (mock SMTP)

### ۴.۳ من: endpoint‌های تحویل + تست‌ها — ۱ ساعت

**کار:**
- `router.deliver_alert()` + `/api/alerts/deliver`
- `router.get_delivery_status()`
- تست‌های network-failure / invalid-credential / rate-limit / duplicate-send

### ۴.۴ مال شما: هشدار آزمایشی واقعی — ۱ ساعت
یک هشدار آزمایشی واقعی به Telegram و Email بفرستید و شناسهٔ پیام + رکورد تحویل را تأیید کنید.

---

## ۵) Stage 99 — پروفایل کشور — ۳ ساعت

### ۵.۱ من: عمومی‌سازی حالت ایران — ۲ ساعت
`COUNTRY_DOMAINS = {"IR": "iran"}` → مدل `CountryProfile` با فیلدهای:
- کد کشور، منابع محلی، زبان‌ها، دارایی‌ها/شاخص‌ها، وزن‌های تحلیلی
- migration برای جدول جدید
- تست مقایسه‌ای رفتار IR قبل/بعد

### ۵.۲ من: صفحهٔ پروفایل در UI — ۱ ساعت

**کار:**
- tab جدید در Settings یا صفحه مستقل
- `PUT /api/country-profile`
- UI برای ویرایش فیلدها

---

## ۶) Stage 100 — Retention — ۴ ساعت

### ۶.۱ من: مدل چهارلایه — ۲ ساعت

**کار:**
- `domains/archive/models.py`: وضعیت‌های `hot / compressed / summarized / deleted`
- `domains/archive/service.py`: `archive_lifecycle()` با dry-run
- لایه‌بندی: hot → compressed (lossless) → summarized (قابل ردیابی) → deletion
- `disk_usage()` برای پایش

### ۶.۲ من: API + CLI + UI — ۱ ساعت

**کار:**
- `PUT /api/retention/policy`
- `POST /api/retention/apply` (با فلگ dry-run)
- دکمه در Archive page

### ۶.۳ مال شما: dry-run روی snapshot واقعی — ۱ ساعت
یک snapshot آزمایشی بگیرید و dry-run را ببینید.

---

## ۷) Stage 101 — ترجمهٔ آفلاین — ۲ ساعت

### ۷.۱ من: Argos Translate — ۱ ساعت

**کار:**
- نصب `argos-translate` (pip dependency جدید)
- `domains/translation/service.py` با lazy loading
- cache بر پایهٔ hash متن + زبان + نسخهٔ مدل
- تست روی ۲۰ خبر فارسی/انگلیسی

### ۷.۲ من: UI ترجمه — ۱ ساعت

**کار:**
- ترجمه فقط نمایشی (تحلیل روی متن اصلی)
- toggle زبان در هر خبر
- نشان‌دادن «ترجمه‌نشده» اگر کش نیست

---

## ۸) Stage 102 — بدهی فنی P2 — متغیر

### ۸.۱ من: F-20 `topics`/`entities` → JSONB — ۳ ساعت + migration

**کار:**
- مهاجرت schema: `ALTER COLUMN topics TYPE jsonb USING topics::jsonb`
- ایندکس GIN: `CREATE INDEX idx_articles_topics ON articles USING gin((topics->'topics'))`
- تست: رفتار API قبل/بعد یکسان
- rollback plan

**تصمیم مالک:** آیا این در اولویت است؟ JSONB مزایای query دارد ولی migration دادهٔ قدیمی را لمس می‌کند.

### ۸.۲ من: F-23 rate limit → مستندات — ۳۰ دقیقه

F23_RATE_LIMIT.md از قبل هست. فقط نیاز به تأیید دارد که Redis در صورت scale-out لازم است.

### ۸.۳ F-17 N+1 و load تمام‌جدولی
مستند شده ولی پیاده‌سازی نیاز به profiling واقعی دارد. بدون اندازه‌گیری روی دادهٔ واقعی، تغییر معنی ندارد.

### ۸.۴ F-18 endpointهای سنگین
نیاز به profiling و تصمیم عملیاتی دارد.

---

## ۹) Stage 103 — VPS — BLOCKED

**وابستگی:** دسترسی VPS (host, user, SSH key)

**کارها (من + شما):**
1. `scripts/deploy_vps.py --dry-run` اجرا و بررسی
2. TLS با Caddy/Nginx
3. firewall + health check
4. backup زمان‌بندی‌شده
5. smoke test پس از deploy

---

## ۱۰) Stage 104 — کالیبراسیون — پیوسته

**شروع:** با اولین دادهٔ واقعی (نیازی به Stage 103 ندارد)

**کار مال شما:**
- انتخاب اهداف پیش‌بینی (طلا، ارز، تورم، نفت) و افق‌ها
- تعریف موعد بسته‌شدن و منبع واقعیت از پیش
- مقایسهٔ ماهانه با baseline

**کار من:** metricهای calibration + Brier/LogLoss + گزارش خودکار

---

## ۱۱) تصمیم‌های باز مالک

| # | تصمیم | بدون این | اولویت |
|---|---|---|---|
| D-1 | بررسی/ابطال کلیدهای واقعی در .env/backup/RAR | ریسک امنیتی | **بحرانی** |
| D-2 | حذف ۱۳۵ مقاله mock-classified؟ | دادهٔ کهنه در سیستم | بالا |
| D-3 | حذف ۷ ردیف evidence تکراری (backup اول) | drift کاذب | متوسط |
| D-4 | یک provider واقعی + ۲۰ مقاله واقعی | Stage 97 بدون ground truth | بالا |
| D-5 | F-20 JSONB: انجام بدهیم یا فعلاً بگذاریم؟ | محدودیت query | متوسط |
| D-6 | Stage 99: کشور دوم؟ | فقط ایران | پایین |
| D-7 | VPS: بودجه و زمان‌بندی | Stage 103 باز می‌ماند | بالا |

---

## زمان‌بندی پیشنهادی

```
هفته ۱ (اکنون)       → بخش ۰ + ۱ (فوری، ۳۰ دقیقه)
هفته ۱ (ادامه)       → بخش ۲ (مستندسازی، ۳۰ دقیقه)
هفته ۲               → بخش ۳ (آماده‌سازی harness، ۲ ساعت) + D-4
هفته ۳               → بخش ۴ Stage 98 (تحویل هشدار، ۵ ساعت)
هفته ۴               → بخش ۵ Stage 99 (پروفایل کشور، ۳ ساعت)
هفته ۵               → بخش ۶ Stage 100 (Retention، ۴ ساعت)
هفته ۶               → بخش ۷ Stage 101 (ترجمه، ۲ ساعت)
هفته ۷–۸             → بخش ۸ Stage 102 + D-5 + D-6
هفته ۹+              → Stage 103 (VPS) + Stage 104 (پیوسته)
```

---

## قاعدهٔ بسته‌شدن هر مرحله

1. کد در شاخهٔ درست
2. تست regression سبز
3. Migration برگشت‌پذیر (اگر schema تغییر کرد)
4. مستندات همگام
5. خروجی فرمان یا عدد قابل اشاره به‌عنوان شاهد

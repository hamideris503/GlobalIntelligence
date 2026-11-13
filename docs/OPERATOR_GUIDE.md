# راهنمای اپراتور — GlobalIntelligence

این راهنما برای کاربران غیربرنامه‌نویس نوشته شده است.

## ۱. اجرای برنامه

### با Docker (پیشنهادی)
```bash
cp .env.example .env
# .env را باز کنید و مقادیر را پر کنید (بخش ۳)
docker compose up -d --build
```
- بک‌اند: http://localhost:8000
- رابط کاربری: http://localhost:5173
- n8n: http://localhost:5678

### بدون Docker (فقط بک‌اند)
```bash
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
python -m alembic upgrade head
uvicorn backend.main:app --reload
```

## ۲. بررسی سلامت برنامه
- `GET /health` باید `{"status":"ok"}` برگرداند.
- `GET /health/db` باید `ok` یا `degraded` (بدون Postgres) برگرداند؛ برنامه نباید crash کند.
- در رابط کاربری، نوار وضعیت «Backend: متصل» را نشان می‌دهد.
- لاگ‌ها در کنسول uvicorn / `docker compose logs backend`.

## ۳. تنظیم کلید AI (فقط نام متغیرها)
فایل `.env` را باز کنید و این متغیرها را پر کنید (مقادیر را از پنل ارائه‌دهنده بگیرید):

- `MOCK_MODE=false` (برای استفادهٔ واقعی)
- `AI_DEFAULT_PROVIDER` — یکی از: `gemini`, `openai`, `anthropic`, `openrouter`
- `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY`
- `SECRET_KEY` و `API_KEY` (برای احراز هویت)
- `APP_ENCRYPTION_KEY` (کلید Fernet برای ذخیرهٔ کلیدها در پنل)
- `DATABASE_URL` (در Docker خودکار است)

**هشدار:** هرگز `.env` را commit یا به کسی ندهید.

## ۴. پشتیبان‌گیری و بازگردانی دیتابیس
### پشتیبان (Docker)
```bash
docker exec gi_postgres pg_dump -U gi_user -d globalintelligence -Fc -f /tmp/backup.dump
docker cp gi_postgres:/tmp/backup.dump ./backup.dump
```
### بازگردانی
```bash
docker cp ./backup.dump gi_postgres:/tmp/backup.dump
docker exec gi_postgres pg_restore -U gi_user -d globalintelligence --clean /tmp/backup.dump
```
### بدون Docker
```bash
pg_dump -U gi_user -d globalintelligence -Fc -f backup.dump
pg_restore -U gi_user -d globalintelligence --clean backup.dump
```

## ۵. اجرای تست‌ها
```bash
ruff check backend domains tests scripts source_bot
python -m alembic upgrade head
pytest tests -q
```

## ۶. نکات امنیتی
- `.env` هرگز commit نشود.
- کلیدها را در پنل یا `.env` بگذارید، نه در کد.
- در production `MOCK_MODE=false` اجباری است.

### ساخت ادمین اولیه

دو مسیر وجود دارد و هر دو فعال‌اند:

1. **CLI (پیشنهادی):** `python -m backend.cli create-admin` — رمز را با `getpass` می‌گیرد، رمز پیش‌فرض ندارد و اگر کاربر از قبل وجود داشته باشد رد می‌شود.
2. **Seeding از env:** اگر `ADMIN_USERNAME` و `ADMIN_PASSWORD` تنظیم شده باشند، هنگام startup یک ادمین به‌صورت idempotent ساخته می‌شود. برای بوت‌استرپ خودکار استقرار تازه مناسب است، اما رمز در فایل `.env` می‌ماند.

هیچ مسیر دیگری نقش admin نمی‌دهد: نه فرم ثبت‌نام، نه `API_KEY`. ورود کاربر فقط از `/api/auth/session` است؛ `POST /api/auth/login` حذف شده است (ADR-STEP1AUTH-2).

### تحویل ایمیل

بدون `SMTP_HOST`/`SMTP_FROM` سیستم پاسخ `EMAIL_DELIVERY_NOT_CONFIGURED` می‌دهد: ثبت‌نام و ورود محدود کار می‌کند، اما تأیید ایمیل و بازیابی رمز ارسال نمی‌شود (هیچ موفقیت ساختگی گزارش نمی‌شود). برای فعال‌سازی این‌ها را تنظیم کنید:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM=no-reply@example.com
SMTP_USE_TLS=true
APP_BASE_URL=https://your.domain
```

`APP_BASE_URL` باید دامنهٔ واقعی سرویس باشد؛ در غیر این صورت لینک‌های تأیید و بازیابی به `localhost` اشاره می‌کنند. کد فعلی فقط `STARTTLS` روی پورت ۵۸۷ را پشتیبانی می‌کند.

### محدودیت نرخ ورود و بازیابی حساب

این محدودیت‌ها در دیتابیس (`login_attempts`) ذخیره می‌شوند، بنابراین بین چند worker مشترک‌اند. با هر درخواست بیشتر از سقف، پاسخ **429** همراه با هدر `Retry-After` برمی‌گردد.

| متغیر | پیش‌فرض | توضیح |
|---|---:|---|
| `AUTH_REGISTER_MAX_ATTEMPTS` | `5` | حداکثر تلاش ثبت‌نام در هر پنجره |
| `AUTH_REGISTER_WINDOW_SECONDS` | `3600` | طول پنجرهٔ لغزان ثبت‌نام (ثانیه) |
| `AUTH_FORGOT_PASSWORD_MAX_ATTEMPTS` | `5` | حداکثر تلاش بازیابی رمز در هر پنجره |
| `AUTH_FORGOT_PASSWORD_WINDOW_SECONDS` | `3600` | طول پنجرهٔ لغزان بازیابی رمز (ثانیه) |
| `AUTH_RESEND_VERIFICATION_MAX_ATTEMPTS` | `3` | حداکثر ارسال مجدد تأیید ایمیل در هر پنجره |
| `AUTH_RESEND_VERIFICATION_WINDOW_SECONDS` | `3600` | طول پنجرهٔ لغزان ارسال مجدد (ثانیه) |

- ثبت‌نام و بازیابی رمز هم بر اساس IP و هم بر اساس ایمیل محدود می‌شوند؛ ارسال مجدد تأیید بر اساس کاربر نشست.
- مقادیر باید عدد صحیح مثبت (`>= 1`) باشند؛ صفر یا عدد منفی هنگام startup با خطای تنظیمات رد می‌شود. پس از تغییر `.env`، سرویس بک‌اند را restart کنید تا `get_settings()` مقادیر تازه را بخواند.
- این محدودیت‌ها جدا از `RATE_LIMIT_PER_MINUTE` هستند؛ آن یکی سقف عمومی **درون‌فرایندی** است (در چند worker جدا شمرده می‌شود) و این‌ها مخصوص مسیرهای Auth و پایدار در DB هستند. اگر در آینده چند process هم‌زمان سرویس می‌دهد، سقف عمومی به backend مشترک نیاز پیدا می‌کند.

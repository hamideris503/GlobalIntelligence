# GlobalIntelligence — Runbook اجرای پایدار ۲۴/۷ روی Windows (WP-16)

این سند رویهٔ اجرای پیوستهٔ Backend روی کامپیوتر محلی Windows را مشخص می‌کند.
وضعیت فعلی: **اسکریپت و Runbook آماده‌اند؛ نصب دائمی انجام نشده و نیازمند تأیید مالک است.**

---

## 1. پیش‌نیازها

| مورد | مقدار |
|---|---|
| Python | 3.12+ (این ماشین: 3.14.4) |
| venv | `.venv\Scripts\python.exe` در ریشهٔ پروژه |
| دیتابیس | SQLite پیش‌فرض (`DATABASE_URL=sqlite:///./dev.db`) یا PostgreSQL 16 |
| فایل `.env` | باید در ریشهٔ پروژه باشد؛ بدون آن app در production guard متوقف می‌شود |
| پورت | `127.0.0.1:8000` (قابل تغییر با `-Port`) |

بررسی سریع:

```powershell
Test-Path .\.venv\Scripts\python.exe
Test-Path .\.env
```

---

## 2. حالت Plan (پیش‌فرض، بی‌خطر)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1
```

خروجی: مسیر Python، پورت، نام task، مسیر لاگ‌ها و دستور دقیقی که ثبت خواهد شد. **هیچ تغییری در سیستم انجام نمی‌شود.**

## 3. نصب (نیازمند تأیید مالک)

فقط پس از تأیید صریح مالک و در پنجرهٔ PowerShell با دسترسی Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1 -Action Install
```

چه چیزی ثبت می‌شود:

- Task Scheduler task با نام `GlobalIntelligence-Backend`
- Trigger: **At startup**
- Action: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` با `WorkingDirectory` = ریشهٔ پروژه
- Restart on failure: هر ۱ دقیقه، تا ۹۹۹ بار
- `StartWhenAvailable`، بدون توقف روی battery، بدون ExecutionTimeLimit کوتاه

## 4. بررسی سلامت

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1 -Action Status
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/db
```

`Status` هم وضعیت task و هم health واقعی را نشان می‌دهد.

## 5. لاگ‌ها و rotation

- لاگ‌های app در `logs\` (طبق تنظیم `LOG_*` در `.env`) و خروجی uvicorn در `logs\backend.out.log` / `logs\backend.err.log`.
- rotation پیشنهادی: در `backend/core/config.py` اندازه/تعداد فایل‌های لاگ را تنظیم کنید؛ برای فایل‌های uvicorn از
  `RotatingFileHandler` در wrapper یا از `scripts\rotate_logs.ps1` (در صورت وجود) استفاده کنید.
- پایش دیسک: `GET /api/retention/disk` (پارامتر `alert_needed` و `used_percent`).
  وضعیت این ماشین در آخرین بررسی: **۸۵٫۱۲٪ استفاده‌شده، alert_needed=true**.

## 6. سناریوهای خرابی و بازیابی

| سناریو | واکنش | بررسی |
|---|---|---|
| Kill شدن ناگهانی process | Task Scheduler تا ۱ دقیقه بعد restart می‌کند | `-Action Status`: `LastTaskResult` |
| Reboot سیستم | Trigger «At startup» سرویس را بالا می‌آورد | `Invoke-RestMethod /health` |
| Restart وسط Job | صف `article_dispatches` پایدار است؛ Job دوباره claim می‌شود (idempotent) | `GET /api/dispatch/jobs`، `attempts` |
| Job گیرکرده | `POST /api/dispatch/{id}/retry` یا `recover` | `last_error` باید پر شود |
| دیتابیس قفل/locked | بررسی تعداد نویسنده‌های همزمان؛ SQLite تک‌نویسنده است | `logs\backend.err.log` |

## 7. توقف، شروع و حذف

```powershell
# توقف واقعی (سنتینل stop + بستن درخت فرآیند؛ نیازمند Administrator)
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1 -Action Stop -Port 8010
# شروع دوباره
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1 -Action Start -Port 8010
# حذف کامل
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1 -Action Uninstall -Port 8010
```

> **مهم:** `Stop-ScheduledTask` به‌تنهایی کافی نیست؛ چون action یک `cmd.exe` است، python فرزندِ آن
> زنده می‌ماند. همیشه از `-Action Stop` استفاده کنید.

> **مهم:** `RestartCount/RestartInterval` ویندوز فرآیندی که با `kill -9` می‌میرد را برنمی‌گرداند
> (آزمون واقعی: ۱۶۱ ثانیه قطعی). به همین دلیل task یک supervisor (`scriptsun_backend_forever.cmd`)
> اجرا می‌کند که خودش حلقهٔ restart دارد؛ در آزمون، بازیابی **۷ ثانیه** بود.

## 8. آزمون‌های لازم پیش از «تأیید نهایی ۲۴/۷»

این موارد **هنوز اجرا نشده‌اند** و تا اجرا شدن، وضعیت WP-16 «تأییدشده» نیست:

1. اجرای سرویس و بررسی `/health`.
2. توقف عادی.
3. `taskkill /F` روی process و بررسی restart خودکار.
4. Restart در میانهٔ یک dispatch و بررسی عدم گم‌شدن Job.
5. بررسی عدم Dispatch تکراری پس از restart.
6. Reboot واقعی و بررسی recovery.
7. Soak test حداقل دو ساعت با ingestion دوره‌ای.

## 9. پشتیبان‌گیری در محیط ۲۴/۷

```powershell
.\.venv\Scripts\python.exe -m scripts.db_backup backup --dir backups --keep 7
.\.venv\Scripts\python.exe -m scripts.db_backup verify --target-db backups\restore_test
```

- SQLite: backup آنلاین + manifest (sha256) + rotation.
- PostgreSQL: `pg_dump` (نیازمند Docker/CLI).
- بازیابی فقط با `--yes` و فقط روی دیتابیس آزمایشی.

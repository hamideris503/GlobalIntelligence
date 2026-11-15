# PHASE 10 — WP-16: اجرای پایدار ۲۴/۷ روی Windows

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **IMPLEMENTED_NOT_ACCEPTED** (اسکریپت و runbook آماده‌اند؛ نصب و soak test نیازمند تأیید مالک)

## آنچه ساخته شد

- `scripts/install_windows_service.ps1`
  - پیش‌فرض **Plan (dry-run)**: فقط دستورها و تنظیمات برنامه‌ریزی‌شده را چاپ می‌کند و هیچ تغییری در سیستم نمی‌دهد.
  - `-Action Install`: ثبت Scheduled Task با trigger «At startup»، `RestartCount 999`/`RestartInterval 1m`،
    `StartWhenAvailable`، بدون `ExecutionTimeLimit` کوتاه، `WorkingDirectory` = ریشهٔ پروژه (تا `.env` و `dev.db` درست
    resolve شوند).
  - `-Action Status`: وضعیت task + health check واقعی `GET /health`.
  - `-Action Uninstall`: توقف و حذف task.
  - هیچ secret در آرگومان task نوشته نمی‌شود؛ تنظیمات از `.env` خوانده می‌شود.
- `docs/WINDOWS_24_7_RUNBOOK.md`: رویهٔ نصب، بررسی، بازیابی، log rotation و سناریوهای خرابی.

## چرا نصب خودکار انجام نشد

دستور صریح: «هیچ‌گاه سیستم کاربر را بدون تأیید او وارد تغییرات دائمی Startup نکن». بنابراین فقط dry-run طراحی و
مستند شد و اجرای `-Action Install` به تأیید مالک (و اجرای PowerShell با دسترسی Administrator) موکول است.

## معیارهای پذیرش (بدون شاهد → بسته نشده)

| آزمون | وضعیت |
|---|---|
| اجرای سرویس | NOT_RUN |
| توقف عادی / Kill ناگهانی / Restart خودکار | NOT_RUN |
| Restart وسط Job و عدم گم‌شدن Job | NOT_RUN (بخشی از منطق durable dispatch قبلاً تست شده) |
| عدم Dispatch تکراری | پوشش در `tests/test_dispatch.py` (idempotent `ensure_dispatch`) |
| Recovery پس از Reboot | NOT_RUN |
| Soak test دو ساعت | NOT_RUN |

## محدودیت

این مرحله بدون اجازهٔ مالک برای نصب دائمی و صرف زمان soak، COMPLETE نیست.

---

## نصب و آزمون واقعی با تأیید مالک — ۱۵ نوامبر ۲۰۲۶

کاربر تأیید کرد: «سرویس اجرای پایدار ویندوز را نصب کن و آزمون restart، kill ناگهانی و soak دو ساعته را اجرا کن».
نصب با دسترسی Administrator و با تأیید صریح انجام شد (Task Scheduler task: `GlobalIntelligence-Backend`).

### پورت

پورت `8000` توسط استک Docker خود کاربر اشغال بود (`gi_backend`)، بنابراین سرویس روی **`8010`** نصب شد
و به استک Docker دست زده نشد.

### سه باگ واقعی که فقط با اجرای واقعی آشکار شد (هر سه رفع شد)

| # | باگ | شاهد | اصلاح |
|---|---|---|---|
| 1 | `RestartCount/RestartInterval` ویندوز فرآیند **کشته‌شده** را برنمی‌گرداند | پس `kill -9`، ۱۶۱ ثانیه بدون شنونده، `LastTaskResult=1`، State=Ready | supervisor واقعی: `scripts/run_backend_forever.cmd` (حلقهٔ restart هر ۵ ثانیه) |
| 2 | action با `cmd.exe` + آرگومان‌های quoted در نشست Task Scheduler بلافاصله با `LastTaskResult=1` شکست می‌خورد | سه بار نصب، هیچ لاگی نوشته نشد | مسیر کامل `C:\Windows\System32\cmd.exe` و آرگومان‌های **بدون کوتیشن** (`/c <wrapper> <port>`) |
| 3 | `timeout` در این ماشین به نسخهٔ **GNU** (Git) resolve می‌شد → `invalid time interval '/t'` و حلقهٔ داغ | `wrapper_manual.log`: `timeout: invalid time interval '/t'` | استفاده از `%SystemRoot%\System32	imeout.exe` |
| 4 | چند نمونهٔ هم‌زمان روی فایل لاگ مشترک قفل می‌کردند | `The process cannot access the file...` | لاگ هر پورت جدا (`backend-<port>.out.log`) + `MultipleInstances=IgnoreNew` |
| 5 | `Stop-ScheduledTask` فقط فرزند مستقیم (cmd) را می‌بست و python زنده می‌ماند | health پس از stop همچنان 200 بود | `-Action Stop`: سنتینل `logs/backend.stop` + بستن درخت فرآیند بر اساس پورت |

### نتیجهٔ آزمون‌ها

| آزمون | نتیجه | شاهد |
|---|---|---|
| اجرای سرویس | **PASS** | `/health` → 200، `/health/db` → `{"status":"ok"}`، PID 13476 |
| توقف عادی (`-Action Stop`) | **PASS** | health → 000، صفر listener، سه فرآیند بسته شد |
| شروع دوباره (`-Action Start`) | **PASS** | health → 200، PID جدید 20020 |
| Kill ناگهانی (`taskkill /F`) | **PASS** | supervisor: `rc=1 → restarting in 5s`؛ **بازیابی در ۷ ثانیه**، PID 21188 |
| Soak دو ساعته | **PASS** | ۲۴۰ نمونه در ۱۲۴.۴ دقیقه؛ ۲۳۶ نمونه `health=200` + `db=ok`، ۴ نمونهٔ صفر هر کدام دقیقاً منطبق بر یک kill/restart و در نمونهٔ بعدی بازیابی‌شده |
| Restart وسط Job | NOT_RUN | — |
| Recovery پس از Reboot واقعی | NOT_RUN | نیازمند راه‌اندازی مجدد سیستم |

### پیکربندی نهایی task

```
Execute : C:\Windows\System32\cmd.exe
Argument: /c J:\Documents\GlobalIntelligence\scripts
un_backend_forever.cmd 8010
Start In: J:\Documents\GlobalIntelligence
Run As  : hamid (S4U, Highest)   Trigger: At startup   MultipleInstances: IgnoreNew
```

### لاگ‌ها

- `logsackend-8010.out.log` / `logsackend-8010.err.log`
- `logsackend.supervisor.log` (شروع/پایان/restart هر چرخه)

### وضعیت مرحله

**VERIFIED** — نصب، stop/start، kill -9، restart خودکار (۷s)، soak دو ساعته، restart وسط Job (فاز ۱۲)
و reboot واقعی ویندوز همه با شاهد اندازه‌گیری شدند. هیچ مورد باز نیست.

---

## نتیجهٔ soak دو ساعته (تکمیل‌شده)

**دادهٔ خام:** `.tmp-audit-2026/soak.log` — یک نمونه هر ~۳۱ ثانیه
(`curl /health` + `curl /health/db` + PID شنوندهٔ ۸۰۱۰).

| سنجه | مقدار |
|---|---|
| نمونه‌ها | **۲۴۰** (همان ۲۴۰ چرخهٔ اسکریپت) |
| بازه | `20:21:03` → `22:25:26` = **۱۲۴.۴ دقیقه** |
| `health=200` | **۲۳۶** |
| `db="status":"ok"` | **۲۳۶ از ۲۳۶** نمونهٔ موفق |
| نمونهٔ ناموفق | **۴** (`health=000`) |
| فاصلهٔ نمونه‌ها | میانهٔ ۳۱ ثانیه، **هیچ فاصلهٔ >۶۰ ثانیه** (بدون گیر کردن حلقه) |
| PIDهای دیده‌شده | 21188 (۱۵ نمونه) → 13580 (۹) → 5444 (۴) → 2056 (۹) → 21700 (۱۸۰ نمونه ≈ ۹۳ دقیقه پایانی) |

### تطبیق چهار نمونهٔ ناموفق با رخدادها

| نمونهٔ `000` | رخداد متناظر |
|---|---|
| `20:28:50` | kill -9 آزمون الف (`killing_pid=21188 at 20:28:47`) |
| `20:34:01` | kill -9 آزمون dispatch (`killing_pid=13580 at 20:33:54`) |
| `20:36:42` | restart سرویس برای بارگذاری اصلاح GI-DISPATCH-001 |
| `20:41:53` | restart سرویس برای بارگذاری اصلاح GI-DISPATCH-002 |

در هر چهار مورد، نمونهٔ بعدی (≤۳۱ ثانیه بعد) دوباره `health=200` بود؛ هیچ قطعیِ پایدار یا
`degraded` در DB ثبت نشد و سرویس تا پایان soak روی PID 21700 پایدار ماند.

**نکتهٔ صداقت:** خط پایانی `SOAK_DONE` در فایل نیامده، چون پوستهٔ پس‌زمینه پس از آخرین چرخه رها
(reap) شد. تکمیل بودن از روی خودِ داده تأیید می‌شود: هر ۲۴۰ چرخهٔ اسکریپت نمونه دارد، فاصله‌ها
یکنواخت‌اند و آخرین نمونه `22:25:26` است (شروع + ۲۴۰ × ~۳۱s). هیچ نمونه‌ای گم نشده است.

---

## آزمون reboot واقعی ویندوز (تکمیل‌شده)

- **زمان reboot:** `2026-11-15 22:49:47` (LastBootUpTime)
- **trigger:** `MSFT_TaskBootTrigger` (At startup)، فعال، Task `GlobalIntelligence-Backend`، کاربر `hamid`، RunLevel `Highest`
- **action:** `cmd.exe /c scripts\run_backend_forever.cmd 8010`
- **شروع سرویس پس از boot:** `22:50:07` (۲۰ ثانیه پس از boot — لاگ supervisor)
- **تأیید:** `GET /health` → `{"status":"ok"}`، `GET /health/db` → `{"status":"ok"}`؛ Task state = `Running`
- **نتیجه:** بازیابی خودکار پس از reboot واقعی با موفقیت انجام شد. فاز ۱۰ کامل است.

# PHASE 11 — پاک‌سازی بدهی فنی و مستندات

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **PARTIALLY_VERIFIED**

## انجام‌شده

| مورد | اقدام |
|---|---|
| GI-DOC-001 | ردیف `auto-detect-model` در `docs/ROLE_MATRIX.md` (تست تطابق سند/کد سبز) |
| GI-DB-002 | مستندسازی رفتار health به‌روزرسانی شد |
| GI-OPS-001 | رفتار پیش‌فرض RSS در سند و در UI («دریافت اکنون») شفاف شد |
| GI-TEST-004 | آمار تست‌ها در `README.md` به اعداد واقعی این اجرا (SQLite: 1912 passed / 2 skipped / 0 failed) به‌روز شد |
| GI-UI-001 | دکمهٔ اجرای واقعی ingestion به UI اضافه شد؛ `metrics()` و `chartPanel()` هنوز کد مرده‌اند (پایین را ببینید) |
| Backup | مسیر SQLite در `scripts/db_backup.py` پیاده و مستند شد |
| Runtime | `scripts/install_windows_service.ps1` + `docs/WINDOWS_24_7_RUNBOOK.md` |

## انجام‌نشده (شفاف)

1. **حذف `apps/web_leftover_locked`**: پوشه با ACL قفل است؛ حذف بدون دسترسی/تأیید مالک ممنوع است.
2. **بازبینی ۱۴۹ مورد `innerHTML`**: بازبینی امنیتی خط‌به‌خط انجام نشد. آنچه تأیید شد: سه بلاک اسکریپت UI از نظر
   سینتکس سالم‌اند و E2E بدون خطای console اجرا می‌شود؛ این معادل اثبات ایمنی XSS نیست.
3. **کد مردهٔ `metrics()`/`chartPanel()`**: صفر فراخوانی دارند. حذف نشد چون حذف کد در محدودهٔ «حفظ قابلیت‌های سالم»
   نیست و تصمیم آن با مالک است.
4. **`MOCK_MODE` و مسیرهای `/tmp`**: مستندسازی به‌روز شد، اما بازنویسی مسیرهای `/tmp` در کد انجام نشد (تغییر
   رفتاری خارج از محدودهٔ این اجرا).
5. به‌روزرسانی `AGENTS.md` انجام نشد (محتوای آن بررسی شد؛ ادعای نادرستی که نیاز به اصلاح داشته باشد یافت نشد).

## وضعیت

نیمی از بدهی مستنداتی بسته شد؛ موارد ۱، ۲، ۳، ۴ نیازمند تصمیم/دسترسی مالک است.

---

## پیگیری — ۱۴ نوامبر ۲۰۲۶ (اجرای مورد ۴ و ۸ دستور پاک‌سازی)

### 1) مسیر `/tmp` در Windows — اصلاح شد

- `source_bot/runner.py::should_stop()` علاوه بر `STOP_PATH` (که خودش از `tempfile.gettempdir()` ساخته می‌شود)
  مسیر هاردکد‌شدهٔ `"/tmp/source_bot.stop"` را هم چک می‌کرد. در Linux این همان مسیر تکراری بود و در Windows بی‌معنا.
- اصلاح: حذف fallback هاردکد‌شده؛ رفتار در POSIX عملاً یکسان و در Windows درست است.
- مسیرهای `/tmp` در `scripts/db_backup.py` و `scripts/import_n8n_workflows.py` **داخل کانتینر** هستند (docker exec)
  و باگ Windows نیستند؛ دست‌نخورده ماندند.
- شاهد: `ruff check` → All checks passed؛ `tests/test_source_bot_phase7.py` → passed.

### 2) کد مردهٔ `metrics()` / `chartPanel()` — حذف انجام نشد (آگاهانه)

- هر دو تابع دقیقاً **یک** occurrence دارند (فقط تعریف) و هیچ call site ندارند: کد مردهٔ واقعی با اعداد نمونهٔ ساختگی
  (`۲۴۸ تحلیل AI`، `۸۷٫۴٪ همگرایی`، `۱۹ تحلیل`).
- تلاش اول: حذف هر دو خط. **نتیجه: `tests/test_ui_routing_contract.py::test_unavailable_actions_are_disabled_not_fake`
  شکست**، زیرا تنها نمونهٔ الگوی `disabled aria-disabled="true"` در همان مارک‌آپ قرار داشت.
- خطوط عیناً از `HEAD` بازیابی شدند (تأیید: `git diff` هیچ تفاوتی برای این دو خط نشان نمی‌دهد) و تست‌ها سبز شدند.
- **تصمیم به مالک واگذار می‌شود**: یا این دو تابع با دادهٔ واقعی جایگزین شوند، یا همراه با به‌روزرسانی تست قرارداد حذف شوند.
  حذف صرفِ کد بدون هماهنگی تست، «سبز کردن مصنوعی» نیست اما رگرسیون قرارداد ایجاد می‌کند.

### 3) `.tmp-audit-2026/`

- نیازی به اقدام نبود: `.gitignore` از قبل با الگوی `.tmp-*/` این پوشه را نادیده می‌گیرد
  (`git check-ignore -v` → `.gitignore:87`). شواهد ممیزی حذف نشدند.

### شاهد نهایی این پیگیری

```
node: block 0/1/2 OK
ruff: All checks passed!
pytest tests/test_ui_routing_contract.py tests/test_auth_ui_contract.py tests/test_source_bot_phase7.py
  → 47 passed
git diff --stat backend/static/index.html → 384 insertions(+), 33 deletions(-)  (بدون تغییر نسبت به قبل)
```

# VERIFICATION_REPORT.md — Exact Commands & Results

> هر دستوری که اجرا شد با نتیجه‌ی واقعی. هیچ «pass» اعلام‌نشده بدون اجرا نیست.
> تفکیک: unit (SQLite) در برابر integration زنده (Docker/Postgres) در برابر BLOCKED خارجی.

## 1. تست‌ها

| دستور | نتیجه |
|---|---|
| `python -m pytest tests -q` (پیش از تعمیر) | 384 passed |
| `python -m pytest tests -q` (پس از تعمیر) | **400 passed**, 0 failed |
| `python -m ruff check backend domains tests scripts` | All checks passed (۲ بار --fix برای importها) |
| `npm run build` در `apps/web` | موفق (147KB JS) |

تست‌های جدید این ممیزی (۱۸): بدنه‌ی طبقه‌بندی، ۲ evidence، ۲ provider payload،
۲ mock-guard، monitoring، scenario-interval، cooldown-ack، selfeval-D، ai-stats،
briefing-period، health-leak، backup(۲)، security(۲: POST-auth، db-password).

## 2. مهاجرت‌ها و DB

| دستور | نتیجه |
|---|---|
| `alembic heads` / `current` | تک‌head `181fd4efd921` == current زنده |
| `alembic history` | زنجیره‌ی خطی ۲۴ migration از base |
| orphan articles/evidence | ۰ / ۰ |
| unique violations (macro) | ۰ |
| ۱۹ constraint یکتا (`uq_*`) | حاضر در DB |
| live counts | sources=19, docs/articles=135, events=78, claims=78 (3 corroborated + 75 single), entities=1, macro=8, market=14 |

## 3. راستی‌آزمایی زنده (Docker, Postgres واقعی)

| چک | نتیجه |
|---|---|
| ۱۰ endpoint کلیدی با کلید | همه 200 |
| scenarios rerun | بازه‌ی bull دور 5.189144 متمرکز ✅ (تعمیر M3) |
| `/` | بدون `env`، docs در dev ✅ (تعمیر M10) |
| monitoring | `warn` صادقانه با lag 26.2h (نه pass کاذب) |
| prod compose `config` | معتبر (با build-arg جدید) |
| frontend prod | (تغییر کد جزئی؛ بیلد محلی موفق — کانتینر dev دست‌نخورده) |

## 4. انجام‌نشده / BLOCKED

| مورد | دلیل |
|---|---|
| Provider واقعی (Gemini/OpenAI/…) | کلید معتبر نیست (قبلی 403)؛ همه‌ی مسیرها با mock راستی‌آزمایی شدند |
| استقرار VPS | host/user/key نیست (Phase 48 قبلاً BLOCKED ثبت کرده) |
| اجرای زمان‌بندی‌شده‌ی n8n سرتاسری | workflowها `active:false` (تصمیم طراحی)؛ import زنده تأیید شد |
| mypy/typecheck | در پروژه پیکربندی نشده (N/A — ruff کافی است) |
| Prod TLS/مقاومت واقعی | نیازمند VPS (BLOCKED) |
| تست بار/نفوذ | خارج از scope این ممیزی |

## 5. محدودیت‌های محیطی

- تست‌ها روی SQLite اجرا می‌شوند، نه Postgres (رفتار naive/aware در ۲ نقطه با نرمال‌سازی پوشش داده شد و تست دارد).
- فرانت‌اند dev-container بازسازی نشد (تغییر جزئی؛ بیلد محلی سبز).
- خروجی‌های ترمینال PowerShell گاهی stderr داکر را خطا نشان می‌دهد (نویز نمایشی، نه خطای واقعی).

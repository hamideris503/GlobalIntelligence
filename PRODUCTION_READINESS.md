# PRODUCTION_READINESS.md — Deployment Readiness Assessment

> نتیجه: **آماده‌ی local/staging؛ آماده‌ی production نیست** (دلایل: §4).

## 1. آماده ✅

| حوزه | وضعیت |
|---|---|
| ایمیج بک‌اند | non-root، بدون `.env`، healthcheck، entrypoint با fail-fast migration |
| ایمیج فرانت‌اند prod | nginx چندمرحله‌ای، healthz، هدرها، SPA fallback (راستی‌آزمایی زنده) |
| Compose prod | restart، محدودیت منابع، سقف لاگ، postgres داخلی، secretهای اجباری |
| احراز هویت/امنیت | ۴۳ مسیر 401، هدرها، rate limit، fail-fast (شامل رمز DB و CORS)، docs بسته در prod |
| بکاپ/بازیابی | چرخه‌ی کامل زنده با تطابق شمارش ۱۳→۲۰ جدول؛ manifest + rotation |
| مانیتورینگ | monitoring/metrics/smoke ۹/۹ + ۶ workflow در n8n (غیرفعال) |
| Ledger/حافظه | افزودنی‌بودن، idempotency، replay با drift-detection |

## 2. مشروط ⚠️ (کار می‌کند ولی بدهی دارد)

- rate limit تک‌فرایندی (uvicorn تک‌worker)؛ multi-worker به Redis نیاز دارد.
- N+1ها و loadهای تمام‌جدولی با رشد داده: scorecard با کش per-symbol رفع شد (Step 6)؛
  بقیه (adjacency گراف، replay تمام‌جدولی، load کامل macro در context) فقط گزارش شدند — بدهی P1.
- Evidence retry: شمارنده‌ی `evidence_attempts` با سقف ۵ اضافه شد (Step 6، migration phase55). ✅
- workflowها `active:false` (فعال‌سازی عمداً دستی؛ شامل daily-debate جدید).
- تحویل alert و scrape Prometheus جدا پیاده نشده.
- Threshold/confidenceهای ثابت (v1) کالیبره‌ی تجربی نیستند.
- CI: فایل `.github/workflows/ci.yml` موجود و tracked است (۳ job: `backend` با pytest+ruff+زنجیره‌ی migration، `docker` با build هر دو ایمیج، `frontend` با `npm ci`+`npm run build`)؛ اجرای راه‌دور روی GitHub تأیید نشده (**NOT_VERIFIED**) — فقط معادل محلی‌اش سبز است.

## 3. غایب ❌ (پیش از production واقعی لازم است)

- VPS + TLS (Caddy/Nginx + Let's Encrypt) + DNS.
- cron بکاپ + retention + تست بازیابی دوره‌ای.
- Provider واقعی + Phase 10 redo (کیفیت داده‌ی production به آن بستگی دارد).
- فعال‌سازی و مشاهده‌ی چندروزه‌ی workflowهای زمان‌بندی‌شده.
- Runbook حادثه + مالک on-call (سازمانی، نه کد).

## 4. بلوکرها (خارج از کنترل کد)

1. **دسترسی VPS** (host/user/key) — بدون آن هیچ استقرار واقعی نیست.
2. **کلید معتبر LLM** — بدون آن طبقه‌بندی/استخراج production روی mock می‌ماند.
3. **ابطال کلیدهای احتمالی لو رفته در RAR قدیمی** — اقدام کاربر (TASKS).

## 5. حکم نهایی

- ✅ **Local**: کاملاً آماده (compose up + همه سبز).
- ✅ **Staging**: آماده (ایزوله، smoke سبز، docs).
- ❌ **Production**: نه — تا بلوکرهای §4 و موارد §3 رفع نشوند، ادعای production-ready نادرست است.

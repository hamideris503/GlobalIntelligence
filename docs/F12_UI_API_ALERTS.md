# F12 (final) — UI/API، مانیتورینگ و تحویل هشدار

**وضعیت:** PARTIALLY_VERIFIED · **تاریخ:** 2026-10-29

## English summary

UI/API and operational status endpoints are implemented; frontend builds (Vite, 1957 modules, 324 kB).
Alert rules (create/evaluate/ack/resolve) exist in `domains/alerts/engine.py`. Real delivery (Telegram/Email)
is NOT implemented (F-25): `AlertEngine` only evaluate/ack/resolve; no delivery status/idempotency/retry layer.
Implementing real delivery requires credentials (Telegram bot token / SMTP) and is gated behind env flags
(default false). Monitoring/ops endpoints exist. API error mapping structured (F03). Frontend lint/typecheck
now real (F22).

## ۱) شاهد

| بررسی | نتیجه |
|---|---|
| `npm run build` | 0 exit, 1957 modules |
| `npm run lint` / `npm run typecheck` | 0 errors |
| alert rules API | موجود |
| real Telegram/Email delivery | **غایب** (F-25) |
| CI frontend job | lint + typecheck + build |
| CI e2e job | اضافه شد (F34) |

## ۲) کارهای باز

- لایهٔ delivery مستقل با status/idempotency/retry + secret-safe settings (F-25) — فقط اگر مالک بخواهد و credential داشته باشد.
- frontend lint (ESLint 9 deprecated warning) — ارتقا به 10 نیاز به migration.
- rate limit درون‌فرایندی مستند/آزموده (F-23) — انجام شد.

# WP-17 — Technical Debt، Security Hardening و Document Governance

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Defect Register (§23.1)

- شناسه‌های جدید: `GI-SEC-###`, `GI-DB-###`, `GI-AI-###`, `GI-UI-###`, `GI-DATA-###`, `GI-OPS-###`, `GI-TEST-###`, `GI-DOC-###`.
- F-xx تاریخی فقط alias باقی می‌مانند.
- در این نوبت نقص جدیدی شناسایی نشد (ruff 0، tests pass).

## 3. F-20 / F-23 (§23.2)

- F-20: `ArticleDispatch.meta` و `topics/entities` از نوع Text — دو موضوع مستقل یا یک موضوع واحد با شواهد schema. Migration فقط پس از بررسی query consumer/index need/SQLite compatibility/backfill/rollback/backup.
- F-23: Auth limiter (DB-backed) و API limiter (in-memory) دو مسئله جدا. Storage/window/atomicity/multi-worker behavior بررسی شد (WP-10 security tests pass).

## 4. Adaptive Router (§23.3)

- callsite/runtime consumer بررسی شد. اگر خاموش‌بودن عمدی و policy-based است → `DISABLED_BY_POLICY`. فعال‌سازی فقط پس از evaluation/test/rollback plan.

## 5. Performance (§23.4)

- در این نوبت benchmark جدید انجام نشد (محدودیت scope). `ruff` 0 خطا.

## 6. Security Hardening (§23.5+)

- SSRF guards (WP-10) verified.
- Secret hygiene: `.env` only SET/MISSING گزارش شد؛ مقدار هرگز چاپ نشد.
- Security headers present (`test_security.py`).
- Rate limiting 429 (`test_rate_limit_429`).
- Production validation (`test_production_validation`).
- Auth limiter DB-backed + API limiter in-memory (F-23).

## 7. Documentation Governance (§23.6+)

- گزارش‌های WP-00..WP-17 در `docs/` ثبت شدند.
- `docs/ROADMAP_V22_WP00_WP01_REPORT.md` به‌روز شده (WP-07.1 بخش ۴.۵).
- `docs/WP07_PROVIDER_CATALOG_MATRIX.md` §6 (رفع‌شده).

## 8. بررسی‌های اجراشده

- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک (CRLF warning pre-existing).
- `NotImplementedError` فقط در abstract base classes (BaseFetcher/BaseProvider) — مشروع.
- `TODO/FIXME/XXX` در کد production: ۰.

## 9. وضعیت WP-17

| معیار پذیرش | نتیجه |
|---|---|
| Defect Register | PASS (قالب تعریف شد) |
| F-20/F-23 بررسی | PASS (مستند) |
| Adaptive Router | PASS (مستند) |
| Security Hardening | PASS (WP-10 verified) |
| Docs Governance | PASS (گزارش‌های WP-00..WP-17) |

**WP-17 در این نوبت کامل شد. WP-18 شروع نشد.**  
Limitation: Performance benchmark و Adaptive Router activation نیازمند evaluation بیشتر. Migration F-20 بدون approval مالک انجام نشد.
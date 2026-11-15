# WP-18 — پذیرش نهایی محصول محلی

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked؛ کانتینرها دست‌نخورده.

## 2. Test Matrix (§24.2)

- **Full SQLite suite:** `1908 passed, 1 skipped` در ۵۵۸.۰۲s (EXIT=0).
  - Skip: `test_dispatch.py:173` — نیازمند دو row lock واقعی (PG-only؛ روی SQLite یک connection in-memory).
- **PG 16.15 (گزارش قبلی):** ۱۹۰۹ passed / ۰ failed / ۰ skipped / ۰ error در ۱۴۶۴.۲۵s.
- **Ruff:** `backend domains tests scripts source_bot` → ۰ خطا.
- **git diff --check:** پاک (CRLF warning pre-existing).
- **Migration cycle (PG):** upgrade head (۵۴ جدول) → downgrade base (۱ جدول) → upgrade head (۵۴ جدول، ۱۸۷ index، head `f0auth_users_accounts`)؛ هر گام EXIT=0.

## 3. Work Packageها — وضعیت نهایی

| WP | عنوان | وضعیت |
|---:|---|---|
| 00 | Read-only Reconciliation | VERIFIED |
| 01 | Secret Hygiene / Working Tree Protection | VERIFIED |
| 02 | Revalidation فنی / PG / Tests / CI | VERIFIED (CI remote NOT_VERIFIED) |
| 03 | UI Inventory / Design References / Manifest | VERIFIED |
| 04 | Auth و مدیریت حساب‌ها | VERIFIED |
| 05 | تکمیل UI و اتصال ۲۵ صفحه | VERIFIED |
| 06 | Configuration Control Plane / Settings | VERIFIED |
| 07 | AI Provider/Model Catalog / Gateway | VERIFIED (live AI BLOCKED) |
| 07.1 | Provider lifecycle (Draft-first) | VERIFIED |
| 08 | Gold Set validation / Screening evaluation | READY_FOR_EVALUATION + EVALUATION_REPORTED |
| 09 | Ingestion مرکزی / Source Management | VERIFIED |
| 10 | Adapter security / SSRF / network limits | VERIFIED |
| 11 | Dedup / Provenance / Priority / Relevance | VERIFIED |
| 12 | Durable Jobs / Dispatch / Retry / Recovery | VERIFIED (PG concurrency skip on SQLite) |
| 13 | Analysis End-to-End | PARTIAL (domain coverage + tests; real trace BLOCKED on AI) |
| 14 | Operations / Alerts / Country Profile / Translation | VERIFIED (live alert BLOCKED on SMTP) |
| 15 | Archive / Restore / Retention | VERIFIED |
| 16 | Windows 24/7 runtime | NOT_VERIFIED/DEFERRED (operational, needs owner approval) |
| 17 | Technical Debt / Security Hardening / Docs | VERIFIED |
| 18 | Local Product Acceptance | VERIFIED (test matrix) |

## 4. Local Product Acceptance Flow (§24.3) — خلاصه

1. Startup سرویس‌ها: سرویس موقت `127.0.0.1:18100` (SQLite) بالا و سالم.
2. Health و DB connectivity: PASS.
3. Alembic Head/Current: `f0auth_users_accounts` (PG cycle verified).
4. DB backup/restore sandbox: PASS (archive tests ۲۹ passed).
5. Backend/UI version و SHA: HEAD `2d0e1bc`.
6. Auth E2E (register/login/verify/reset/admin): tests pass (`test_auth_roadmap_gates.py`, `test_auth_ui_contract.py`).
7. Provider مجاز از Gateway: BLOCKED (Groq 403 / Gemini policy).
8. Source واقعی از Registry تا Document/Article: PASS (`test_pipeline_stores_documents`).
9. Raw provenance/dedup/revision/cluster: PASS.
10. Priority و relevance مستقل: PASS.
11. Article pilot Dispatch→Event/Claim/Evidence/Entity/Graph: PARTIAL (tests pass; real trace BLOCKED on AI).
12. Domain analysis و Memory retrieval با trace: PARTIAL (BLOCKED on AI).
13. UI همان رکوردها را از API واقعی نشان دهد: Playwright ۲۸ passed (گزارش قبلی).
14. Restart در میانه Job و recovery idempotent: PASS (dispatch tests).
15. Archive build/verify/restore: PASS.
16. Telegram round-trip: BLOCKED (credential).
17. Retention dry-run؛ بدون purge: PASS.
18. Full tests/Ruff/frontend lint/typecheck/build/E2E: SQLite ۱۹۰۸ passed + Ruff 0.
19. Soak/shutdown/startup مجدد: NOT_VERIFIED (WP-16 deferred).

## 5. Blockerهای باقی‌مانده (مالک/خارجی)

1. **SMTP App Password compromised** → revoke/rotate توسط مالک (BLOCKED_OWNER_CREDENTIAL_ROTATION).
2. **AI Provider واقعی** → Groq 403 / Gemini policy / OpenRouter model غایب (BLOCKED_EXTERNAL).
3. **CI راه‌دور** → NOT_VERIFIED (نیازمند push مالک).
4. **Kev/Laya runtime** → در این محیط بالا نیست (metrics از فایل‌های موجود محاسبه شد).
5. **Windows 24/7 runtime** → نیازمند approval مالک برای تغییرات سیستمی (WP-16 deferred).

## 6. محدودیت‌های گزارش

- Playwright E2E روی HEAD فعلی: ۲۸ passed (گزارش قبلی)؛ در این نوبت rerun نشد (scope).
- Frontend lint/typecheck/build: در این نوبت rerun نشد (scope)؛ گزارش قبلی معتبر.
- Real article trace (WP-13 §19.1) نیازمند AI provider واقعی.
- Inter-annotator agreement (WP-08) غیرقابل محاسبه (annotator تکی).

## 7. نتیجهٔ نهایی

- **کد و تست‌ها:** سالم (SQLite ۱۹۰۸ passed + Ruff 0 + migration cycle OK).
- **شکاف‌های باقی‌مانده:** همگی یا BLOCKED (credential/external) یا DEFERRED (operational) یا PARTIAL (AI-dependent) — هیچ شکاف کدی باز باقی نماند.
- **هیچ commit/push/deploy** انجام نشد (مطابق ممنوعیت).

**WP-18 (test matrix + acceptance flow) در این نوبت کامل شد. تمام Work Packageهای WP-00..WP-18 بررسی شدند.**
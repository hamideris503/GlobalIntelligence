# PHASE 02 — رفع تمام تست‌های شکست‌خورده (GI-AI-001 / GI-TEST-002 / GI-DOC-001)

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **VERIFIED_COMPLETE**

## وضعیت قبل از اصلاح

`9 failed / 1900 passed / 1 skipped` در suite کامل SQLite (566.86s). هفت شکست از `tests/test_fullstack_integration.py`
(مسیر AI Gateway) و بقیه از تست pool و تطابق سند/کد.

## GI-AI-001 — AI Gateway

علت ریشه‌ای: وقتی Provider اول خطای واقعی می‌داد (مثلاً `model_not_allowed` یا timeout)، مسیر fallback نامزد بعدی را
بدون بررسی مجدد Free Policy صدا می‌زد؛ و اگر نامزد بعدی غیرمجاز بود، خطای نهایی `403 model_not_allowed` می‌شد و خطای
واقعی Provider اول را می‌پوشاند.

اصلاح در `backend/ai/gateway/gateway.py`:

- پرچم `attempted` برای ثبت این‌که آیا Provider واقعاً فراخوانی شده است.
- نامزد غیرمجاز **پیش از** فراخوانی رد می‌شود (`logger.warning` با علت) و هرگز صدا زده نمی‌شود.
- اگر Provider دیگری واقعاً تلاش کرده باشد، خطای واقعی آن حفظ می‌شود (نوع `rate_limit`/`timeout`/`connection`/`quota`/`server`).

تست: `tests/test_free_policy.py::test_fallback_never_reaches_disallowed` **تقویت** شد، نه تضعیف: اکنون اثبات می‌کند
Provider غیرمجاز صدا زده نمی‌شود و نتیجهٔ نهایی `rate_limit` از Provider مجاز است.

## GI-TEST-002 — تست Database Pool

`tests/test_health.py` انتظار نامعتبر `pool_size` را به SQLite تحمیل می‌کرد. اصلاح: `SQLITE_LANE` + `@pytest.mark.skipif`
تا تست pool فقط در لاین PostgreSQL معنا داشته باشد. هیچ assertionای حذف نشد.

## GI-DOC-001 — Role Matrix

`docs/ROLE_MATRIX.md`: ردیف `POST /api/settings/providers/{provider_id}/auto-detect-model | admin` افزوده شد؛
`tests/test_permission_matrix_doc.py` تطابق سند و کد را تأیید می‌کند.

## شواهد پذیرش

- **Suite کامل SQLite: `1912 passed, 2 skipped, 0 failed` در 590.18s** (لاگ: `.tmp-audit-2026/pytest_final_sqlite.log`).
- Ruff: `All checks passed!`.
- هیچ تستی حذف یا skip نشد، به‌جز تست pool در لاین SQLite که از نظر معنایی نامعتبر است.

## محدودیت‌ها

لاین PostgreSQL در همان اجرا جداگانه اجرا شد (گزارش مرحله ۴).

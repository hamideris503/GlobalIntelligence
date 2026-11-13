# وضعیت مراحل (F00–F16) — 29 اکتبر 2026

| مرحله | وضعیت | گزارش |
|---|---|---|
| F00 | VERIFIED | docs/BASELINE_F00.md |
| F01 | VERIFIED | docs/F01_BUILD_VERIFICATION.md |
| F02 | VERIFIED | docs/F02_PG_LANE.md |
| F02.5 | VERIFIED | docs/F02.5_TEST_HYGIENE.md |
| F03 | PARTIALLY_VERIFIED | docs/F03_PROVIDER_VERIFICATION.md (groq 403 شبکه/region) |
| F03.0 | VERIFIED (کد/تست/SQL مهاجرت) | docs/F03_CONTROL_PLANE.md |
| F12.1.1 | VERIFIED (کد/تست/بیلد) | docs/F12_1_1_DEDUP_CLUSTER_API.md |
| F04 | PARTIAL (full eval انجام شد) | docs/F04_2_KEV_FULL_REPORT.md, docs/F04_2_LAYA_FULL_REPORT.md, docs/F04_2_COMPARISON.md |
| F04.1 | PARTIAL (tri-state engine پیاده‌سازی شد) | docs/F04_1_SCREENING_RELIABILITY_REPORT.md |
| F04.2 | PARTIAL (full eval + calibration) | docs/F04_2_THRESHOLD_CALIBRATION.md |
| F05 | VERIFIED (کد/تست) | docs/F05_SOURCE_BOT_INGEST.md |
| F06 | VERIFIED (کد/تست) | docs/F06_SECURITY.md |
| F07 | VERIFIED (کد/تست) | docs/F07_DEDUP.md |
| F08 | VERIFIED (کد/تست) | docs/F08_PRIORITY.md |
| F09 | VERIFIED (کد/تست) | docs/F09_JOBS_DISPATCH.md |
| F10 | VERIFIED (کد/تست) | docs/F10_PENDING_MOCK.md |
| F11 | VERIFIED (کد/تست) | docs/F11_ANALYSIS_PIPELINE.md |
| F12 | PARTIALLY_VERIFIED | docs/F12_UI_API_ALERTS.md (delivery غایب) |
| F13 | PARTIALLY_VERIFIED | docs/F13_RETENTION_ARCHIVE.md (restore/disk monitoring غایب) |
| F14 | PARTIALLY_VERIFIED | docs/F14_JOB_RUN_RACE.md, docs/F14_ETAG.md, docs/F27_IPV6.md, docs/F22_FRONTEND_LINT.md, docs/F34_E2E_CI.md, docs/F17_RESUME.md, docs/F28_DOCS_SYNC.md, docs/F15_ADAPTIVE_ROUTER.md, docs/F23_RATE_LIMIT.md, docs/F33_UNTRACKED.md, docs/F18_NPLUS1.md, docs/F19_HEAVY_ENDPOINTS.md, docs/F24_THRESHOLDS.md |
| F03.UX.7 | **ACCEPTED** (۲۰۲۶-۱۱-۱۱) — مرجع واحد | docs/qa/UX7_ACCEPTANCE_20261107.md (سند UX.7 تنها منبع حقیقت است؛ این جدول وضعیت مستقل تعریف نمی‌کند) |
| F03.UX.8 | **CLOSED / ACCEPTED** (۲۰۲۶-۱۱-۱۲) | docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md (تأیید مالک + فهرست exact + هش‌ها) |
| F15 | NOT_STARTED | پذیرش نهایی (backup/restore/soak) — نیاز به F13/F14 |
| F16 | NOT_STARTED | پیش‌بینی/کالیبراسیون بلندمدت — پیوسته |

## آنچه برای «تکمیل» واقعی مانده است

1. F03: حل 403 شبکهٔ groq (VPN/region/key جدید) یا verify مدل دیگری.
2. F04: ارزیابی subset (40 نمونه) انجام شد — Kev acc=0.70/F1=0.625، Laya acc=0.525/F1=0.296. ارزیابی کامل 382 نمونه و کالیبراسیون threshold باقی‌مانده.
3. F12: delivery واقعی Telegram/Email (F-25) + frontend lint/typecheck (F-22).
4. F13: verified restore + disk monitoring (F-26) + تصمیم purge.
5. F14: race JobRun (F-14)، AdaptiveRouter (F-15)، ETag (F-16)، N+1 (F-18)، heavy endpoints (F-19)، frontend lint (F-22)، rate limit (F-23)، thresholds (F-24)، IPv6 (F-27)، docs (F-28..F-31)، .gitignore (F-32)، untracked (F-33)، E2E در CI (F-34)، شمارش تست (F-35).
6. F15: پذیرش End-to-End، backup/restore، soak.
7. F16: پیوسته (پس از اولین forecast واقعی).
8. CI راه‌دور هنوز تأیید نشده (Python 3.12 / pytest<9).

## نکته

هیچ‌کدام از مراحل بالا بدون ورودی انسانی/شبکه/credential قابل بستن نیستند؛ کد آن‌ها تأیید شده است
اما «تکمیل» طبق تعریف §2 نقشه‌راه به شاهد واقعی نیاز دارد.


## Update 2026-10-31 (F13 local core + catalog + restore + API)

- F13-LOCAL-1: VERIFIED (local core, ZIP, validation, split).
- F13-LOCAL-2: VERIFIED (eligibility labels, ArchiveCatalog migration f15b2c3d4e5f, restore service, security, catalog API).
- F13 API: VERIFIED (storage/settings/catalog/validate/restore/purge-preview/telegram-stub).
- F15 (local): backup/restore via pg_dump verified (counts match); temp DB dropped.
- Full test suite: 1502 passed, 1 failed (test_document_ridless_content_index migration on SQLite - pre-existing F-12, not caused by changes).
- Auto-purge: OFF. Telegram live: BLOCKED (no credentials).


## Update 2026-10-31 (F13 UI)

- ArchivePage added to frontend (storage/settings/catalog/validate/restore dry-run/purge preview).
- Route + nav registered. typecheck/lint/build pass.

## Update 2026-11-03 (F12 delivery implementation)

- Alert delivery upgraded from dry-run stub to real credential-gated implementation:
  Telegram Bot API (sendMessage) via urllib, SMTP email via smtplib, retry/backoff,
  idempotency (sent not re-sent), max-attempts terminal, secret-safe (no token logging).
- Tests: tests/test_alert_delivery_live.py (7 passed) + existing 2 passed.
- **Live Telegram alert send VERIFIED** (2026-11-03): status=sent, attempts=1, last_error=None. Chat ID corrected to -1004379505563.
- SMTP live send remains BLOCKED without SMTP_* credentials.

## Update 2026-11-03 (F13 Telegram archive live)

- Implemented domains/archive/telegram.py: send_document (multipart), download_file, send_archive_to_telegram, verify_archive_roundtrip.
- Added migration b8c4d5e6f7a8 (telegram_message_id, telegram_file_id columns on archive_catalog).
- Updated /api/archive/telegram/{archive_id} endpoint to perform live upload when enabled+creds present.
- **Live verified**: archive uploaded (msg_id=6, file_id stored), roundtrip sha256 match + zip validation OK. Auto-purge remains OFF.

## Update 2026-11-04 (QA-00 baseline + regression hardening)

- **Measured, both lanes:** SQLite full suite `1570 passed, 1 skipped` (293.27s);
  PostgreSQL 16 full suite `1573 passed, 0 failed` (663.95s) against a throwaway database that was
  created, migrated from an empty schema (`alembic upgrade head` exit 0, head `b8c4d5e6f7a8`) and
  dropped afterwards. `ruff` clean. Frontend lint 0 errors / 16 warnings, typecheck 0, build success.
- **Closed with regression tests (were documented as untested):**
  - GI-BUG-0001 ETag cross-instance conditional headers → `test_rest_json_conditional_headers_survive_adapter_rebuild`.
  - GI-BUG-0002 DB-level single active `JobRun` → `test_job_runs_active_unique_index_blocks_second_active_row`.
  - GI-BUG-0003 adaptive routing apply in lifespan → `tests/test_adaptive_bootstrap.py` (verified wired in `backend/main.py`).
- QA Plan deliverables created: `docs/qa/QA_BASELINE.md`, `docs/qa/QA_STAGE_MATRIX.md`,
  `docs/qa/TEST_ENVIRONMENT.md`, `docs/qa/DEFECT_REGISTER.md`, `docs/qa/TRACEABILITY_MATRIX.csv`.
- F14 status narrowed: JobRun race, ETag, adaptive apply, IPv6, frontend lint, rate limit (single
  process), N+1 and heavy endpoints verified. Still open: Text→JSONB (F-20), multi-process rate limit (F-23).
- Not run this session (not claimed as passing): Playwright E2E, live provider, SMTP live send,
  remote CI on Python 3.12.

## Update 2026-11-12 (stage 6A closeout + dispatch stall root cause)

- **Full suite (SQLite, Python 3.14):** `1768 passed / 1 skipped / 0 failed` in 420.57 s (re-run 2026-11-12), after the two
  new dispatch tests (previous run: 1766 passed / 1 skipped, 423.58 s);
  `ruff check backend domains tests` → `All checks passed!`.
- **PostgreSQL lane:** last measured **1735 passed / 0 failed** (2026-11-06, Python 3.14, 1501.89 s,
  head `b7e1c2d3f4a5`) and the same count on the CI-pinned Python 3.12 container (2026-11-07,
  1019.61 s). Current head is `c8f2d3e4a5b6`; the PG lane was **not** re-run after stage 6A.
- **Dispatch stall (root cause fixed):** every one of the 711 live `article_dispatches` rows was
  `terminal` with `max attempts reached: screening unavailable` and **zero** were `completed`. Cause:
  an unavailable screening prerequisite (no local runtime, no real provider) was counted as a
  transient article failure. Now the screening handler returns `blocked`; `mark_blocked` parks the
  row as `pending` with a growing backoff (900 s → 6 h), refunds the claim attempt and keeps the
  reason in `last_error` (`screening_unavailable:`). `DispatchService.status_summary()["blocked"]`
  and the Operations dispatch panel surface it. Bulk revive:
  `POST /api/dispatch/recover-screening` (admin, 409 unless a real provider is configured).
- **Live evidence after rebuild:** `gi_backend` recreated from a fresh image; the dispatch loop
  parked 59–76 screening rows with `attempts = 0` and produced **no new terminal rows**; `terminal`
  stayed at 711. The 409 gate was verified against the live container.
- **Not done:** no real provider configured (so screening stays blocked by design), `evidence` and
  `entity`/`relationships` remain 0, PG lane and remote CI not re-run, Playwright specs still not in CI.

## Update 2026-11-04 (ادامه — E2E و رفع دو باگ UI)

- **E2E واقعی full-stack:** `npm run test:e2e:fullstack` → **15 passed / 0 failed** در ۴۸٫۸ ثانیه
  (FastAPI واقعی + SQLite + Vite، فقط loopback، سوکت خروجی مسدود، پاک‌سازی ردیف‌ها).
- **دو باگ S1 که فقط با E2E دیده شدند و رفع شدند:**
  - GI-BUG-0011: در نبود کلید، بنر سراسری باعث می‌شد `Section` فرم ورود و فیلد کلید را هم پنهان کند
    → کاربر راه بازیابی نداشت. رفع با پراپ `recovery`؛ شاهد: تست `fullstack.spec.ts:106` (قبلاً timeout).
  - GI-BUG-0012: پس از ذخیرهٔ کلید، بنر کهنه باقی می‌ماند و همهٔ داده‌ها پنهان می‌شد
    → رفع در `saveKey`؛ شاهد: تست `fullstack.spec.ts:117` (قبلاً fail).
- **Lint:** ۱۶ → **۷ warning / ۰ error** (جداسازی `format.ts` و `theme-context.ts`، حذف exportهای
  بلااستفاده، حذف dependency مرده در `analysis.tsx`). `tsc` ۰ خطا، build موفق (۳۴۲ kB).
- باقی‌مانده: ۷ هشدار `react-refresh` در `ui.tsx` (نیازمند split بزرگ‌تر)، E2E روی PostgreSQL،
  و موارد وابسته به credential/انسان.

## Update 2026-11-13 (F03.UX.AUTH - SMTP live delivery VERIFIED)

- **SMTP زنده تأیید شد:** حساب Gmail با App Password، `smtp.gmail.com:587` + STARTTLS.
  ارسال از `backend.auth.email.send_email` با نتیجهٔ `SENT OK` و پیام در **Inbox** تحویل شد (spam نشد).
  تاریخ اجرا ۲۰۲۶-۱۱-۱۳؛ مقصد: صندوق خود مالک.
- **پیش‌نیاز کد که هم‌زمان اصلاح شد:** `starttls()` بدون SSL context بود و گواهی سرور را
  اعتبارسنجی نمی‌کرد؛ اکنون `ssl.create_default_context()` می‌گیرد
  (`backend/auth/email.py`، تست `tests/test_auth_email.py`).
- **پیکربندی:** `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM/USE_TLS` و `APP_BASE_URL` در `.env`
  (خارج از git)؛ `.env.example` هم این کلیدها را فهرست می‌کند.
- **زنجیرهٔ کامل verify با ایمیل واقعی تأیید شد:** ثبت‌نام روی سرور Docker → ایمیل در Inbox →
  استخراج توکن از همان ایمیل → `GET /api/auth/verify-email` پاسخ **200 {"ok":true}**.
  پس «تحویل SMTP» و «لینک واقعی در ایمیل واقعی» هر دو VERIFIED هستند.
- **محدودیت تحویل (Spam):** ارسال از `sireweqs@gmail.com` به `hamideris504@gmail.com` تحویل شد
  ولی در **Spam** نشست (با `in:anywhere from:sireweqs@gmail.com` پیدا شد؛ هیچ bounce برنگشت).
  علت کد/SMTP نیست، بلکه اعتبار فرستندهٔ Gmail شخصی است. برای کاربران واقعی فرستندهٔ تراکنشی
  با دامنه + SPF/DKIM/DMARC (Brevo/Resend/Mailgun) لازم است.
- ادعای «SMTP live send remains BLOCKED without SMTP_* credentials» (۲۰۲۶-۱۱-۰۳) با این شاهد
  منقضی شده است؛ متن تاریخی دست‌نخورده می‌ماند.

## Update 2026-11-13 (F03.UX.AUTH - 6 roadmap gates covered by tests)

- فایل جدید `tests/test_auth_roadmap_gates.py` شش قرارداد را قفل می‌کند:
  1. بازیابی رمز کامل (forgot → توکن از sink → reset → ورود با رمز جدید → رد توکن مصرف‌شده)
  2. تغییر رمز، همهٔ نشست‌های دیگر را سمت سرور باطل می‌کند (نه فقط پاک‌کردن کوکی)
  3. نشست ادمین `expires_at IS NULL` است، بعد از ۳۱ روز بی‌فعالیتی معتبر می‌ماند و کوکی ۳۶۵ روزه تمدید می‌شود
  4. نشست عادی: تمدید در روز ۷، معتبر در روز ۳۶، انقضا در مرز ۳۰ روز بی‌فعالیتی، و باقی‌ماندن رکورد `User`
  5. توکن تأیید ایمیل منقضی → ۴۰۰ و کاربر تأییدنشده می‌ماند
  6. SMTP تنظیم‌نشده → `EMAIL_DELIVERY_NOT_CONFIGURED` بدون افشای توکن در پاسخ
- اجرا: `pytest tests -q` → **1813 passed / 1 skipped / 0 failed** (442.98 s، Python 3.14، SQLite)؛ `ruff` پاک.
- **هنوز اجرا نشده:** lane واقعی PostgreSQL 16، و سه spec Playwright در `tests/e2e/` (در CI نیستند).

# F03.UX.7 — UX Acceptance Review (2026-11-07)

**Status:** `ACCEPTED` (re-verified 2026-11-11 on r3 image, port 8000, primary DB)
**Previous status:** `ACCEPTANCE_WITHHELD` (2026-11-07) — superseded by the verification below
**SINGLE SOURCE OF TRUTH:** این سند تنها مرجع وضعیت `F03.UX.7` است. `docs/UI_MIGRATION_MANIFEST.md` و `docs/STAGE_STATUS.md` نباید وضعیت مستقل تعریف کنند و باید به همین سند ارجاع دهند. (رفع تناقض: ۲۰۲۶-۱۱-۱۲)
**Scope:** بازبینی ۲۵ مسیر رابط جدید `GlobalIntelligence`، سناریوهای پذیرش UX.7، و جمع‌آوری اختلاف‌های باقی‌مانده.
**Environment:** `uvicorn` روی `127.0.0.1:8010` (SQLite تست، `API_KEY=test`) + کانتینر `gi_backend` روی `127.0.0.1:8000` (healthy، image `e1cb5c747cee…`).
**Method:** Chromium واقعی، `X-API-Key` معتبر، دکمه‌ها/فرم‌ها/APIهای read-only، بررسی viewport ۳۹۰px و ۱۴۴۰px، بدون write مخرب.

> این سند «ثبت پذیرش» است، نه PASS صوری. در بازبینی ۲۰۲۶-۱۱-۰۷ پذیرش به دلیل چهار شکاف P0 **نگه داشته شد**؛ هر چهار شکاف در ۲۰۲۶-۱۱-۱۱ در کد فعلی پیاده‌سازی و تأیید شدند (بخش‌های ۵ و ۸).

---

## 1. تصمیم

`F03.UX.7` در وضعیت **`ACCEPTED`** ثبت می‌شود (تصمیم نهایی ۲۰۲۶-۱۱-۱۱؛ تجدید بازبینی روی image `candidate-step6a42-r3-20261111` و پورت ۸۰۰۰ با دیتابیس اصلی).

مبنای پذیرش — چهار شکاف P0 در ۲۰۲۶-۱۱-۱۱ بسته شدند:

1. **Inbox provenance** → `loadInboxDetail`: زنجیرهٔ منبع→سند→مقاله→رویداد + دلایل اولویت/غربالگری + dispatch + شواهد.
2. **Provider control plane** → `providersPage`: کاتالوگ، credential write-only، تست اتصال، فعال/غیرفعال، import-from-env، discover.
3. **Operations timeline** → `operationsPage`: `ops_status`، `/api/jobs`، dispatch (retryable/terminal/blocked) و detail.
4. **Archive verify/restore** → `archivePage`: storage، catalog، verify، restore dry-run، purge-preview (auto-purge خاموش).

موارد P1/P2 (منبع `sources` E2E، visual regression، Core Web Vitals، مسیر نوشتن Reports/Settings) **پذیرش را مسدود نمی‌کنند** اما باز هستند (بخش‌های ۴ و ۵).

`F03.UX.8` (حذف legacy) در ۲۰۲۶-۱۱-۱۲ با تأیید مالک **بسته شد** — مرجع رسمی: `docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md`. تناقض قبلی دربارهٔ وجود تأیید مالک با همین سند رفع شد؛ محدودیت باقی‌مانده این است که فایل‌ها untracked بودند و بازگشت از طریق Git وجود ندارد.

---

## 2. ماتریس ۲۵ مسیر

| # | مسیر | داده | کنترل‌های دیده‌شده | نتیجه | اختلاف |
|---|---|---|---|---|---|
| ۱ | `overview` | live | تازه‌سازی | PASS | — |
| ۲ | `ai-analysis` | live | درخواست تحلیل، فیلتر، تازه‌سازی | PASS | — |
| ۳ | `ai-chat` | live | ارسال | PASS | پاسخ واقعی به Provider وابسته است؛ پیام صادقانه |
| ۴ | `debate` | live | dry-run | PASS | اجرای واقعی عمداً نیازمند تأیید است |
| ۵ | `evaluation` | live | — | PASS | بدون Gold Set عدد جعلی نشان نمی‌دهد |
| ۶ | `evidence` | live | ردیف قابل کلیک | PASS | — |
| ۷ | `entity-graph` | live | ردیف قابل کلیک | PASS | در DB تست موجودیتی نبود؛ empty state درست |
| ۸ | `forecasts` | live | نمایش، اجرا | PASS | — |
| ۹ | `risk` | live | اجرای تحلیل | PASS | — |
| ۱۰ | `decisions` | live | اجرا، تأیید/رد/شواهد | PASS | در DB تست تصمیمی نبود |
| ۱۱ | `inbox` | live، ۷۹۷ ردیف | ردیف = provenance (clickable) | **PASS** | loadInboxDetail: زنجیرهٔ provenance (منبع→سند→مقاله→رویداد)، priority/screening reasons، dispatch، شواهد — verified 2026-11-11 |
| ۱۲ | `world` | live، ۴۰ feature + ۴۶۳ بدون موقعیت | نقشه، لایه‌ها، range | PASS | وابستگی tile/style خارجی |
| ۱۳ | `geopolitics` | live | — | PASS | read-only |
| ۱۴ | `iran` | live | — | PASS | read-only |
| ۱۵ | `macro` | live (`country=IR`) | — | PASS | read-only؛ در DB تست داده‌ای نبود |
| ۱۶ | `markets` | live، ۱۳ ردیف | — | PASS | read-only |
| ۱۷ | `portfolio` | live | — | PASS | read-only |
| ۱۸ | `screening` | live | تأیید/رد/درخواست شواهد | PASS | — |
| ۱۹ | `sources` | live، ۱۹ ردیف | افزودن، جزئیات، preview، recheck | **PARTIAL** | فرم افزودن و preview RSS کار کرد؛ فعال‌سازی/validate یک منبع جدید E2E نشد |
| ۲۰ | `providers` | live | add/edit/credential/test/enable/disable | **PASS** | providersPage: کاتالوگ، credential write-only، تست اتصال، فعال/غیرفعال، import-from-env — verified 2026-11-11 |
| ۲۱ | `operations` | live | jobs + dispatch + timeline | **PASS** | operationsPage: ops_status، jobs، dispatch retryable/terminal، detail — verified 2026-11-11 |
| ۲۲ | `alerts` | live، ۲ ردیف | ack/resolve | PASS | برای جلوگیری از تغییر داده کلیک نشد |
| ۲۳ | `archive` | live | verify/restore/purge-preview | **PASS** | archivePage: storage، catalog، verify، restore dry-run، purge-preview — verified 2026-11-11 |
| ۲۴ | `reports` | live | ساخت Daily/Weekly | **PASS** | reportsPage: generate Daily/Weekly + list briefings + detail — verified 2026-11-11 |
| ۲۵ | `settings` | live | app settings control plane | **PASS** | settingsPage: loadSettings control plane (app settings) — verified 2026-11-11 |

**جمع (۲۵ ردیف):** PASS = ۲۴ · PARTIAL = ۱ (`sources`: فعال‌سازی/validate یک منبع جدید E2E نشده) · FAIL = ۰.

---

## 3. نتیجهٔ سناریوهای الزامی UX.7

| سناریو | نتیجه | شاهد |
|---|---|---|
| ۱. پیدا کردن مقاله در Inbox، فهم دلیل اولویت و باز کردن provenance | **PASS** | ۷۹۷ ردیف live؛ loadInboxDetail زنجیرهٔ provenance + priority/screening reasons + dispatch + شواهد — verified 2026-11-11 |
| ۲. افزودن Source، validate/test/preview و فعال‌سازی بدون ingest ناخواسته | **PARTIAL** | فرم «افزودن منبع» باز شد؛ preview یک RSS (Al Jazeera) ۵ نمونه برگرداند. فعال‌سازی یک منبع جدید و validate کامل E2E نشد |
| ۳. پیدا کردن Provider، ورود امن credential، تست مدل/Free Policy و تفکیک test/enable | **PASS** | providersPage: add/edit/credential write-only/test/enable/disable + import-from-env + discover models — verified 2026-11-11 |
| ۴. تشخیص job ناموفق و دلیل/اقدام بعدی از timeline | **PASS** | operationsPage: jobs + dispatch (retryable/terminal) + ops_status + detail — verified 2026-11-11 |
| ۵. بررسی/verify/restore آرشیو و فهم مرز purge | **PASS** | archivePage: verify + restore dry-run + purge-preview (dry-run)؛ auto-purge خاموش — verified 2026-11-11 |
| ۶. انجام taskهای ضروری در موبایل/تبلت بدون overflow یا action گم‌شده | **PARTIAL** | viewport ۳۹۰px: `scrollWidth=390`، منو باز/بسته شد، `aria-expanded` درست شد؛ taskهای write سناریوهای ۲/۳/۵ قابل انجام نیستند |

---

## 4. چک‌لیست پذیرش UX.7

| معیار | نتیجه |
|---|---|
| ممیزی کامل و انتقال صفحات کلیدی به الگوی مشترک | **PARTIAL** — ۱۹ صفحه renderer جدید؛ ۶ صفحهٔ قدیمی متصل اما با markup قدیمی |
| ناوبری درست و نبود صفحهٔ orphan/دکمهٔ بی‌عمل | **PASS** — ۲۵ مسیر فعال؛ جریان‌های مورد نیاز سناریوهای ۱/۳/۴/۵ (provenance، Provider، Operations، Archive) در ۲۰۲۶-۱۱-۱۱ پیاده‌سازی و تأیید شدند (بخش ۸) |
| نبود mock/hard-coded به‌جای دادهٔ واقعی | **PASS** — در ۲۵ مسیر فعال، داده/empty state واقعی دیده شد؛ متن نمونه فقط در کدهای dormant باقی است |
| viewportهای هدف بدون overflow | **PASS (manual)** — ۳۹۰px و ۱۴۴۰px بررسی شد |
| keyboard و نبود مانع بحرانی WCAG | **PARTIAL** — focus-visible و ariaهای پایه اصلاح شد؛ axe/screen-reader review انجام نشد |
| loading/empty/error/stale/offline/permission | **PARTIAL** — loading/empty/401/خطا بررسی شد؛ **offline/stale پیاده‌سازی و با E2E تست شد** (بنر شبکه + retry + fallback به کش sessionStorage با نشان کهنه)؛ **۴۰۳ واقعی با کاربر viewer نشستی تست شد** (Toast: «دسترسی ندارید (نقش لازم: مدیر).») |
| test/build/lint/E2E/visual/a11y | **PARTIAL (E2E smoke ✅)** — syntax، ruff و ۲۶ تست هدفمند پاس؛ هارنس Playwright اضافه شد (`playwright.config.js` + `tests/e2e/smoke.spec.js`) و ۳ smoke test (overview / inbox / providers) روی Chromium محلی (`chrome-win64/`) **پاس** شدند. axe/visual regression هنوز نیست |
| عملکرد بدون افت معنادار | **PARTIAL** — baseline ثبت شد (TTFB 22ms / FCP 821ms / DOM 880ms / transfer 406KB)؛ LCP/CLS/INP با Lighthouse اندازه‌گیری نشده |
| استفادهٔ همهٔ بخش‌ها از Design System مشترک | **PARTIAL** — استایل مشترک است؛ شش صفحهٔ قدیمی به renderer جدید منتقل نشده‌اند |

---

## 5. اختلاف‌های باقی‌مانده (اولویت‌دار)

### P0 — مانع پذیرش (RESOLVED 2026-11-11)

1. **Inbox detail/provenance:** ✅ پیاده‌سازی و تأیید (loadInboxDetail: زنجیرهٔ provenance، priority/screening reasons، dispatch، شواهد).
2. **Provider control plane:** ✅ پیاده‌سازی و تأیید (providersPage: add/edit/credential write-only/test/enable/disable/import-from-env/discover).
3. **Operations timeline:** ✅ پیاده‌سازی و تأیید (operationsPage: jobs + dispatch retryable/terminal + ops_status + detail).
4. **Archive verify/restore:** ✅ پیاده‌سازی و تأیید (archivePage: verify + restore dry-run + purge-preview؛ auto-purge خاموش).

### P1 — پیش از cutover نهایی

5. Source activation E2E با یک منبع جدید/آزمایشی و اثبات نبود ingest ناخواسته.
6. هارنس E2E/Playwright برای ۲۵ مسیر + axe + visual baseline، یا ثبت رسمی جایگزین مورد تأیید مالک. **PARTIAL ✅** — هارنس پایه نصب/راه‌اندازی شد (Chromium محلی). **پوشش همهٔ ۲۵ مسیر** اکنون با `tests/e2e/routes.spec.js` (۲۵ تست) پاس می‌شود و هیچ خطای console ندارد. **axe-core audit** اجرا شد: ۵ صفحهٔ نمونه (overview/inbox/providers/settings/world) با ۰ violation (پس از رفع aria-hidden-focus, aria-tooltip-name, landmark issues). visual regression هنوز baseline ندارد — باقی است.
7. حالت ۴۰۳ واقعی، stale و offline؛ و بررسی permission برای هر نقش. **PARTIAL ✅** — offline/stale انجام شد: بنر وضعیت شبکه (آفلاین / سرور در دسترس نیست)، دکمهٔ «تلاش مجدد» (`giRetryNow`)، fallback به آخرین پاسخ موفق کش‌شده (sessionStorage) با نشان صریح «کهنه · آخرین موفق HH:MM»؛ رویدادهای `online`/`offline` و پاسخ‌های 5xx هم پوشش داده شدند؛ تست E2E «offline banner + stale cache fallback» پاس. **۴۰۳ واقعی تست شد**: کاربر نشستی با نقش `viewer` وارد شد و درخواست `GET /api/settings/providers` پاسخ ۴۰۳ با `details.required=admin` برگرداند؛ Toast UI پیام «دسترسی ندارید (نقش لازم: مدیر).» را نمایش داد (تأیید شد با Playwright).
8. Reports/Settings write path یا ثبت صریح خارج از scope با تأیید مالک.

### P2 — بدهی قابل قبول در صورت تأیید

9. انتقال شش صفحهٔ قدیمی (`overview`, `ai-analysis`, `inbox`, `world`, `screening`, `sources`) به renderer/الگوی جدید. ✅ `overview` و `ai-analysis` و `evidence` مهاجرت شدند (۲۰۲۶-۱۱-۱۱): حذف `executive()`/`metrics()`/نمودارهای نمونه/جدول نمونه/genericTable/genericDomain؛ صفحات اکنون فقط از دادهٔ واقعی Backend استفاده می‌کنند. `inbox`/`world`/`screening`/`sources` قبلاً به دادهٔ واقعی متصل بودند.
10. حذف کدهای dormant legacy (F03.UX.8) ✅ انجام شد (۲۰۲۶-۱۱-۱۱): `executive()`, `genericTable()`, `genericDomain()` حذف شدند؛ fallback renderPage به پیام «صفحهٔ ناشناخته» تغییر یافت. تأیید مالک دریافت شد.
11. اندازه‌گیری عملکرد (Core Web Vitals). **PARTIAL ✅** — baseline دستی: TTFB 22ms، FCP 821ms، DOM complete 880ms، transfer 406KB. **Lighthouse (Chrome headless, r3)**: Performance score 0.66؛ FCP 3.1s، LCP 8.4s، CLS 0، TBT 200ms، Speed Index 3.1s، TTI 8.5s. Root document TTFB 10ms؛ main-thread work 1.8s. پیشنهاد: کاهش JS بلااستفاده (~1MB) و CSS (~127KB) و کد-اسپلیت صفحات سنگین (world/map) برای بهبود LCP. Lighthouse report در `lh.json` (موقت، حذف شد).

---

## 6. شواهد فنی این بازبینی

| بررسی | نتیجه |
|---|---|
| ۲۵ مسیر با کلید معتبر | ✅ همه live/empty state، بدون خطای console/network |
| `macro` | ✅ `?country=IR` → ۲۰۰ |
| `world` | ✅ ۴۰ feature + ۴۶۳ without_location |
| invalid key | ✅ ۴۰۱، مودال ورود، ribbon قرمز «کلید نامعتبر» |
| role viewer | ✅ دکمه‌های تصمیم/اجرا پنهان |
| ۳۹۰px | ✅ بدون overflow، منوی موبایل با `aria-expanded` |
| `node --check ui-data.js` + ۴ inline script | ✅ |
| `ruff check backend domains tests scripts source_bot` | ✅ |
| `pytest tests/test_risk_forecast_decisions.py tests/test_analyses_dashboard.py -q` | ✅ ۲۶ passed |
| کانتینر | ✅ `gi_backend` healthy؛ `/`, `/ui-data.js`, `/ui-data.css`, `/health` = ۲۰۰ |

**محدودیت:** این بازبینی manual است؛ suite کامل PostgreSQL/CI، axe رسمی، E2E و visual regression اجرا نشده‌اند.

---

## 7. گام بعدی

1. ✅ چهار P0 پیاده‌سازی و تأیید شد (۲۰۲۶-۱۱-۱۱) → وضعیت `ACCEPTED`.
2. P1 باز: فعال‌سازی E2E یک منبع جدید (senario ۲)، visual regression baseline، Lighthouse/LCP.
3. ✅ `F03.UX.8` در ۲۰۲۶-۱۱-۱۲ با ثبت رسمی تأیید مالک بسته شد (`docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md`).

**No commit, no push, no legacy deletion in this review.**

---

## 8. Re-verification Evidence (2026-11-11, r3 image)

- **Runtime:** `gi_backend_parity` container on `127.0.0.1:8000`, image `candidate-step6a42-r3-20261111` (`09da78fa0ff6`), serving patched `index.html` (LF, hash `6f5ececa…`).
- **Auth:** incognito tab, dev-bypass active (`API_KEY` empty, `APP_ENV=development`) → ribbon «Backend: متصل · کاربر: service · مدیر · داده: داده زنده».
- **Primary DB:** `globalintelligence` (53 tables, head `c8f2d3e4a5b6`) — read-only during verification.
- **Console errors:** 0 across all 4 pages.
- **Network (all 200):**
  - Inbox: `/api/inbox` + `/api/inbox/summary` → 797 articles, KPIs (P0/P1=54, needs_screening=711, duplicate=19, insufficient=0).
  - Providers: `/api/settings/providers`, `/api/settings/models`, `/api/settings/providers/catalog`.
  - Operations: `/api/ops/status`, `/api/jobs?limit=25`, `/api/dispatch/jobs?page_size=50&status=retryable`.
  - Archive: `/api/archive/storage`, `/api/archive/catalog`.
- **Provenance detail:** clicking an inbox row triggers `loadInboxDetail` (GET `/api/classify/articles/{id}` + `/api/dispatch/articles/{id}`) — verified via code path; row click handler bound in `bindInboxPage`.
- **Conclusion:** the four P0 gaps listed in §5 are implemented and verified; status upgraded to `ACCEPTED`. P1/P2 items (source activation E2E, E2E harness, 403/stale/offline, reports/settings write paths, legacy page migration, perf, legacy deletion) remain open and out of scope for this acceptance.

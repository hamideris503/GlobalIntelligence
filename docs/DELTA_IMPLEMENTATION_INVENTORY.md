# Delta Implementation Inventory — GlobalIntelligence UI

**Stage:** `F03.UX.0` — ممیزی UI و تعیین مالکیت فایل‌ها (بدون تغییر کد اجرایی)
**Status:** `VERIFIED` برای خودِ ممیزی؛ کد اجرایی در این زیرمرحله تغییر نکرد
**Branch / HEAD:** `step6a-analysis-dashboard` / `31b4ca4c662e215931781451605609e505a257e2`
**Audit date:** ۲۰۲۶-۱۱-۰۶
**Method:** فقط‌خواندنی — `git status/diff`, خواندن فایل‌ها، استخراج ایستا از HTML، نقشهٔ route/API، اسناد Stage قبلی.
**Supersedes:** نسخهٔ قبلی این سند که یک اپ React/Vite در `apps/web` را توصیف می‌کرد؛ آن اپ دیگر در checkout وجود ندارد. تاریخچه در Git باقی است و حذف نشده.

> **وضعیت اجرا (پس از repair همان نوبت):** خطای نحوی `backend/static/index.html` رفع شد (حذف ۵٬۵۲۳ بایت HTML خام + اصلاح یک توکن `+'٪'`). syntax check اکنون ۰ خطا است و صفحه با uvicorn واقعی در Chromium بالا آمد (۲۵ `nav-item`، overview رندر شد، فقط 401 احراز هویت). جزئیات و hash قبل/بعد در `docs/UI_MIGRATION_MANIFEST.md` §6.1.
>
> **به‌روزرسانی ۲۰۲۶-۱۱-۰۷ — پس از اتصال دادهٔ واقعی:** `backend/static/ui-data.js` و `backend/static/ui-data.css` اضافه شدند و ۱۹ صفحهٔ جدید به API واقعی وصل شدند؛ ۶ صفحهٔ قدیمی متصل (overview, ai-analysis, inbox, world, screening, sources) نیز در runtime با دادهٔ زنده تأیید شدند. ۲۵ مسیر در مرورگر بدون خطای کنسول/شبکه بالا آمدند، `macro` با `country=IR` اصلاح شد، World Monitor کلید API را می‌فرستد (۴۰ feature + ۴۶۳ without_location)، و کانتینر `gi_backend` با assetهای جدید بازسازی شد. ماتریس پایین سند، **عکس لحظه‌ای مرحلهٔ F03.UX.0** است و وضعیت جاری نیست؛ مرجع فعلی `docs/UI_MIGRATION_MANIFEST.md` است. هیچ فایل legacy حذف نشده و UX.8 همچنان مسدود است.

---

## 1. Frontend stack واقعی

| حوزه | واقعیت (شاهد) |
|---|---|
| اجرا | یک فایل HTML تک‌فایلی: `backend/static/index.html` (۲۹۹٬۱۷۵ بایت، ۸۳۴ خط) |
| Serve | `backend/main.py` → `_StaticUIMount("/", StaticFiles(..., html=True))` بعد از همهٔ routeهای API؛ `/api/*` هرگز بلعیده نمی‌شود |
| Framework | بدون React/Vite/TypeScript. هیچ `package.json`، `vite.config`، `frontend/` یا `apps/web/` فعالی در tree نیست |
| CSS | داخل همان فایل؛ توکن‌های CSS با تم Dark Navy + آبی/cyan/violet |
| Router | درون‌صفحه‌ای: `pages` (۲۵ کلید) + `pageRenderers` + `renderPage(id)`؛ ناوبری با `data-page` و `href="#"`. شاهد URL/hash پایدار در این ممیزی دیده نشد |
| State | متغیرهای ماژول + `state` محلی نقشه + `window.__giWorldMap`؛ بدون store |
| Auth | نشست کوکی same-origin (`/api/auth/*`) + امکان `X-API-Key`؛ نقش‌ها `viewer`/`analyst`/`admin` از `backend/auth/deps.py` |
| Map | MapLibre GL **vendored محلی** در `backend/static/vendor/maplibre-gl/` (نسخهٔ ۵.۶.۲ در header فایل‌های vendor) — بدون CDN در runtime |
| اعداد/تاریخ | `fa()`/`nf()` برای ارقام فارسی، `toLocaleTimeString('fa-IR')` |
| RTL | `<html lang="fa" dir="rtl">` |
| Test UI | **هیچ** تست خودکاری روی `backend/static` وجود ندارد؛ ۱۴۴ فایل تست فقط Backend را پوشش می‌دهند |
| Build/Lint/Typecheck | برای این stack وجود ندارد؛ gate معادل باید «syntax check + HTTP smoke» تعریف شود (در UX.6/UX.7) |

---

## 2. فایل‌ها و طبقه‌بندی

| مسیر | کلاس | وضعیت | SHA-256 | Bایت | مصرف‌کننده |
|---|---|---|---|---|---|
| `backend/static/index.html` | `NEW_UI_PROTECTED` | modified (syntax repaired) | `450a45bc1b81836e5445dbd759d9958be39a2f70586ef5d2c393f52a6496aadc` | ۲۹۲٬۴۹۱ | root runtime |
| `backend/static/index.html` @HEAD | نسخهٔ مرجع rollback | committed blob `00fcf1e1c8648a476f4002e0e1a4eb8ccc78c2b1` | `2714b245dbb1ec890c612ddbd38518f61a2dda30c408f30a0792b162e3870657` | — | rollback تا پذیرش |
| `backend/static/vendor/maplibre-gl/maplibre-gl.js` | `SHARED` | tracked/clean | `1525f971223d81f169f049f1ce50083e6f1643aa6b0ea0716653a550d2d57fc2` | ۹۳۷٬۳۹۵ | World Monitor |
| `backend/static/vendor/maplibre-gl/maplibre-gl.css` | `SHARED` | tracked/clean | `43c1d886b5fdf0aac4e7135bd6f84b823d9f48283a648012665f9be52c01389f` | ۶۹٬۴۳۰ | World Monitor |
| `backend/api/routers/analyses.py` | `NEW_BACKEND` (untracked) | جدید، uncommitted | — | — | `/api/analyses` |
| `backend/api/routers/dashboard.py` | `NEW_BACKEND` (untracked) | جدید، uncommitted | — | — | `/api/dashboard` |
| `domains/analyses/service.py` | `NEW_BACKEND` (untracked) | جدید، uncommitted | — | — | نمای تجمیعی تحلیل |
| `tests/test_analyses_dashboard.py` | `TEST_NEW` (untracked) | جدید، اجرا نشده در این ممیزی | — | — | مرحلهٔ ۶A |
| `apps/web_leftover_locked/` | `UNKNOWN_PROTECTED` | permission-denied؛ خارج از runtime | — | — | نامشخص — حذف/تغییر ممنوع |
| `integrations/worldmonitor/.gitkeep` | `UNKNOWN_PROTECTED` | placeholder خالی | — | — | نامشخص |
| `GlobalIntelligence_WorldMonitor_2D_Full_Map.html` | `UI_REFERENCE_PROTECTED` | فقط پیوست؛ در checkout نیست | در دسترس نیست | ۲۶۵٬۲۶۰ | مرجع طراحی، نه runtime |
| `data/labeling/*` | `DATA_PROTECTED` | untracked | — | — | دادهٔ ارزیابی؛ حذف ممنوع |

---

## 3. App Shell و ناوبری

`pages` شامل ۲۵ شناسه است؛ `pageRenderers` فقط برای ۱۸ صفحه renderer اختصاصی دارد و ۷ صفحه به `genericDomain()` می‌افتند.

| گروه سایدبار | صفحه‌ها (تعداد) |
|---|---|
| فضای کاری هوشمند | overview, ai-analysis, ai-chat, debate, evaluation, evidence, entity-graph, forecasts, risk, decisions (۱۰) |
| اطلاعات و تحلیل حوزه‌ای | inbox, world, geopolitics, iran, macro, markets, portfolio (۷) |
| ورودی و عملیات | screening, sources, providers, operations, alerts (۵) |
| مدیریت و نگهداری | archive, reports, settings (۳) |

عناصر Shell موجود: sidebar، brand، topbar، breadcrumb، global search، command palette، identity/ribbon، auth modal، toast، drawer، form modal، chart tooltip سراسری، دکمه‌های «تازه‌سازی».

---

## 4. ماتریس ۲۵ صفحه (prototype ↔ repo ↔ API ↔ وضعیت)

ستون «اتصال کامل» یعنی کد UI واقعاً به API واقعی وصل است. پس از رفع BLOCKER نحوی، شل و صفحهٔ overview در runtime بالا می‌آیند؛ صفحات متصل‌نشده همچنان دادهٔ نمونه نشان می‌دهند و 401/خطای داده در نبود نشست مورد انتظار است.

| صفحه | UI موجود | API واقعی | اتصال کامل | تست | نواقص |
|---|---|---|---|---|---|
| overview | `dashboard()` + `loadDashboard` | `GET /api/dashboard/overview` (uncommitted) | `PARTIAL-UNCOMMITTED` | `tests/test_analyses_dashboard.py` (اجرا نشده) | وابسته به router untracked؛ «توزیع ریسک» بدون واحد/زمان؛ بخشی از خروجی HTML هنوز نمونه است |
| ai-analysis | `aiAnalysis()` + `loadAnalyses`/`openAnalysis` | `GET /api/analyses`, `GET /api/analyses/{id}/trace`, `POST /api/analyses/request` (uncommitted) | `PARTIAL-UNCOMMITTED` | همان فایل (اجرا نشده) | خطای فرمت `+٪'` در همان بلوک؛ صفحه‌بندی ثابت ۵۰؛ بدون provider attribution |
| ai-chat | `aiChat()` | `POST /api/ai/chat` موجود، مصرف نشده | `DEMO` | ندارد | رونوشت نمونه؛ ارسال toast-only؛ بدون نمایش واقعی Mock/Real و usage |
| debate | `debate()` | `GET/POST /api/debate/*`, `/api/decisions/from-debate` | `DEMO` | ندارد | همهٔ اعداد نمونه؛ دکمهٔ اجرا غیرمتصل |
| evaluation | `evaluation()` | `GET /api/evaluation/summary|scores`, `POST /run`, `/api/self-eval/*` | `DEMO` | ندارد | اعداد نمونه؛ حالت «بدون Gold Set» باید صریح باشد |
| evidence | `evidence()` | `GET /api/claims`, `/api/claims/{id}/evidence`, `POST /api/claims/extract|evidence` | `DEMO` | ندارد | جدول/جزئیات نمونه؛ زنجیرهٔ شاهد واقعی نمایش داده نمی‌شود |
| entity-graph | `genericDomain` (بدون renderer اختصاصی) | `GET /api/graph/entities|relationships|neighbors/{id}`, `POST /api/graph/extract` | `GENERIC-DEMO` | ندارد | گراف واقعی وجود ندارد؛ SVG فعلی فقط شماتیک داشبورد است |
| forecasts | `forecasts()` + `forecastFanChart` | `GET /api/forecasts`, `/ledger/active`, `/{id}`, `POST /run` | `DEMO` | ندارد | fan نمونه؛ P10/P90 واقعی نباید جعل شود |
| risk | `risk()` | `GET /api/risk/overview|assessments`, `POST /analyze`, `/api/scenarios` | `DEMO` | ندارد | ماتریس نمونه؛ API واقعی مصرف نمی‌شود |
| decisions | `decisions()` | `GET /api/decisions`, `/{id}`, `POST /run|from-debate` | `DEMO` | ندارد | شاخهٔ `step6a-risk-forecast-decisions` اتصال دارد ولی merge نشده؛ کورکورانه merge نشود |
| inbox | `inbox()` + `loadInbox` | `GET /api/inbox`, `GET /api/inbox/summary` | `CONNECTED` (commitشده) | Backend موجود | صفحه‌بندی/فیلتر URL؛ جزئیات مقاله و provenance |
| world | `worldMonitorPage()` + `fetchFeed` | `GET /api/geo/events` | `CONNECTED` (commitشده) | Backend موجود | منبع style/tile باید audit شود؛ وضعیت «بدون موقعیت» از metadata خوانده می‌شود؛ clustering/لایه‌ها نیازمند تست |
| geopolitics | `genericDomain` | `GET /api/geopolitics/assessments|tensions`, `POST /analyze` | `GENERIC-DEMO` | ندارد | جدول نمونه؛ نمرات تنش واقعی نمایش داده نمی‌شود |
| iran | `genericDomain` | `GET /api/iran/brief|events|transmission`, `POST /transmission/analyze` | `GENERIC-DEMO` | ندارد | برچسب «درحال‌توسعه» در منو؛ `/events` مصرف نشده |
| macro | `genericDomain` | `GET /api/macro/overview|assessments`, `POST /analyze`, `/api/economic/*` | `GENERIC-DEMO` | ندارد | واحد/دوره/منبع هر مشاهده الزامی است |
| markets | `genericDomain` | `GET /api/markets/symbols|latest|observations`, `POST /fetch` | `GENERIC-DEMO` | ندارد | سوییچ نماد و سری زمانی واقعی نیست |
| portfolio | `genericDomain` | `GET/POST /api/portfolios*`, snapshots | `GENERIC-DEMO` | ندارد | تخصیص/تاریخ ارزش واقعی نیست |
| screening | `screening()` + `loadScreening`/`loadDispatch`/`submitDecision` | `GET /api/screening/queue|summary`, `POST /review/{id}/ack|decision`, `GET /api/dispatch/status` | `CONNECTED` (commitشده) | Backend موجود | برچسب advisory و provenance باید برجسته شود |
| sources | `sources()` + `loadSources`/`loadFunnel`/form/preview | `GET /api/sources`, `/stats`, `GET /api/ingest/stats`, `POST /api/sources`, `POST /{id}/preview|health|recheck`, `PATCH /{id}` | `CONNECTED` (commitشده) | Backend موجود | preview باید غیرمخرب بماند؛ اعتبارسنجی URL/SSRF؛ total/pagination |
| providers | `providers()` + `saveProviderDraft` | `GET /api/ai/providers|status`, `GET/POST /api/settings/providers`, models, test | `DEMO` | ندارد | Draft فقط در `window.__giProviderDraft`؛ هیچ call واقعی/provider catalog load نمی‌شود؛ کلید به‌درستی ذخیره نمی‌شود |
| operations | `operations()` | `GET /api/jobs`, `/api/ops/status|monitoring|metrics`, `/api/dispatch/*` | `DEMO` | ندارد | pipeline/job واقعی نمایش داده نمی‌شود |
| alerts | `genericDomain` | `GET /api/alerts`, `/{id}`, `POST ack|resolve|deliver`, rules CRUD | `GENERIC-DEMO` | ندارد | ۱۰ عملیات Backend بدون UI |
| archive | `archive()` | `GET /api/archive/storage|settings|catalog`, `POST validate|restore/dry-run|restore|purge/preview|telegram/{id}` | `DEMO` | ندارد | auto-purge باید خاموش بماند؛ restore/verify از UI اجرا نمی‌شود |
| reports | `reports()` | `GET /api/briefings`, `/{id}`, `POST daily|weekly`, `/api/audit/log` | `DEMO` | ندارد | تولید/نمایش گزارش واقعی نیست |
| settings | `settings()` | `/api/settings/*` (۲۳ op), `/api/configuration/*` (۱۰ op) | `DEMO` | ندارد | کنترل‌پلین واقعی متصل نیست؛ secrets باید write-only بمانند |

**جمع:** `CONNECTED` = ۴ (inbox, sources, screening, world) · `PARTIAL-UNCOMMITTED` = ۲ · `DEMO` = ۱۲ · `GENERIC-DEMO` = ۷.

---

## 5. قرارداد داده و امنیت

- UI فقط از `api()`/`fetch` به Backend وصل می‌شود؛ دسترسی مستقیم به DB وجود ندارد.
- مسیرهای امنیتی: `access_guard` (نشست/کلید + نقش)، `/health` عمومی، `/api/auth/*` عمومی به‌جز `me/logout`.
- `POST /api/analyses/request` در working tree به `ANALYST_WRITE_PATHS` اضافه شده است (نقش `analyst`).
- هیچ secretی در `index.html` hard-code نشده؛ Draft provider کلید را ذخیره نمی‌کند (`keyConfigured` فقط boolean).
- `ARCHIVE_AUTO_PURGE_ENABLED=false` باید در تمام مراحل دست‌نخورده بماند.
- Mock و Real: نشان `sample`/`دادهٔ نمونه` در HTML وجود دارد، اما به‌صورت خودکار به وضعیت واقعی API گره نخورده؛ ribbon فقط pages متصل را «داده زنده» می‌کند.

---

## 6. Baseline تست و اجرا

| مورد | نتیجه | وضعیت |
|---|---|---|
| Syntax check اسکریپت‌های inline @HEAD `31b4ca4` | ۰ خطا | `VERIFIED` (این ممیزی) |
| Syntax check اسکریپت‌های inline working tree | ۰ خطا (پس از repair) | `VERIFIED` |
| بارگذاری واقعی صفحه (`127.0.0.1:8010` + Chromium) | HTTP 200 · ۲۵ nav · overview رندر · فقط 401 احراز هویت | `VERIFIED` |
| آخرین suite گزارش‌شده (مرحلهٔ ۵، PostgreSQL) | ۱۷۱۹ passed / ۱ skipped | گزارش مالک؛ در این ممیزی اجرا نشد |
| `tests/test_analyses_dashboard.py` (مرحلهٔ ۶A) | اجرا نشده | `NOT_VERIFIED` |
| تست UI/مرورگر | وجود ندارد | `MISSING` |
| `pytest` full | در F00-R طبق قرارداد اجرا نشد | `NOT_RUN` |
| Lint/Typecheck/Build فرانت | stack ندارد | `NOT_APPLICABLE` (gate جایگزین لازم است) |

---

## 7. شکاف‌های باز (به ترتیب اولویت)

1. **BLOCKER-1:** خطای نحوی `backend/static/index.html` — کل UI از کار افتاده؛ باید با diff محدود، snapshot و تست syntax رفع شود.
2. **BLOCKER-2:** مرحلهٔ ۶A (dashboard/analyses) uncommitted و تست‌نشده است؛ بدون تأیید تست نباید «متصل» اعلام شود.
3. **HIGH:** ۱۹ صفحهٔ باقی‌مانده DEMO/GENERIC هستند؛ هیچ‌کدام API واقعی مصرف نمی‌کنند.
4. **HIGH:** بدون deep-link/URL state، refresh و direct navigation قابل اتکا نیست.
5. **HIGH:** صفر تست UI/E2E برای رابط جدید؛ gateهای UX.6/UX.7 نیازمند harness جایگزین هستند.
6. **MEDIUM:** اسناد قبلی (`UI_PAGE_FEATURE_MATRIX`, `UI_HTML_TRACEABILITY_MATRIX`, `UI_LEGACY_FEATURE_MIGRATION`, `UI_FINAL_ACCEPTANCE`) وضعیت React-era را توصیف می‌کنند و باید در UX.0/UX.1 به این سند ارجاع داده شوند؛ سند تکراری ساخته نشود.
7. **MEDIUM:** `4 branch` قدیمی (`replace-ui`, `connect-ui-step0`, `step6a-risk-forecast-decisions`, `ui-gap-analysis`) بررسی‌نشده‌اند؛ merge کورکورانه ممنوع.
8. **LOW:** برچسب «درحال‌توسعه» فقط روی `iran` است؛ سایر صفحات ناقص برچسب ندارند.

---

## 8. قابلیت‌هایی که عمداً بازسازی نمی‌شوند

- ۴۵ router و ۲۰۰+ operation موجود Backend (auth, sources, ingest, dedup, classify, events, claims, graph, geo, screening, dispatch, risk, forecasts, decisions, archive, settings, ops, …).
- سرویس‌های دامنه (`domains/*`)، مدل‌ها، migrationها، dispatch، AI Gateway، local screening، Source Bot.
- MapLibre vendored و CSS/توکن‌های موجود؛ کتابخانه یا design system دوم ساخته نمی‌شود.
- داده‌های `data/labeling/` و فایل مرجع HTML؛ نه حذف، نه جایگزینی.

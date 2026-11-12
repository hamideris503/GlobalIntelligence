# UI Migration Manifest — GlobalIntelligence

**Manifest state:** `CUTOVER_READY` — جابه‌جایی کارکردی انجام شده و `F03.UX.7` **`ACCEPTED`** است بر اساس `docs/qa/UX7_ACCEPTANCE_20261107.md` (تنها منبع حقیقت؛ تصمیم نهایی ۲۰۲۶-۱۱-۱۱). این سند وضعیت مستقل برای UX.7 تعریف نمی‌کند. `F03.UX.8` = **`CLOSED / ACCEPTED`** (۲۰۲۶-۱۱-۱۲): تأیید مالک ثبت شد و حذف `ui-data.js`/`ui-data.css` رسمیت یافت — مرجع واحد: `docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md`. بازگشت از طریق Git ممکن نیست (هر دو فایل untracked بودند)، اما پشتیبان با هش تأییدشده در `backups/legacy_ui_20261112/backend/static/` نگهداری می‌شود و با `python scripts/check_legacy_ui_backup.py` قابل بررسی است.
**Roadmap:** `GlobalIntelligence_Roadmap_v1.8_Protected_UI_Migration_and_Full_Reaudit.md` — **این فایل در repository وجود ندارد**؛ تنها نسخهٔ موجود `docs/GlobalIntelligence_Roadmap_v1.5_Full_Engineering_Spec.md` است و v1.8 فقط به‌صورت پیوست در دسترس بوده است.
**Updated:** ۲۰۲۶-۱۱-۱۲
**Substage:** `F03.UX.6` تکمیل شد؛ `F03.UX.7` = **`ACCEPTED`** (۲۰۲۶-۱۱-۱۱؛ منبع واحد: `docs/qa/UX7_ACCEPTANCE_20261107.md`)؛ `F03.UX.8` = **`CLOSED`** (۲۰۲۶-۱۱-۱۲؛ `docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md`)
**Owner approval for legacy deletion:** ندارد (`none`) — حذف 6A.13 بدون این تأیید انجام شده است

---

## 0. همگام‌سازی ۲۰۲۶-۱۱-۱۲ (مقدم بر بخش‌های ۱ تا ۹)

بخش‌های ۱ تا ۹ عکس لحظه‌ای **۲۰۲۶-۱۱-۰۷** هستند و با checkout فعلی نمی‌خوانند. وضعیت اندازه‌گیری‌شدهٔ امروز:

| مورد | مقدار فعلی |
|---|---|
| Branch / HEAD | `step6a-analysis-dashboard` / `aa5e000` (۵ commit جلوتر از `origin/main`، push‌شده) |
| Staged / Unstaged / Untracked | هیچ / هیچ / هیچ |
| `backend/static/index.html` | **۳۹۳٬۳۷۵ B** · SHA-256 `4c65129759b29900a7fc0ffbb74090273fca01a7b57f79ba75187e285cd78a65` |
| `backend/static/ui-data.js` / `.css` | **وجود ندارند** (حذف 6A.13؛ هرگز tracked نبودند؛ پشتیبان فقط در temp مالک) |
| Container | `gi_backend` با image تازه‌ساخته‌شده روی `127.0.0.1:8000`، `healthy`؛ `/health/db` روی head `c8f2d3e4a5b6` |
| `/ui-data.js`، `/ui-data.css` | **۴۰۴** |
| مرحلهٔ ۶A | analyses/dashboard، روترهای risk/forecast/decision و migration `c8f2d3e4a5b6` اکنون commit شده‌اند |

اختلاف‌های باقی‌مانده (نیازمند تصمیم مالک):

1. ✅ **رفع شد (۲۰۲۶-۱۱-۱۲):** تناقض وضعیت UX.7 برداشته شد؛ `docs/qa/UX7_ACCEPTANCE_20261107.md` تنها منبع حقیقت است و وضعیت `ACCEPTED` دارد. این سند و `STAGE_STATUS.md` وضعیت مستقل تعریف نمی‌کنند.
2. حذف `ui-data.js`/`ui-data.css` بدون تأیید مالک انجام شده و چون untracked بودند مسیر بازگشت در Git ندارد.
3. نسخهٔ v1.8 نقشه‌راه در repository نیست؛ استناد این سند به آن قابل بازتولید نیست.
**`LEGACY_UI_ALLOWLIST`:** خالی و غیرفعال

---

## 1. Snapshot

| مورد | مقدار |
|---|---|
| Repository root | `J:/Documents/GlobalIntelligence` |
| Branch | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` |
| Staged | هیچ |
| Unstaged | `backend/static/index.html`, `backend/auth/deps.py`, `backend/main.py`, routerهای risk/forecast/decision و مدل ریسک |
| Untracked | `backend/static/ui-data.js`, `backend/static/ui-data.css`, `backend/api/routers/analyses.py`, `backend/api/routers/dashboard.py`, `domains/analyses/`, تست‌های مرحلهٔ ۶A/ریسک، migration `c8f2d3e4a5b6` |
| Container | `gi_backend` با image `e1cb5c747cee…`؛ وضعیت `healthy` روی `127.0.0.1:8000` |
| Container assets | `/ui-data.js` = ۲۰۰ (۵۰٬۰۲۴ B)، `/ui-data.css` = ۲۰۰ (۳٬۶۵۲ B) |

### 1.1 Hashهای فعلی UI

| مسیر | SHA-256 | اندازه |
|---|---|---|
| `backend/static/index.html` | `4c65129759b29900a7fc0ffbb74090273fca01a7b57f79ba75187e285cd78a65` | ۳۹۳٬۳۷۵ B |
| ~~`backend/static/ui-data.js`~~ | حذف‌شده در 6A.13 (قبلاً `b0db284f…`، ۵۰٬۰۲۴ B) | ۰ |
| ~~`backend/static/ui-data.css`~~ | حذف‌شده در 6A.13 (قبلاً `363f4f89…`، ۳٬۶۵۲ B) | ۰ |

> هش و اندازهٔ `index.html` بالا مربوط به ۲۰۲۶-۱۱-۱۲ است؛ مقدار قبلی (`f5f57d46…` / ۲۹۳٬۰۳۶ B) منقضی شده و نباید مبنای تأیید قرار گیرد.

`index.html` فقط با patchهای محدود تغییر کرده است: بارگذاری CSS جدید **بعد** از `<style>`، بارگذاری JS جدید، hash routing/404، حذف شمارنده‌های نمونهٔ ناوبری، اصلاح ribbon/هویت API-key، اتصال نقشهٔ جهان به `X-API-Key`، و فراخوانی hook صفحه. هیچ delete/rename/refactor گسترده‌ای انجام نشده است.

---

## 2. طبقه‌بندی فایل‌های UI

| مسیر | کلاس | وضعیت | نقش |
|---|---|---|---|
| `backend/static/index.html` | `NEW_UI_PROTECTED` | modified؛ hash بالا | پوستهٔ اصلی runtime |
| `backend/static/ui-data.js` | `NEW_UI_DATA` | **حذف‌شده** (6A.13، بدون تأیید مالک) | —؛ محتوایش در `index.html` ادغام شده بود |
| `backend/static/ui-data.css` | `NEW_UI_STYLE` | **حذف‌شده** (6A.13، بدون تأیید مالک) | —؛ استایل‌هایش در `index.html` است |
| `backend/static/vendor/maplibre-gl/*` | `SHARED` | tracked/clean | نقشهٔ ۲بعدی |
| `GlobalIntelligence_WorldMonitor_2D_Full_Map.html` | `UI_REFERENCE_PROTECTED` | خارج از repo | مرجع طراحی؛ runtime نیست |
| `apps/web_leftover_locked/` | `UNKNOWN_PROTECTED` | untracked/قفل‌شده | حذف/تغییر ممنوع |
| `data/labeling/*` | `DATA_PROTECTED` | untracked | حذف ممنوع |

---

## 3. «رابط قدیمی» در این checkout

- **Runtime:** `GET /` همان `backend/static/index.html` است؛ این فایل رابط جدید/جاری است. هیچ React/Vite runtime فعالی در tree نیست.
- **Remainderهای تاریخی:** کدهای dormant قدیمی (`executive()`، `genericTable()`، `genericDomain()`، drawer نمونه) در ۲۰۲۶-۱۱-۱۱ حذف شدند و `ui-data.js`/`ui-data.css` هم retired شدند؛ تأیید مالک در ۲۰۲۶-۱۱-۱۲ ثبت شد (STEP 6A.43).
- **شاخه‌ها:** `replace-ui`, `connect-ui-step0`, `step6a-risk-forecast-decisions`, `ui-gap-analysis` بدون merge/reset حذف نشده‌اند.
- **نتیجه (به‌روزشده ۲۰۲۶-۱۱-۱۲):** دو فایل legacy در 6A.13 حذف شده‌اند و با تأیید مالک رسمیت یافته‌اند؛ در همین مرحلهٔ همگام‌سازی هیچ فایلی حذف یا rename نشد و `LEGACY_UI_ALLOWLIST` همچنان خالی است.

---

## 4. Entrypoint و Route

| مورد | وضعیت |
|---|---|
| Root | `/` → `backend/static/index.html`؛ پس از rebuild از کانتینر ۲۰۰ می‌شود |
| Routeهای صفحه | ۲۵ شناسه در `pages`؛ hash routing با `#<page>` |
| Deep-link/refresh | `#risk`، `#macro` و `#world` با reload مستقیم حفظ می‌شوند |
| 404 | `#does-not-exist` → `#not-found` و صفحهٔ اختصاصی ۴۰۴ |
| 403 | مسیر خطای ۴۰۳ در `ui-data.js` وجود دارد؛ در این نوبت با نقش واقعی viewer روی API نوشتن اجرا نشد |
| Auth | `/api/auth/me` حالا `X-API-Key` را هم می‌فرستد؛ کلید نامعتبر → «کلید نامعتبر» + مودال ورود |
| Map | `fetchFeed` حالا `X-API-Key` را می‌فرستد؛ بدون آن فقط ۴۰۱ می‌گرفت |

---

## 5. Stage ledger

| Substage | وضعیت | شاهد |
|---|---|---|
| `F00-R` | `VERIFIED` | ممیزی read-only قبلی |
| `F03.UX.0` | `VERIFIED` | manifest + inventory |
| `F03.UX.1` | `VERIFIED` | ترتیب صحیح `ui-data.css` پس از `<style>`؛ حذف footerهای ۸–۱۰px از مسیرهای فعال؛ focus-visible |
| `F03.UX.2` | `VERIFIED` | hash routing، reload مستقیم، ۴۰۴، حالت ۴۰۱، نقش viewer |
| `F03.UX.3` | `VERIFIED` | ۲۵/۲۵ مسیر؛ ۱۹ renderer جدید + ۶ صفحهٔ قدیمی متصل؛ همه با دادهٔ زنده/empty state |
| `F03.UX.4` | `PARTIAL` | World Monitor: ۴۰ عارضهٔ دارای مختصات + ۴۶۳ بدون موقعیت؛ tile/style خارجی (OpenFreeMap) در دسترس؛ سناریوی offline تست نشد |
| `F03.UX.5` | `PARTIAL` | Provider/Archive/Settings/Alerts و فرم Sources بارگذاری شدند؛ همهٔ عملیات نوشتن تست نشد |
| `F03.UX.6` | `VERIFIED` | ۳۹۰px بدون overflow افقی (scrollWidth ۳۷۳ < ۳۹۰)، منوی موبایل، حداقل فونت ۱۱px، focus ring؛ ممیزی WCAG رسمی انجام نشد |
| `F03.UX.7` | `ACCEPTED` | چهار P0 (Inbox provenance، Provider control، Operations timeline، Archive verify/restore) در ۲۰۲۶-۱۱-۱۱ بسته شدند — مرجع واحد: `docs/qa/UX7_ACCEPTANCE_20261107.md` |
| `F03.UX.8` | `CLOSED / ACCEPTED` | تأیید مالک در ۲۰۲۶-۱۱-۱۲؛ محدودهٔ exact + هش‌ها در `docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md` |

---

## 6. شواهد این نوبت

| بررسی | نتیجه |
|---|---|
| `node --check backend/static/ui-data.js` | ✅ exit 0 |
| Parse چهار اسکریپت inline `index.html` | ✅ exit 0 |
| `ruff check backend domains tests scripts source_bot` | ✅ `All checks passed!` |
| `pytest tests/test_risk_forecast_decisions.py tests/test_analyses_dashboard.py -q` | ✅ **۲۶ passed** |
| مرورگر واقعی روی `127.0.0.1:8010` | ✅ ۲۵ مسیر، ribbon «داده زنده»، بدون خطای کنسول در دو batch |
| APIهای ۲۵ صفحه | ✅ همهٔ درخواست‌های اصلی ۲۰۰؛ `macro` با `country=IR` از ۴۲۲ به ۲۰۰ رسید |
| World Monitor | ✅ ۴۰ feature + ۴۶۳ without_location؛ نقشه و sprite/font tiles بارگذاری شدند |
| حالت کلید نامعتبر | ✅ ۴۰۱، پیام ورود، مودال و tag «خطا»؛ سپس کلید معتبر بازگردانده شد |
| نقش viewer | ✅ دکمه‌های approve/reject/evidence و «اجرای تصمیم‌سازی» پنهان شدند |
| Deep-link/404 | ✅ `#does-not-exist` → صفحهٔ `not-found` |
| Responsive ۳۹۰px | ✅ `scrollWidth=373`، منوی موبایل باز شد، فونت زیر ۱۱px در محتوای فعال باقی نماند |
| Container rebuild | ✅ image جدید ساخته شد؛ `gi_backend` healthy؛ `/`, `/ui-data.js`, `/ui-data.css`, `/health` = ۲۰۰ |
| Full suite / PostgreSQL | ❌ در این نوبت اجرا نشد؛ فقط تست‌های هدفمند |
| CI / push / commit | ❌ انجام نشد؛ تغیيرات uncommitted باقی مانده‌اند |

### 6.1 محدودیت‌های صریح

1. این تأیید روی SQLite/uvicorn محلی و smoke کانتینر است؛ suite کامل PostgreSQL و CI اجرا نشده است.
2. عملیات نوشتن (Provider save، Archive restore/purge، Alert ack/resolve، Decision review واقعی) به‌صورت end-to-end تست نشده‌اند.
3. ۴۰۳ واقعی با نقش API-limited تست نشد؛ فقط گیت UI نقش viewer بررسی شد.
4. تأیید بصری کامل/WCAG formal انجام نشد؛ بررسی‌ها DOM/computed-style/network-based هستند.
5. World Monitor به style/tile خارجی OpenFreeMap وابسته است؛ رفتار offline/custom endpoint تست نشده است.
6. ~~هیچ فایل legacy حذف نشد و تأیید مالک برای UX.8 وجود ندارد.~~ **به‌روزشده:** دو فایل legacy حذف شدند و تأیید مالک در ۲۰۲۶-۱۱-۱۲ ثبت شد (STEP 6A.43).

---

## 7. Cutover و Rollback

- **وضعیت cutover:** `CUTOVER_READY` — root همان رابط جدید را سرو می‌کند؛ ۲۵ مسیر بازبینی شد و چهار P0 UX.7 در ۲۰۲۶-۱۱-۱۱ بسته شدند (منبع: `docs/qa/UX7_ACCEPTANCE_20261107.md`). `F03.UX.8` نیز در ۲۰۲۶-۱۱-۱۲ بسته شد (STEP 6A.43)؛ هیچ blocker پذیرشی باقی نیست.
- **Rollback:** نسخهٔ commitشدهٔ `31b4ca4:backend/static/index.html` و image قبلی `9381e66152f3` / `f160a1ee7325` در دسترس‌اند.
- **UX.8:** بسته شد. فهرست exact + SHA-256 + تأیید مالک در STEP 6A.43 ثبت است؛ `LEGACY_UI_ALLOWLIST` خالی می‌ماند و حذف بیشتر ممنوع است.

---

## 8. ریسک‌ها و قواعد فعال

1. `NEW_UI_PROTECTED` فقط با patch محدود و hash قبل/بعد تغییر کرده است.
2. `data/labeling/`، `backups/` و `apps/web_leftover_locked/` دست‌نخورده‌اند.
3. Auto-purge خاموش مانده است؛ هیچ عملیات حذف خودکار فعال نشد.
4. Mock/Real در UI تفکیک شده‌اند؛ صفحات بدون داده، empty state صادقانه نشان می‌دهند.
5. اسناد React-era تاریخی‌اند؛ این manifest مرجع وضعیت فعلی است.

---

## 9. گام بعدی

1. چهار P0 گزارش `docs/qa/UX7_ACCEPTANCE_20261107.md` رفع و تست شوند؛ سپس پذیرش UX.7 دوباره ثبت شود.
2. تصمیم دربارهٔ `F03.UX.4` (منبع tile/offline) و `F03.UX.5` (عملیات نوشتن) گرفته شود.
3. `F03.UX.8` ✅ بسته شد (۲۰۲۶-۱۱-۱۲). مرحلهٔ بعد: موارد P1 UX.7 (فعال‌سازی E2E منبع، visual regression، Core Web Vitals).

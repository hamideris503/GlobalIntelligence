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

---

# 10. همگام‌سازی Roadmap v2.2 — WP-03 (۲۰۲۶-۱۱-۱۴)

این بخش در ادامهٔ بخش‌های ۱ تا ۹ اضافه شده و جایگزین آن‌ها نیست. منبع: استخراج ایستا از `backend/static/index.html` (HEAD `2d0e1bc`) و تطبیق با route table واقعی `create_app().routes`. هیچ فایل UI تغییر نکرد.

**تاریخ:** ۱۴ نوامبر ۲۰۲۶ · **Branch:** `step6a-analysis-dashboard` · **HEAD:** `2d0e1bc768ecbedde9dc58a91ef914e1e6a5be97`
**روش:** استخراج ایستا از کد واقعی (`backend/static/index.html`) + تطبیق با route table واقعی FastAPI (`create_app().routes`). هیچ فایل UI تغییر نکرد؛ هیچ درخواست شبکه‌ای برای این inventory اجرا نشد.

---

## 1. فایل‌های UI کشف‌شده (با SHA-256)

| # | مسیر | بایت | SHA-256 | دسته | وضعیت Git | مصرف‌کننده |
|---|---|---:|---|---|---|---|
| 1 | `backend/static/index.html` | 468,087 | `a00a181e4783d9abb319440a0ca3d758b5e25c00f0e2d0a520b7b0c300cb2b8a` | `NEW_UI_PROTECTED` | tracked (Modified) | تنها UI اجرایی؛ FastAPI در `/` سرو می‌کند |
| 2 | `backend/static/vendor/maplibre-gl/maplibre-gl.js` | 937,395 | `1525f971223d81f169f049f1ce50083e6f1643aa6b0ea0716653a550d2d57fc2` | `SHARED` (asset ثالث) | tracked | نقشهٔ `world` |
| 3 | `backend/static/vendor/maplibre-gl/maplibre-gl.css` | 69,430 | `43c1d886b5fdf0aac4e7135bd6f84b823d9f48283a648012665f9be52c01389f` | `SHARED` (asset ثالث) | tracked | نقشهٔ `world` |
| 4 | `.tmp-ui/index.before.html` | 381,403 | `6ed721c59feb921e7407955c832d1c15d211e0b2b1ca3baa98e993737a404f79` | `WORK_DIR_SNAPSHOT` | gitignored (`.tmp-*/`) | snapshot کاری مالک — **حفظ می‌شود** |
| 5 | `.tmp-ui/{patch_ui.py, router.txt, region.txt}` | — | — | `WORK_DIR_SCRATCH` | gitignored | ابزار پچ موقت مالک |
| 6 | `backups/ui-index-before-syntax-fix-20261106.html` | 299,175 | `74caa69728a61773353dd7cf6eb75066355d4c682dbc5464a907492e4d9d6344` | `BACKUP_SNAPSHOT` | gitignored | rollback تاریخی |
| 7 | `backups/roadmap_v22/wp01_snapshot_20261114/backend__static__index.html` | — | در `manifest.json` همان پوشه | `WP01_SNAPSHOT` | gitignored | rollback WP-01 |
| 8 | `tests/e2e/{routes,smoke,axe}.spec.js` + `global-setup.js` | — | — | `TEST_FIXTURE` | tracked | Playwright (خارج از CI) |
| 9 | `docs/graphify-out/graph.html` | 2,616,556 | `0a9bfafd7b9affd53e1412c0fa3b02ae0fc0bd5811e459603a5179a4b4834fa0` | `GENERATED_ARTIFACT` | generated | خروجی graphify؛ UI نیست |
| 10 | `apps/web_leftover_locked/` | — | — | `LEGACY_PLACEHOLDER` (خالی) | tracked | هیچ consumer ندارد |
| 11 | `ui-data.js`, `ui-data.css` | — | مرجع هش در `check_legacy_ui_backup.py` | `RETIRED_LEGACY` | **absent** | guard: exit 0 |

**تصمیم‌ها:** هیچ فایلی حذف یا بازنویسی نشد. موارد 1–3 و 8 محافظت‌شده‌اند. مورد 4 snapshot مالک است و در `.gitignore` قرار دارد. مورد 11 طبق F03.UX.8 حذف‌شده و برنگشته (با اجرای `--live-only` در همین نوبت تأیید شد).

## 2. فایل‌های مرجع که پیدا نشدند (§1 نقشه‌راه)

| مورد انتظار | نتیجه |
|---|---|
| `GlobalIntelligence_Roadmap_v1.9_Auth_UI_Animated_and_Security_Completion` | **NOT_FOUND** — در repo و `docs/` هیچ فایلی با الگوی `*v1.9*` نیست. محتوای آن حدس زده نشد. |
| HTML مرجع Auth انیمیشنی مالک | **NOT_FOUND** — تنها HTMLهای موجود: UI زنده، دو snapshot، و artifact گراف. |
| HTML مرجع WorldMonitor/Map | **NOT_FOUND** (نسخهٔ اجرایی همان `worldMonitorPage()` داخل `index.html` است). |
| بررسی `H:\GIRuntime` | فقط `kev-source`, `kev-venv`, `laya-venv`, `labeling`, `logs`, `model-cache`, `pip-cache`, `python`, `uv-cache` — هیچ HTML/design file. |

⇒ WP-03.3 (انتقال طراحی از Reference HTML مالک) در حال حاضر **قابل اجرا نیست**؛ تنها منبع طراحی، خود `index.html` است. این وضعیت `BLOCKED_OWNER_REFERENCE_NOT_FOUND` ثبت می‌شود، نه یک فرض.

## 3. ماتریس صفحه → API (۲۵ صفحهٔ واقعی)

ناوبری: `data-page` + `renderPage(id)` با `const pages = {…}` (۲۵ کلید) — **بدون** hash/URL، بدون deep-link، بدون back/forward.

| page_id | تعداد endpoint | endpointهای متصل (واقعی) | Auth | وضعیت | gap |
|---|---:|---|---|---|---|
| overview | 1 | `GET /api/dashboard/overview` | session | `IMPLEMENTED_NOT_ACCEPTED` | KPI runtime تأیید نشده |
| ai-analysis | 2 | `GET /api/analyses?page=1&page_size=100`, `GET /api/classify/articles/` | session | `IMPLEMENTED_NOT_ACCEPTED` | اجرای تحلیل از UI مبهم |
| ai-chat | 2 | `GET /api/ai/status`, `POST /api/ai/chat` | session | `IMPLEMENTED_NOT_ACCEPTED` | usage/history نمایش داده نمی‌شود |
| debate | 1 | `GET /api/debate/runs` | session | `IMPLEMENTED_NOT_ACCEPTED` | فقط خواندن run؛ اجرای Debate از UI نیست |
| evaluation | 3 | `GET /api/evaluation/summary`, `GET /api/evaluation/scores`, `POST /api/evaluation/run` | session | `IMPLEMENTED_NOT_ACCEPTED` | dataset/version انتخاب نمی‌شود |
| evidence | 1 | `GET /api/claims` | session | `IMPLEMENTED_NOT_ACCEPTED` | شواهد موافق/مخالف و verification status نیست |
| entity-graph | 2 | `GET /api/graph/entities`, `GET /api/graph/relationships` | session | `IMPLEMENTED_NOT_ACCEPTED` | lineage/node detail ندارد |
| forecasts | 2 | `GET /api/forecasts/outlook?target=`, `POST /api/forecasts/run?target=` | session | `IMPLEMENTED_NOT_ACCEPTED` | outcome/uncertainty کامل نیست |
| risk | 3 | `GET /api/risk/overview`, `GET /api/risk/matrix`, `POST /api/risk/analyze` | session | `IMPLEMENTED_NOT_ACCEPTED` | `NO_DATA` صریح ندارد |
| decisions | 3 | `GET /api/decisions?limit=50`, `POST /api/decisions/`, `POST /api/decisions/run` | session | `IMPLEMENTED_NOT_ACCEPTED` | approval state ندارد |
| inbox | 2 | `GET /api/inbox?`, `GET /api/inbox/summary` | session | `IMPLEMENTED_NOT_ACCEPTED` | pagination سمت سرور نامشخص |
| world | 2 (raw `fetch`, نه `api()`) | `GET /api/geo/events` (GeoJSON), `GET /api/world-state/history?limit=500` | session + `X-API-Key` اختیاری | `IMPLEMENTED_NOT_ACCEPTED` | نقشه تا دریافت فید واقعی فقط دادهٔ خالی نشان می‌دهد (`wmConnectionStatus` = «بدون فید رویداد») |
| geopolitics | 3 | `GET /api/geopolitics/assessments`, `GET /api/geopolitics/tensions`, `POST /api/geopolitics/analyze` | session | `IMPLEMENTED_NOT_ACCEPTED` | پیوند Source/Event/Entity ندارد |
| iran | 1 | `GET /api/iran/brief` | session | `IMPLEMENTED_NOT_ACCEPTED` | Country Profile عمومی نیست (WP-14) |
| macro | 3 | `GET /api/macro/overview`, `GET /api/macro/assessments`, `POST /api/macro/analyze` | session | `IMPLEMENTED_NOT_ACCEPTED` | unit/period/source نمایش داده نمی‌شود |
| markets | 1 | `GET /api/markets/latest` | session | `IMPLEMENTED_NOT_ACCEPTED` | freshness/timestamp ندارد |
| portfolio | 5 | `GET/POST /api/portfolios`, `GET/POST/DELETE /api/portfolios/{id}` | session | `IMPLEMENTED_NOT_ACCEPTED` | فرض‌های ریسک در UI نیست |
| screening | 3 | `GET /api/screening/summary`, `GET /api/screening/queue`, `POST /api/screening/review/{id}` | session | `IMPLEMENTED_NOT_ACCEPTED` | provenance/human review display |
| sources | 6 | `GET /api/sources`, `GET /api/sources/stats`, `GET/POST/PATCH /api/sources/{id}`, `POST /api/sources` | session | `IMPLEMENTED_NOT_ACCEPTED` | wizard/validate/preview ندارد |
| providers | 0 اختصاصی | از `GET/POST/PUT /api/settings/providers*` و `catalog` استفاده می‌کند | session | `IMPLEMENTED_NOT_ACCEPTED` | گیت Admin ندارد (GI-SEC-001) |
| operations | 7 | `GET /api/ops/status`, `/api/dispatch/{status,jobs,articles}`, `GET /api/jobs`, `POST /api/dispatch/{recover,run}` | session | `IMPLEMENTED_NOT_ACCEPTED` | retry/pause/cancel با audit ندارد |
| alerts | 3 | `GET /api/alerts`, `POST /api/alerts/{id}/…`, `POST /api/alerts/test-deliver/{channel}` | session | `IMPLEMENTED_NOT_ACCEPTED` | test-deliver گیت Admin ندارد (GI-SEC-001) |
| archive | 7 | `GET /api/archive/{catalog,storage,purge/preview}`, `POST /api/archive/{build,restore,restore/dry-run,…}` | session | `IMPLEMENTED_NOT_ACCEPTED` | restore به sandbox اثبات نشده |
| reports | 2 | `GET /api/briefings`, `GET /api/briefings/{id}` | session | `IMPLEMENTED_NOT_ACCEPTED` | دوره/نسخهٔ داده در UI نیست |
| settings | 9 | `GET /api/settings/{app,models,providers,providers/catalog}`, `POST /api/settings/import-from-env`, `POST/PUT /api/settings/providers*`, key/verify/test | session | `IMPLEMENTED_NOT_ACCEPTED` | تمام عملیات حساس بدون گیت Admin (GI-SEC-001) |

### نتیجهٔ تطبیق

| سنجه | مقدار |
|---|---:|
| `api('…')` callsite در UI | **92** |
| endpoint یکتای `api()` | **82** |
| endpoint خام `fetch()` (نقشه/Auth) | **3**: `/api/auth/me`, `/api/geo/events`, `/api/world-state/history` |
| بدون route متناظر در FastAPI (بین همهٔ ۸۵ مورد) | **0** |
| callsite مشترک (Auth/Events) | 10 (`/api/auth/*`, `GET /api/events`, `GET /api/ingest/stats`) |
| route ثبت‌شده در app | 240 |

**تعداد صفحه:** رجیستری `pages` دقیقاً **۲۵** کلید دارد؛ ۲۴ تابع render با الگوی `function x(){return \`` به‌علاوهٔ `worldMonitorPage()` که تابع صفحه است ولی با الگوی بالا match نمی‌شود. دو تابع `evidenceFlow` و `miniNetwork` کامپوننت مشترک‌اند، نه صفحه — بنابراین عدد واقعی ۲۵ است و شمارش خام ۲۶ گمراه‌کننده است.

هیچ callsite مرده‌ای وجود ندارد: هر ۸۲ فراخوانی در route table واقعی resolve شد (این یک بررسی **کد** است، نه اثبات Runtime).

## 4. شکاف‌های ثبت‌شده

| ID | شکاف | شاهد |
|---|---|---|
| `GI-UI-001` | ~~ناوبری بدون URL/deep-link~~ **رفع شد (WP-05.1):** `renderPage` اکنون با `giSyncUrl` آدرس را به `#/<page>` می‌برد، `popstate` برای back/forward گوش می‌دهد، `giPageFromHash` فقط صفحه‌های رجیستری را می‌پذیرد و بارگذاری اولیه به‌جای `overview` همان deep-link را باز می‌کند. قفل تست: `tests/test_ui_routing_contract.py`. | `backend/static/index.html` (helpers پیش از `renderPage`), ۴ callsite به‌روزشده |
| `GI-UI-001a` | تناقض مستند/کد: بخش ۱ همین سند (۲۰۲۶-۱۱-۱۲) از «hash routing/404» به‌عنوان patch اعمال‌شده یاد می‌کند، اما در `HEAD:backend/static/index.html`، فایل زندهٔ فعلی و snapshot ۲۰۲۶-۱۱-۰۶ هیچ `location.hash`/`hashchange` وجود ندارد | `grep -c` = 0 در هر سه نسخه |
| `GI-UI-002` | ~~نبود stateهای استاندارد در ۲۵ صفحه~~ **صورت‌مسئله اصلاح شد (WP-05.1):** شمارش ۶/۱/۲ فقط مصرف helperهای مشترک را می‌سنجید؛ در واقع ۳۴ loader تابع `loadX` دارند و ۳۳ موردشان try/catch و پیام خالی/خطای فارسی دارند (`loadInboxDetail` با `Promise.allSettled` و `giErrorHtml` خودش خطا را مدیریت می‌کند). شکاف واقعی، استفادهٔ ناهمگون از helper مشترک است، نه نبود state. | `grep -c 'async function load'` = 34؛ بازرسی بدنهٔ همهٔ loaderها |
| `GI-UI-003` | صفحهٔ `world` تابع `worldMonitorPage()` دارد و به‌جای helper یکسان `api()` از `fetch` خام با GeoJSON استفاده می‌کند (استثنای توجیه‌پذیر، اما inventory خودکار را گمراه می‌کند) | `index.html:3026`, `:3054` |
| `GI-UI-004` | صفحهٔ `providers` endpoint اختصاصی ندارد و کاملاً به `settings` وابسته است (خوب یا بد: تصمیم مالک لازم) | `index.html:1971-2079` |
| `GI-UI-005` | ۵ دکمهٔ `data-action` بدون handler (`debate`, `analysis`, `void`, `ack`, `filter`) — **رفع شد (WP-05.2):** سه مورد به API واقعی وصل، دو مورد صریحاً `disabled`/`NOT_CONNECTED` شدند؛ تست `test_no_dead_data_actions` از بازگشت آن جلوگیری می‌کند | `tests/test_ui_routing_contract.py`، `tests/e2e/deeplink.spec.js` |
| `GI-UI-006` | ~~صفحهٔ تنظیمات هیچ رابطی برای Configuration Control Plane نداشت~~ **رفع شد (WP-06):** بخش «Configuration Control Plane» با تعریف‌ها، نمونه‌ها و چرخهٔ Draft→Validate→Test→Activate→Rollback؛ همچنین گروه‌های بدون adapter با `NEEDS_ADAPTER` و دلیل، و اصلاح باگ رندر بخش Alert Channels که بعد از `innerHTML` ساخته می‌شد و هرگز دیده نمی‌شد. | `backend/static/index.html`، `tests/e2e/configuration.spec.js`، `tests/test_config_control_plane.py` |
| `GI-SEC-001` | ~~هیچ endpoint نقشی را enforce نمی‌کند~~ **ابطال شد (WP-04، ۲۰۲۶-۱۱-۱۴):** RBAC واقعی و سراسری وجود دارد — `access_guard` روی ۵۱ router (همه جز `health` و `auth`) + `required_role(method, path)`. ادعای قبلی بر پایهٔ grep ناقص (`role ==`/`require_admin`) بود و غلط است. نباید مبنای هیچ تصمیمی قرار گیرد. | `backend/auth/deps.py:105-140`, `backend/main.py` (`protected = [Depends(access_guard)]`), `tests/test_permission_matrix_doc.py` |
| `GI-SEC-002` | ~~گیت Admin ندارد~~ **ابطال شد (بازبینی ۲۰۲۶-۱۱-۱۴):** گیت Admin از طریق `access_guard` + `required_role` اعمال می‌شود؛ این مسیر در `ANALYST_WRITE_PATHS` نیست و `required_role("POST", "/api/alerts/test-deliver/email") == "admin"` است (پیش‌فرض `dry_run=True` هم دست‌نخورده). ادعای قبلی از جست‌وجوی decorator اختصاصی آمده بود. | `backend/auth/deps.py:95-103`، `docs/ROLE_MATRIX.md:82`، `tests/test_doc_claims.py::test_test_deliver_requires_admin` |

## 5. پذیرش WP-03

| معیار | نتیجه |
|---|---|
| همهٔ صفحات فعلی Inventory شده‌اند | PASS — ۲۵ صفحهٔ ثبت‌شده + ۲۶ page function |
| Reference HTMLهای مالک حفظ شده‌اند | PASS — هیچ فایلی حذف/بازنویسی نشد؛ Reference یافت‌نشده به‌صورت شفاف ثبت شد |
| هر صفحه API/permission/status/gap دارد | PASS — ماتریس §3 |
| مسیر اصلی UI و مسیر Legacy مشخص‌اند | PASS — `index.html` = مسیر اجرایی؛ `ui-data.*` = بازنشسته و غایب |
| هیچ فایل UI محافظت‌شده حذف/overwrite نشده | PASS |
| WP-03.3 (انتقال Design Reference) | `BLOCKED_OWNER_REFERENCE_NOT_FOUND` |

## 6. زیرمرحلهٔ بعدی

**WP-04.1/WP-04.2 — Auth audit و سیاست حساب‌ها:** با توجه به `GI-SEC-001`، اول باید permission matrix واقعی (anonymous / verified / unverified / viewer / admin) از کد استخراج و سپس حداقل گیت Admin برای عملیات حساس اضافه شود؛ بدون آن هیچ صفحهٔ مدیریتی «امن» نیست.

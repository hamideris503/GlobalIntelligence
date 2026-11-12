# UI Migration Manifest — GlobalIntelligence

**Manifest state:** `CUTOVER_READY_ACCEPTANCE_WITHHELD` — جایگزینی کارکردی انجام شده؛ پذیرش UX.7 به دلیل شکاف‌های P0 نگه داشته شده و حذف legacy انجام نشده است
**Roadmap:** `GlobalIntelligence_Roadmap_v1.8_Protected_UI_Migration_and_Full_Reaudit.md`
**Updated:** ۲۰۲۶-۱۱-۰۷
**Substage:** `F03.UX.6` تکمیل شد؛ `F03.UX.7` بازبینی شد اما `ACCEPTANCE_WITHHELD` است؛ `F03.UX.8` همچنان مسدود
**Owner approval for legacy deletion:** ندارد (`none`)
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
| `backend/static/index.html` | `f5f57d4630433fcf61401df8cbf88482ca025b955bd35afe31b80a03f5d92fd5` | ۲۹۳٬۰۳۶ B |
| `backend/static/ui-data.js` | `b0db284faf5a2c222e18cd3f3d6dd33025155ecd3643b584cb3d0a6d9a97426e` | ۵۰٬۰۲۴ B |
| `backend/static/ui-data.css` | `363f4f89d185040c8fce39d09c12ff4df15e3e883b87b5ea8c9415a3df1beb5d` | ۳٬۶۵۲ B |

`index.html` فقط با patchهای محدود تغییر کرده است: بارگذاری CSS جدید **بعد** از `<style>`، بارگذاری JS جدید، hash routing/404، حذف شمارنده‌های نمونهٔ ناوبری، اصلاح ribbon/هویت API-key، اتصال نقشهٔ جهان به `X-API-Key`، و فراخوانی hook صفحه. هیچ delete/rename/refactor گسترده‌ای انجام نشده است.

---

## 2. طبقه‌بندی فایل‌های UI

| مسیر | کلاس | وضعیت | نقش |
|---|---|---|---|
| `backend/static/index.html` | `NEW_UI_PROTECTED` | modified؛ hash بالا | پوستهٔ اصلی runtime |
| `backend/static/ui-data.js` | `NEW_UI_DATA` | untracked؛ hash بالا | داده/رندر ۱۹ صفحهٔ جدید + hook/ribbon/routing |
| `backend/static/ui-data.css` | `NEW_UI_STYLE` | untracked؛ hash بالا | responsive، فوکوس، جدول‌ها، حداقل فونت |
| `backend/static/vendor/maplibre-gl/*` | `SHARED` | tracked/clean | نقشهٔ ۲بعدی |
| `GlobalIntelligence_WorldMonitor_2D_Full_Map.html` | `UI_REFERENCE_PROTECTED` | خارج از repo | مرجع طراحی؛ runtime نیست |
| `apps/web_leftover_locked/` | `UNKNOWN_PROTECTED` | untracked/قفل‌شده | حذف/تغییر ممنوع |
| `data/labeling/*` | `DATA_PROTECTED` | untracked | حذف ممنوع |

---

## 3. «رابط قدیمی» در این checkout

- **Runtime:** `GET /` همان `backend/static/index.html` است؛ این فایل رابط جدید/جاری است. هیچ React/Vite runtime فعالی در tree نیست.
- **Remainderهای تاریخی:** چند تابع و markup قدیمی داخل همان فایل (مثل `executive()`، `genericTable()`، drawer نمونه) باقی مانده‌اند؛ اما مسیرهای ۲۵گانهٔ فعال به آن‌ها render نمی‌کنند. حذف آن‌ها در `F03.UX.8` و فقط با فهرست exact + تأیید مالک انجام می‌شود.
- **شاخه‌ها:** `replace-ui`, `connect-ui-step0`, `step6a-risk-forecast-decisions`, `ui-gap-analysis` بدون merge/reset حذف نشده‌اند.
- **نتیجه:** هیچ فایلی در این نوبت حذف یا rename نشد؛ `LEGACY_UI_ALLOWLIST` خالی است.

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
| `F03.UX.7` | `ACCEPTANCE_WITHHELD` | بازبینی ۲۵ مسیر ثبت شد؛ چهار P0 باز است: Inbox provenance، Provider control، Operations timeline، Archive verify/restore — `docs/qa/UX7_ACCEPTANCE_20261107.md` |
| `F03.UX.8` | `BLOCKED` | فهرست exact legacy، hashها و تأیید صریح مالک وجود ندارد |

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
6. هیچ فایل legacy حذف نشد و تأیید مالک برای UX.8 وجود ندارد.

---

## 7. Cutover و Rollback

- **وضعیت cutover:** `CUTOVER_READY_ACCEPTANCE_WITHHELD` — root از قبل همان رابط جدید را سرو می‌کند و کانتینر با image جدید بازسازی شد؛ بازبینی ۲۵ مسیر انجام شد اما چهار P0 مانع پذیرش UX.7 هستند.
- **Rollback:** نسخهٔ commitشدهٔ `31b4ca4:backend/static/index.html` و image قبلی `9381e66152f3` / `f160a1ee7325` در دسترس‌اند.
- **UX.8:** فقط پس از تأیید مالک، فهرست exact path + SHA-256 + commit مبنا ارائه می‌شود؛ سپس `LEGACY_UI_ALLOWLIST` و حذف مرحله‌ای. در این نوبت هیچ حذفی انجام نشد.

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
3. برای `F03.UX.8` فهرست exact مسیرهای legacy + SHA-256 + commit مبنا آماده و **پس از تأیید صریح** حذف شود.

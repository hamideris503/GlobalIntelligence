# GlobalIntelligence — Comprehensive Technical Audit & Project Status Report

**تاریخ ممیزی:** ۲۰۲۶-۱۱-۱۲ (۱۲ نوامبر ۲۰۲۶)
**نوع ممیزی:** فقط‌خواندنی (Read-Only) — هیچ فایل، کد، سند، migration، تنظیمات، داده یا وضعیت Git تغییر نکرد
**شاخه:** `step6a-analysis-dashboard` · **HEAD:** `31b4ca4c662e215931781451605609e505a257e2`
**مبنای نقشه‌راه:** `GlobalIntelligence_Roadmap_v1.8_Protected_UI_Migration_and_Full_Reaudit.md` (پیوست، ۲۵۴٬۸۷۵ نویسه — کامل خوانده شد)
**محیط:** Windows، Git Bash، Python 3.14.4 (`.venv`)، Node v24.16.0، Docker Desktop با ۷ کانتینر در حال اجرا

> این گزارش بر پایهٔ **checkout محلی، اجرای واقعی دستورها و queryهای فقط‌خواندنی روی دیتابیس واقعی** نوشته شده است، نه بر پایهٔ گزارش‌های قبلی. هرجا شاهد مستقل نداشته‌ام، صریحاً `NOT VERIFIED` یا `UNKNOWN` علامت خورده است.

---

## بخش A — خلاصه مدیریتی

### A.1 وضعیت کلی

GlobalIntelligence یک **پروژهٔ واقعی و بزرگ** است، نه یک اسکلت: ۴۶٬۷۸۵ خط پایتون در `backend/` (۲۰٬۳۷۳)، `domains/` (۱۹٬۵۷۵) و `source_bot/` (۳٬۲۷۶)، ۵۲ روتر FastAPI با ۲۲۰ عملیات HTTP، ۴۱ فایل مدل، ۵۳ جدول در PostgreSQL 16، ۴۹ migration، و ۱۴۷ فایل تست با **۱٬۷۶۴ تست پاس و ۰ ناموفق** (اندازه‌گیری همین ممیزی). رابط کاربری یک فایل HTML تک‌فایلی ۳۹۱٬۷۵۹ بایتی است که در ۲۵ صفحه به API واقعی وصل شده و ۸۵ فراخوانی `api()` دارد.

در همان حال، پروژه در وضعیت **کارِ نیمه‌تمام و commit‌نشده** قرار دارد و چند قابلیت کلیدی «کد دارد ولی داده/عملکرد واقعی ندارد». مهم‌ترین یافتهٔ این ممیزی این است:

> **۷۱۱ ردیف از ۷۱۱ ردیف `article_dispatches` در دیتابیس واقعی وضعیت `terminal` دارند و صفر ردیف `completed`.** علت ثبت‌شده: `max attempts reached: screening unavailable: LOCAL…`. یعنی مسیر بادوام dispatch در محیط فعلی هیچ کار تحلیلی را با موفقیت به پایان نرسانده است.

### A.2 وضعیت Branch و Commit

| مورد | مقدار |
|---|---|
| Branch جاری | `step6a-analysis-dashboard` |
| HEAD | `31b4ca4c662e215931781451605609e505a257e2` — `feat(inbox): real inbox, screening queue and human decisions (stage 5)` — ۲۰۲۶-۱۱-۰۶ |
| رابطه با `main` | دقیقاً همان commit (`0 / 0`) |
| رابطه با `origin/main` | **۱ commit جلوتر** (`31b4ca4` هنوز push نشده) |
| فایل‌های tracked تغییر‌یافته | ۱۵ فایل (+۲٬۴۷۱ / −۱۷۳ خط) |
| فایل‌های staged | ۰ |
| فایل‌های untracked | ۶۶ فایل |
| تعداد branch محلی | ۱۸ |

### A.3 نسخهٔ نقشه‌راه مبنا

نقشه‌راه v1.8 **در Repository وجود ندارد**؛ تنها نسخهٔ موجود در repo فایل `docs/GlobalIntelligence_Roadmap_v1.5_Full_Engineering_Spec.md` است. v1.8 فقط به‌صورت پیوست در اختیار این ممیزی قرار گرفت و کامل خوانده شد (F00–F16، F03.UX.0–.8، F03.0، F03.1، پیوست‌های UX/Configuration/Source Management، بخش‌های ۱ تا ۳۱). این یک شکاف قابل‌توجه است، چون خود نقشه‌راه در §۳۰.۱ می‌گوید فایل باید در workspace قابل خواندن باشد.

### A.4 وضعیت معماری

معماری **modular monolith** واقعاً رعایت شده است: `backend/api/routers/` فقط لایهٔ HTTP، `domains/*` منطق دامنه، `backend/ai/*` لایهٔ AI (Gateway، Free Policy، Providerها، dispatch، screening محلی)، `source_bot/` دریافت داده. وابستگی‌ها یک‌طرفه‌اند و چرخهٔ واردات معیوبی مشاهده نشد. نقاط ضعف: `workers/` و `backend/services/` خالی‌اند (placeholder)، `domains/entities/` کاملاً خالی است، و مرز مالکیت ingest بین `source_bot/` و `domains/news/` در مستندات روشن نیست.

### A.5 وضعیت Backend

بالغ و قابل دفاع. ۲۲۰ endpoint با schemaهای Pydantic، خطای ساختاریافته (`ApiError` با code)، pagination، نقش‌محوری (`viewer/analyst/admin`)، CSRF برای نوشتن با نشست، کلید API با `compare_digest`، و محافظ SSRF چندلایه. `ruff` روی کل کدبیس **پاس** شد. مشکل اصلی: در نوشتن‌ها idempotency عمومی وجود ندارد و rate limit فقط درون‌فرایندی است.

### A.6 وضعیت Frontend

تک‌فایلی، بدون build، بدون React/Vite. **۲۵ صفحه** با hash routing، اتصال واقعی به ۷۷ جفت (متد، مسیر) API، برچسب «دادهٔ واقعی» پس از دریافت موفق، حالت‌های empty/loading/error، محدودسازی دکمه‌ها بر اساس نقش، و گاردهای ضد race با `__opsReqId`. این بسیار بهتر از آن است که سند `DELTA_IMPLEMENTATION_INVENTORY` (عکس لحظه‌ای ۱۱-۰۶) توصیف می‌کند. نقاط ضعف: هیچ gate خودکار (lint/typecheck/build/E2E) در CI، تست سیم‌کشی `tests/test_ui_page_wiring.py` **untracked**، و متای صفحهٔ سرو‌شده هنوز می‌گوید «Demo data only; backend not connected».

### A.7 وضعیت AI

لایهٔ Gateway خوب مهندسی شده است (زنجیرهٔ provider، retry نمایی سقف‌دار، budget اتمیک، تفکیک Mock/Real، error taxonomy با ۱۰ نوع خطا، ثبت `AdaptiveRouter` به‌صورت best-effort). اما **Free Policy عملاً همهٔ مدل‌های ابری را می‌بندد**: تنها جفت فعال `groq / openai/gpt-oss-20b` است و بقیه (gemini, cloudflare, openai, anthropic, openrouter, openai_compatible) با دلیل مستند `disabled` هستند. طبق مستندات، همان groq هم با 403 منطقه‌ای شکست خورده بود. در دیتابیس **۰ provider و ۰ model** ثبت شده است. نتیجه: مسیر AI واقعی در این محیط عملاً وجود ندارد و `MOCK_MODE=true` تنها مسیر کارآمد است.

### A.8 وضعیت داده‌ها (اندازه‌گیری واقعی، فقط‌خواندنی)

| موجودیت | تعداد | تفسیر |
|---|---:|---|
| sources | ۱۹ | ۱۹ فعال، فقط ۵ مورد `last_success` دارد، ۰ مورد `last_error` |
| documents | ۸۷۲ | snapshot خام واقعی |
| articles | ۸۷۲ | ۷۷۷ `done` / ۹۵ `failed` |
| events | ۷۷۴ | استخراج رویداد کار می‌کند |
| claims | ۷۷۵ | استخراج ادعا کار می‌کند |
| **evidence** | **۰** | زنجیرهٔ شواهد عملاً خالی است |
| forecasts | ۳۷ | تولید شده در مرحلهٔ ۶A |
| recommendations | ۰ | موتور تصمیم خروجی ندارد |
| article_dispatches | ۷۱۱ | **۷۱۱ terminal / ۰ completed** |
| **entities / relationships** | **۰ / ۰** | گراف دانش واقعی وجود ندارد |
| ai_providers / ai_models | ۰ / ۰ | کنترل‌پلین Provider پیکربندی نشده |
| human_reviews | ۰ | هیچ تصمیم انسانی ثبت نشده |
| memory_records | ۰ | حافظه خالی است |

### A.9 وضعیت تست‌ها (اجرای همین ممیزی)

`pytest tests -q -p no:cacheprovider` → **۱۷۶۴ passed، ۱ skipped، ۰ failed** در ۴۷۰٫۳۳ ثانیه (exit 0)، روی Python 3.14.4 و SQLite درون‌حافظه. `--collect-only` → ۱۷۶۵ تست. لاین PostgreSQL در این ممیزی اجرا **نشد** (اجرای آن نیازمند DB دورریختنی و migration است)؛ آخرین اندازه‌گیری مالک در `docs/qa/QA_FULL_PG_PY312_20261107.md` → ۱۷۳۵ passed / ۰ failed.

### A.10 مشکلات بحرانی

1. توقف کامل dispatch (۷۱۱/۷۱۱ terminal، صفر completed).
2. حجم بزرگ کار commit‌نشده (۱۵ modified + ۶۶ untracked) و ۱ commit push‌نشده.
3. زنجیرهٔ Evidence و گراف Entity عملاً غیرفعال (۰ ردیف) در حالی که UI و API آن را «قابلیت» نشان می‌دهند.
4. نبود مسیر AI واقعی مصرح (Free Policy + نبود provider در DB + MOCK_MODE).
5. تناقض مستندات دربارهٔ پذیرش F03.UX (سه سند، سه وضعیت).

### A.11 مهم‌ترین نقاط قوت

- جداسازی واقعی لایه‌ها و ۴۶٫۸k خط کد دامنه‌ای منسجم.
- انضباط «هیچ عدد بدون منبع/زمان/عدم‌قطعیت»: UI در نبود داده عدد جعلی نشان نمی‌دهد (stateهای `INSUFFICIENT_EVIDENCE`/`UNAVAILABLE` در کد و سند مرحلهٔ ۶A).
- dedup غیرتخریبی (MinHash/LSH/Union-Find) که هیچ‌وقت حذف نمی‌کند.
- SSRF guard چندلایه و fail-closed، شامل پین‌کردن IP تأییدشده در Scrapy.
- ۱٬۷۶۴ تست پاس و ruff پاک.
- آرشیو با ZIP/محتوا/catalog/restore و `ARCHIVE_AUTO_PURGE_ENABLED=false` دست‌نخورده.
- UI متصل واقعی با ۲۵ صفحه و احترام به نقش کاربر.

### A.12 مهم‌ترین موانع ادامهٔ توسعه

1. بدون حل dispatch، هیچ مقالهٔ جدیدی به تحلیل دامنه نمی‌رسد.
2. بدون commit/بازبینی، هر `reset` می‌تواند کل UI جدید را نابود کند.
3. بدون gate خودکار فرانت (lint/syntax/E2E) هر تغییر UI می‌تواند بی‌صدا بشکند.
4. بدون provider واقعی، کیفیت inference قابل ارزیابی نیست و F04/F16 قفل می‌مانند.
5. مستندات متناقض باعث می‌شود «وضعیت واقعی» هر بار از نو کشف شود.

---

## بخش B — وضعیت Git و Repository

### B.1 Snapshot دقیق

```
## step6a-analysis-dashboard
HEAD          31b4ca4c662e215931781451605609e505a257e2
main          31b4ca4  (0 عقب / 0 جلو)
origin/main   f502daf  (1 commit جلوتر: 31b4ca4 push نشده)
staged        0
modified      15
untracked     66
```

**آخرین commitها:**

| SHA | تاریخ | پیام |
|---|---|---|
| `31b4ca4` | 2026-11-06 20:27 | feat(inbox): real inbox, screening queue and human decisions (stage 5) |
| `f502daf` | 2026-11-06 19:50 | feat(sources): real ingest funnel, global helpers and source form (stage 4) |
| `0ecbcba` | 2026-11-06 16:18 | feat(sources): wire sources page to real data (stage 4) |
| `e929f36` | 2026-11-06 15:08 | feat(sources): read-only source stats and UI count (stage 4) |
| `9bcaafe` | 2026-11-06 14:26 | docs: add simple operator guide (Persian) |

### B.2 فایل‌های tracked تغییر‌یافته (۱۵)

| فایل | خطوط تغییر | گروه |
|---|---|---|
| `.gitignore` | +۵ | hygiene (افزودن `chrome-win64/`, `test-results/`, `playwright-report/`) |
| `backend/api/routers/decisions.py` | ۹۰ | مرحلهٔ ۶A |
| `backend/api/routers/forecasts.py` | ۸۳ | مرحلهٔ ۶A |
| `backend/api/routers/outcomes.py` | ۲۱ | مرحلهٔ ۶A |
| `backend/api/routers/risk.py` | ۴۹ | مرحلهٔ ۶A |
| `backend/auth/deps.py` | ۵ | افزودن `/api/analyses/request` و suffix `/review` به نقش analyst |
| `backend/database/models/risk_assessment.py` | ۵ | ستون‌های probability/impact |
| `backend/main.py` | ۴ | ثبت روترهای `analyses` و `dashboard` |
| **`backend/static/index.html`** | **+۲۰۱۶** | رابط جدید (۲۹۱٬۴۳۳ → ۳۹۱٬۷۵۹ بایت) |
| `docs/DELTA_IMPLEMENTATION_INVENTORY.md` | ۲۰۵ | ممیزی UI |
| `docs/STAGE_STATUS.md` | ۴ | وضعیت مراحل |
| `domains/events/extractor.py` | ۵۹ | استخراج رویداد |
| `domains/forecast/outcome.py` | ۷۱ | outcome |
| `domains/inbox/decisions.py` | ۲۳ | تصمیم انسانی |
| `tests/test_outcome.py` | ۴ | تست |

### B.3 فایل‌های untracked (۶۶) — دسته‌بندی

| گروه | تعداد | نمونه‌ها |
|---|---:|---|
| Backend جدید | ۴ | `backend/api/routers/analyses.py`, `dashboard.py`, `domains/analyses/{__init__,service}.py` |
| استخراج بازیگر/ژئوپلیتیک | ۲ | `domains/events/actor_extraction.py`, `domains/geopolitics/backfill_actors.py` |
| migration جدید | ۱ | `db/migrations/versions/c8f2d3e4a5b6_phase6a_risk_probability_impact.py` |
| دادهٔ برچسب‌گذاری (محافظت‌شده) | ۶ | `data/labeling/*.jsonl`, `MERGE_REPORT.md` |
| تست‌ها | ۴ | `test_analyses_dashboard.py`, `test_risk_forecast_decisions.py`, `test_actor_extraction.py`, `test_ui_page_wiring.py` |
| E2E + config | ۵ | `tests/e2e/{axe,routes,smoke}.spec.js`, `playwright.config.js`, `package.json`, `package-lock.json` |
| مستندات | ۴۳ | `docs/qa/STEP_6A_11…42`, `QA_FULL_PG_*`, `F04_2_*`, `UI_MIGRATION_MANIFEST.md` |

### B.4 بررسی امنیت Git

- هیچ فایل حساسی در فهرست untracked نیست (`.env`, `backups/`, `*.dump` در `.gitignore`).
- `.env` وجود دارد و در `.gitignore` است؛ در این ممیزی **خوانده نشد** و هیچ مقدار secret چاپ نشد.
- هیچ فایل staged وجود ندارد (`git diff --cached` خالی).
- **در پایان ممیزی وضعیت دقیقاً یکسان است:** ۱۵ modified / ۰ staged / ۶۶ untracked. هیچ `reset`, `clean`, `checkout`, `stash`, `commit`, `push` یا `merge` اجرا نشد.

### B.5 ارزیابی Git

وضعیت برای یک شاخهٔ کاری شدیداً **پرریسک** است: تمام رابط کاربری جدید (۱۰۰٬۳۲۶ بایت افزایش در `index.html`)، روترهای `analyses`/`dashboard`، migration جدید و ۴۳ سند QA فقط روی دیسک‌اند. یک `git checkout .` یا خرابی دیسک، همهٔ کار مرحلهٔ ۶A را از بین می‌برد. از نظر نقشه‌راه v1.8 این همان کلاس نقص `F-01` است که هنوز بسته نشده.

---

## بخش C — معماری واقعی سیستم

### C.1 نمودار معماری (استخراج‌شده از کد، نه از سند)

```text
                    ┌──────────────────────────────────────────────┐
                    │  UI: backend/static/index.html (single file) │
                    │  25 pages · hash routing · session/X-API-Key │
                    └───────────────────┬──────────────────────────┘
                                        │ HTTP (JSON) — 220 ops / 52 routers
                    ┌───────────────────▼──────────────────────────┐
                    │ backend/api/routers/*  (HTTP only)           │
                    │ ApiError · pagination · access_guard (RBAC)  │
                    └───┬───────────────┬───────────────┬──────────┘
                        │               │               │
        ┌───────────────▼──┐  ┌─────────▼───────┐  ┌────▼───────────────┐
        │ source_bot/      │  │ domains/news/   │  │ backend/ai/        │
        │ adapters+runner  │  │ ingest/dedup/   │  │ gateway·policy·    │
        │ security (SSRF)  │  │ classify        │  │ providers·dispatch │
        └───────┬──────────┘  └───────┬─────────┘  └────┬───────────────┘
                │                     │                 │
                └──────────┬──────────┴─────────┬───────┘
                           │                    │
                 ┌─────────▼──────────┐  ┌──────▼─────────────────────┐
                 │ PostgreSQL 16      │  │ local_screening (Kev/Laya) │
                 │ 53 tables          │  │ local_runtimes supervisor  │
                 │ 49 migrations      │  └────────────────────────────┘
                 └─────────┬──────────┘
                           │
        ┌──────────────────▼───────────────────────────────────────┐
        │ domains/{events,claims,graph,geopolitics,society,macro,   │
        │ markets,portfolio,risk,forecast,decision,debate,memory,   │
        │ analyses,archive,briefings,alerts,audit,ops,...}          │
        └──────────────────────────────────────────────────────────┘
```

### C.2 ماژول‌ها و نقش واقعی

| مسیر | LOC | نقش | وضعیت واقعی |
|---|---:|---|---|
| `backend/api/routers/` | — (۵۲ فایل) | لایهٔ HTTP | فعال، ۲۲۰ عملیات |
| `backend/ai/gateway/` | ۱ فایل | زنجیرهٔ provider، retry، budget | فعال |
| `backend/ai/free_policy.py` | ۲۲۴ | allowlist جفت provider/model | فعال اما محدودکننده (فقط ۱ جفت) |
| `backend/ai/providers/` | ۱۳ فایل | ۱۰ adapter | فعال، mock پیش‌فرض |
| `backend/ai/dispatch/` | ۳ فایل / ۴۴۲+ | صف بادوام مقاله→task | کد سالم؛ **عملکرد: ۷۱۱/۷۱۱ terminal** |
| `backend/ai/local_screening/` | ۴ فایل | مشورتی Kev/Laya | خاموش پیش‌فرض |
| `backend/configuration/` | ۵ فایل | کنترل‌پلین تنظیمات (descriptor/revision) | فعال در API؛ UI آن را مصرف نمی‌کند |
| `domains/news/` | ۱۷ فایل | fetchers، normalizer، dedup، classifier | فعال (۸۷۲ سند) |
| `domains/events/` | ۶ فایل | استخراج رویداد + بازیگر + geo | فعال (۷۷۴ رویداد) |
| `domains/claims/` | ۷ فایل | استخراج claim + evidence | claim فعال (۷۷۵)؛ evidence خالی (۰) |
| `domains/graph/` | ۴ فایل | موجودیت/رابطه | کد فعال، داده ۰ |
| `domains/entities/` | **۰** | — | **خالی (فقط `.gitkeep`)** |
| `domains/memory/` | ۳ فایل | آرشیو حافظه/تایم‌لاین | کد فعال، داده ۰ |
| `domains/forecast/` | ۱۴ فایل | forecast/eval/metrics | ۳۷ forecast، ۰ outcome |
| `domains/archive/` | ۵ فایل | ZIP/catalog/restore/telegram | فعال، purge خاموش |
| `source_bot/` | ۳٬۲۷۶ | ربات دریافت + job ledger | فعال |
| `workers/` | **۰** | — | **خالی** (کار پس‌زمینه in-process است) |
| `backend/services/` | **۰** | — | **خالی** |

### C.3 جریان دادهٔ واقعی (آنچه واقعاً اجرا می‌شود)

```text
Source (19 ردیف، 19 active)
  → adapter (rss 5 / api 3 / dataset 6 / official 5)
  → validate + SSRF guard (source_bot/security.py)
  → Document (872)  ← snapshot خام
  → Article (872)   ← normalized + hash + provenance
  → dedup (MinHash/LSH/UF)  ⚠ dedup_on_ingest پیش‌فرض False
  → classify (rules/mock/AI) → 777 done / 95 failed
  → screening (rules / local Kev-Laya / AI) — مشورتی
  → ArticleDispatch  ⚠ 711 terminal / 0 completed
  → event (774) ✔ · claim (775) ✔ · evidence (0) ✘ · entity/graph (0) ✘
  → domain analyses → analyses/dashboard API → UI
```

**مسیرهایی که در نمودار بالا نیستند چون واقعاً کار نمی‌کنند:** زنجیرهٔ evidence، گراف موجودیت، memory، recommendation/decision output، و fan-out dispatch به تسک‌های دامنه.

### C.4 ارزیابی معماری

**قوت:** مرزبندی روشن، بدون microservice زودهنگام، بدون ORM-دوم، بدون framework موازی. dispatch با idempotency key `(article_id, task@version)` و claim اتمیک `UPDATE … WHERE status IN (…)` طراحی درستی دارد.

**ضعف ساختاری:** 
1. وجود دو مسیر موازی ایجاد event/claim (فراخوانی دستی endpointها و dispatch) که باعث می‌شود داده‌ها بدون عبور از dispatch ساخته شوند — همین توضیح می‌دهد چرا ۷۷۴ event داریم ولی صفر dispatch موفق.
2. `terminal` بودن همهٔ ردیف‌ها در UI (صفحهٔ Operations) به‌عنوان شکست قابل‌تشخیص نمایش داده می‌شود، اما هیچ آلارم/هشدار خودکاری برای «۰ completed» وجود ندارد.
3. پوشه‌های placeholder (`workers/`, `services/`, `entities/`) در مستندات به‌عنوان بخشی از معماری معرفی شده‌اند ولی کد ندارند.

---

## بخش D — بررسی Backend و API

### D.1 آمار واقعی

| سنجه | مقدار | شاهد |
|---|---:|---|
| روترها | ۵۲ فایل | `ls backend/api/routers/*.py` |
| عملیات HTTP | ۲۲۰ | `grep -rhoE "@router\.(get|post|patch|put|delete)\("` |
| مدل‌های ORM | ۴۱ فایل | `backend/database/models/` |
| LOC بک‌اند | ۲۰٬۳۷۳ | `find backend -name "*.py"` |
| Lint | `All checks passed!` | `ruff check backend domains tests scripts source_bot` |
| مستندات API | `/docs` فقط در non-production | `backend/main.py` |

### D.2 جدول APIهای مهم

| Endpoint | وظیفه | پیاده‌سازی | UI | DB | اعتبارسنجی | تست | نتیجه | مشکل |
|---|---|---|---|---|---|---|---|---|
| `GET /health`, `/health/db` | سلامت | کامل | — | ✔ | — | ✔ | **پاس (زنده: ok, migration c8f2d3e4a5b6)** | — |
| `GET /api/dashboard/overview` | KPI داشبورد | کامل (جدید/untracked) | ✔ | ✔ | ✔ | `test_analyses_dashboard.py` | پاس (در suite) | وابسته به فایل untracked |
| `GET /api/analyses` | نمای تجمیعی تحلیل | کامل | ✔ | ✔ | ✔ | همان | پاس | داده‌ای برای نمایش نیست (recommendations=0) |
| `GET /api/inbox` | صف ورودی | کامل | ✔ | ✔ | ✔ | ✔ | پاس | ۹۵ مقالهٔ failed در صف دیده نمی‌شود |
| `GET /api/screening/queue` | صف بازبینی | کامل | ✔ | ✔ | ✔ | ✔ | پاس | human_reviews=0 |
| `POST /api/screening/review/{id}/decision` | تصمیم انسانی | کامل | ✔ | ✔ | ✔ | ✔ | پاس | ثبت تصمیم در DB تأیید نشد (جدول خالی) |
| `GET /api/sources`, `/stats` | منابع | کامل | ✔ | ✔ | ✔ | ✔ | پاس | — |
| `POST /api/sources/{id}/preview` | پیش‌نمایش غیرمخرب | کامل | ✔ | ✔ | ✔ | ✔ | پاس | — |
| `GET /api/claims` | ادعاها | کامل | ✔ | ✔ | ✔ | ✔ | پاس | evidence=0 |
| `GET /api/claims/{id}/evidence` | شواهد | کامل | ✘ | ✔ | ✔ | ✔ | پاس (کد) | **UI آن را فراخوانی نمی‌کند** |
| `GET /api/graph/entities` | موجودیت‌ها | کامل | ✔ | ✔ | ✔ | ✔ | پاس | ۰ ردیف |
| `GET /api/geo/events` | رویدادهای نقشه | کامل | ✔ | ✔ | ✔ | ✔ | پاس | ۴۶۳ رویداد بدون مختصات |
| `GET /api/forecasts/outlook` | پیش‌بینی | کامل | ✔ | ✔ | ✔ | ✔ | پاس | ۳۷ forecast، ۰ outcome |
| `GET /api/risk/overview|matrix` | ریسک | کامل | ✔ | ✔ | ✔ | `test_risk_forecast_decisions.py` | پاس | — |
| `GET /api/decisions` | تصمیم‌ها | کامل | ✔ | ✔ | ✔ | ✔ | پاس | recommendations=0 |
| `GET/PUT /api/settings/providers` | کنترل Provider | کامل | ✔ | ✔ | ✔ | ✔ | پاس (کد) | ۰ provider در DB |
| `POST /api/settings/providers/{id}/test` | تست اتصال | کامل | ✔ | ✔ | ✔ | ✔ | کد پاس | **هیچ تست زندهٔ واقعی در این ممیزی** |
| `GET /api/archive/*` | آرشیو | کامل | ✔ | ✔ | ✔ | ✔ | پاس | purge خاموش |
| `GET /api/dispatch/status` | وضعیت صف | کامل | ✔ | ✔ | ✔ | ✔ | پاس | خروجی نشان می‌دهد همه terminal |
| `/api/configuration/*` (۱۰ op) | کنترل‌پلین تنظیمات | کامل | ✘ | ✔ | ✔ | ✔ | پاس (کد) | **UI صفحهٔ Settings آن را مصرف نمی‌کند** |
| `/api/memory/*`, `/api/society/*`, `/api/world-state/*`, `/api/research/*`, `/api/self-eval/*`, `/api/tournaments/*`, `/api/learning/*`, `/api/analogues/*`, `/api/narratives/*`, `/api/independence/*` | قابلیت‌های دامنه | کامل (کد) | ✘ | ✔ | ✔ | ✔ | پاس (کد) | **بدون UI** |

### D.3 نقاط قوت Backend

- خطای یکنواخت `ApiError(status, code, message, details)` و نبود stack trace به کلاینت.
- `access_guard` سراسری با نگاشت نقش بر اساس متد+مسیر و CSRF double-submit برای نشست.
- pagination واقعی روی لیست‌ها (`page/page_size/total`).
- `_StaticUIMount` که `/api/*` را هرگز نمی‌بلعد (باگ کلاسیک static mount حل شده).
- تفکیک محض لایه: routerها منطق دامنه ندارند.

### D.4 کاستی‌های Backend

| ID | مشکل | شدت |
|---|---|---|
| B-01 | idempotency عمومی برای POSTهای نوشتنی وجود ندارد (به‌جز dispatch/alert) | Medium |
| B-02 | rate limit درون‌فرایندی؛ در چند worker بی‌اثر | Medium |
| B-03 | `terminal`-شدن انبوه dispatch هیچ مسیر هشدار/جبران خودکار ندارد | High |
| B-04 | هیچ endpoint/گزارشی برای triage مقالات `classification_status=failed` (۹۵ مورد) وجود ندارد | Medium |
| B-05 | ۱۰ روتر بدون UI (حافظه، جامعه، world-state، research، self-eval…) — قابلیت «Backend-only» | Medium |

---

## بخش E — بررسی Frontend و UI/UX

### E.1 واقعیت stack

| مورد | مقدار (شاهد) |
|---|---|
| فایل | `backend/static/index.html` — ۳۹۱٬۷۵۹ بایت / ۲٬۷۰۷ خط |
| SHA-256 فعلی | `61079b606150a04607e112b7e6105c240ab097e68f63cfd33c972f45815a6ebb` |
| SHA-256 در HEAD | `2714b245dbb1ec890c612ddbd38518f61a2dda30c408f30a0792b162e3870657` (۲۹۱٬۴۳۳ بایت) |
| Framework | هیچ (بدون React/Vite/TypeScript؛ `apps/web` وجود ندارد — فقط `apps/web_leftover_locked/.pytest_cache`) |
| Router | hash routing + `renderPage` + ۲۵ `data-page` |
| CSS | inline در همان فایل (Dark Navy + cyan/violet) |
| Map | MapLibre GL **vendored** در `backend/static/vendor/maplibre-gl/` |
| اتصال API | ۸۵ فراخوانی `api(method, path, opts)` → ۷۷ جفت یکتا |
| تست UI | `tests/test_ui_page_wiring.py` (untracked، ۱۹۶ خط) + ۳ spec در `tests/e2e/` (untracked) |
| Build/lint/typecheck | **وجود ندارد** (`package.json` فقط devDeps دارد: playwright, lighthouse, axe) |

### E.2 جدول ۳ — وضعیت ۲۵ صفحه

| صفحه | Route | قابلیت | اتصال API | DB | عملکرد واقعی | مشکل |
|---|---|---|---|---|---|---|
| overview | `#overview` | KPI، زنجیرهٔ داده | `GET /api/dashboard/overview` | ✔ | دادهٔ واقعی | KPI به روتر untracked وابسته |
| ai-analysis | `#ai-analysis` | فهرست/جزئیات تحلیل | `GET /api/analyses` | ✔ | دادهٔ واقعی | وقتی recommendations=0 فهرست خالی است (صادقانه) |
| ai-chat | `#ai-chat` | چت | `POST /api/ai/chat` | ✔ | واقعی در حد provider | بدون provider واقعی پاسخ نمی‌دهد |
| debate | `#debate` | اجرای مناظره | `GET /api/debate/runs` | ✔ | خواندن واقعی | متن‌های «موضع نمونه» باقی مانده؛ اجرای واقعی نیازمند تأیید |
| evaluation | `#evaluation` | Lab ارزیابی | `GET /api/evaluation/{summary,scores}` | ✔ | واقعی | بدون Gold Set عدد نمی‌سازد (درست) |
| evidence | `#evidence` | زنجیرهٔ شاهد | `GET /api/claims` | ✔ | فقط claim | **evidence=0؛ جزئیات شاهد نمایش داده نمی‌شود** |
| entity-graph | `#entity-graph` | گراف | `/api/graph/entities,relationships` | ✔ | empty state | **۰ موجودیت** |
| forecasts | `#forecasts` | پیش‌بینی | `/api/forecasts/outlook`, run | ✔ | ۳۷ ردیف | بخشی از نمایش نمونه (`سری زمانی نمونه`) |
| risk | `#risk` | ماتریس ریسک | `/api/risk/{overview,matrix}` | ✔ | واقعی | — |
| decisions | `#decisions` | تصمیم/بازبینی | `/api/decisions`, run | ✔ | واقعی | ۰ recommendation |
| inbox | `#inbox` | صف + provenance | `/api/inbox`, `/api/classify/articles/{id}`, `/api/dispatch/articles/{id}` | ✔ | **PASS** (زنجیرهٔ source→doc→article→event) | مقالات failed فیلتر ندارند |
| world | `#world` | نقشه | `GET /api/geo/events` | ✔ | ۴۰ feature + ۴۶۳ بدون موقعیت | tile خارجی (OpenFreeMap) |
| geopolitics | `#geopolitics` | ارزیابی ژئوپلتیک | `/api/geopolitics/{assessments,tensions,analyze}` | ✔ | واقعی | read-only |
| iran | `#iran` | بریف ایران | `GET /api/iran/brief` | ✔ | واقعی | `/events` مصرف نمی‌شود |
| macro | `#macro` | کلان | `/api/macro/{overview,assessments,analyze}` | ✔ | واقعی (با `country=IR`) | — |
| markets | `#markets` | بازار | `GET /api/markets/latest` | ✔ | واقعی | سری زمانی کامل نیست |
| portfolio | `#portfolio` | پرتفوی | `/api/portfolios` (+POST) | ✔ | واقعی، خالی | — |
| screening | `#screening` | صف بازبینی + dispatch | `/api/screening/*`, `/api/dispatch/status` | ✔ | واقعی | تصمیم انسانی در DB دیده نشد |
| sources | `#sources` | منابع + эффективность | `/api/sources`, `/stats`, preview, recheck, PATCH | ✔ | واقعی (۱۹ ردیف) | validate/enable کامل E2E نشد |
| providers | `#providers` | کنترل Provider | `/api/settings/{providers,catalog,models,import-from-env}` + test | ✔ | واقعی | **۰ provider؛ هیچ تست زنده** |
| operations | `#operations` | jobs/dispatch/timeline | `/api/ops/status`, `/api/jobs`, `/api/dispatch/*` | ✔ | واقعی | ۷۱۱ terminal بدون آلارم |
| alerts | `#alerts` | هشدارها | `/api/alerts` + ack/resolve | ✔ | واقعی | بدون تست ارسال از UI |
| archive | `#archive` | آرشیو/بازیابی | `/api/archive/{storage,catalog,validate,restore,purge preview}` | ✔ | واقعی | purge (اجرا) عمداً وجود ندارد |
| reports | `#reports` | بریفینگ | `/api/briefings` + daily/weekly | ✔ | واقعی | — |
| settings | `#settings` | تنظیمات اپ | `/api/settings/app` GET/PUT | ✔ | واقعی | **`/api/configuration/*` (کنترل‌پلین) مصرف نمی‌شود** |

**جمع:** بر پایهٔ نگاشت ۷۷ جفت endpoint، هر ۲۵ صفحه دست‌کم یک فراخوانی واقعی دارد؛ ۱۹ صفحه renderer اختصاصی دارند و ۶ صفحه از طریق الگوی عمومی/بایند اختصاصی تغذیه می‌شوند. **صفر صفحه با دادهٔ ساختگی به‌عنوان دادهٔ زنده** مشاهده شد (برچسب نمونه/`Mock` برجسته است). این وضعیت با عکس لحظه‌ای `DELTA_IMPLEMENTATION_INVENTORY` (۱۱-۰۶، که ۱۹ صفحه را DEMO می‌دانست) تفاوت دارد؛ سند مذکور خودش را «عکس لحظه‌ای» معرفی کرده و منقضی است.

### E.3 بررسی F03.UX (Design System و مهاجرت)

| معیار نقشه‌راه | وضعیت | شاهد |
|---|---|---|
| منبع حقیقت واحد token | PARTIAL | توکن‌های CSS در همان فایل؛ فایل جداگانهٔ design-token وجود ندارد |
| component مشترک قابل استفادهٔ مجدد | PARTIAL | helperهای `panel/metric/status/badge` inline؛ بدون مرز component |
| هیچ صفحه با API جعلی | VERIFIED | ۷۷ جفت endpoint واقعی |
| loading/empty/error/stale | VERIFIED | `در حال دریافت…`, `موردی در صف نیست`, `خطا در دریافت…` |
| RTL/فارسی | VERIFIED | `dir="rtl"`, `lang="fa"`, `fa()`/`nf()` |
| responsive | PARTIAL | فقط `390px` و `1440px` بررسی شده؛ ۳۶۰/۷۶۸/۱۰۲۴ ثبت نشده |
| دسترس‌پذیری (WCAG 2.2 AA) | PARTIAL / NOT VERIFIED | `focus-visible` و حداقل فونت ۱۱px؛ ممیزی رسمی انجام نشده |
| keyboard navigation | NOT VERIFIED | هیچ تست خودکار/دستی ثبت نشده |
| migration/cutover | VERIFIED | root همان فایل جدید را سرو می‌کند |
| legacy retirement با approval | **نقض شده** | `ui-data.js`/`ui-data.css` در STEP 6A.13 حذف شدند بدون approval مالک |
| quality gate خودکار | **MISSING** | هیچ lint/typecheck/build/E2E در CI |

### E.4 کاستی‌های UI

| ID | مشکل | شاهد | شدت |
|---|---|---|---|
| U-01 | متای صفحهٔ سرو‌شده می‌گوید «Demo data only; backend not connected» در حالی که UI کاملاً متصل است | `curl /` → `content="GlobalIntelligence local-first intelligence UI prototype. Demo data only; backend not connected."` | Medium |
| U-02 | هیچ gate خودکار برای ۲٬۷۰۷ خط JS/CSS inline | `package.json` بدون `scripts`؛ CI بدون job فرانت | High |
| U-03 | تست سیم‌کشی و E2E **untracked** | `tests/test_ui_page_wiring.py`, `tests/e2e/*.spec.js` | High |
| U-04 | بخش‌هایی از debate/forecast متن نمونه دارند | `موضع نمونه`, `شاخص توافق نمونه`, `سری زمانی نمونه` | Low |
| U-05 | یک فایل تک‌صفحه‌ای ۳۹۲KB بدون code-splitting؛ در هر بار load کل JS پارس می‌شود | اندازهٔ فایل | Low/Medium |
| U-06 | صفحهٔ Settings کنترل‌پلین `/api/configuration/*` را نمایش نمی‌دهد (قابلیت Backend-only) | grep روی `api(` | Medium |
| U-07 | articles با وضعیت `failed` در inbox فیلتر/نمایش ندارند | ۹۵ ردیف failed؛ UI فقط صف | Medium |

---

## بخش F — بررسی Provider و Model

### F.1 وضعیت واقعی

| لایه | شاهد | وضعیت |
|---|---|---|
| Adapterهای موجود | `backend/ai/providers/registry.py` → `_PROVIDER_CLASSES` | ۱۰: mock, openai, anthropic, gemini, openrouter, groq, cloudflare, openai_compatible, kev, laya |
| کاتالوگ | `backend/ai/provider_catalog.py` → `CATALOG` (۸ ورودی) | موجود و از `FREE_ALLOWLIST` ساخته می‌شود (بدون فهرست تکراری در UI) |
| API کنترل | `backend/api/routers/settings.py` (۳۰+ عملیات: CRUD, key rotate, test, discover models, verify/block) | کامل |
| اتصال UI | `GET /api/settings/providers`, `/providers/catalog`, `/models`, `POST /{id}/test`, `PUT /{id}` | متصل |
| دادهٔ DB | `select count(*) from ai_providers` → **۰**؛ `ai_models` → **۰** | **پیکربندی نشده** |
| مسیر واقعی inference | `MOCK_MODE=true` + `AI_DEFAULT_PROVIDER=mock` | Mock |
| Free Policy | `backend/ai/free_policy.py` | فقط ۱ جفت active |

### F.2 جدول ۴ — وضعیت Provider و Model

| Provider | پیکربندی (adapter) | مدل‌ها (سیاست) | اتصال آزمایش‌شده | وضعیت دسترسی | قابلیت استفاده |
|---|---|---|---|---|---|
| mock | ✔ adapter | — | در تست‌ها ✔ | فعال | **قابل استفاده (پیش‌فرض)** |
| groq | ✔ adapter | `openai/gpt-oss-20b` (active، verified 2026-10-17، ۹۰ روز اعتبار) | در مستندات: 403 منطقه‌ای | ناشناخته در این ممیزی | **مشروط** (نیازمند شبکه/region) |
| gemini | ✔ adapter | `gemini-3.5-flash` (disabled: EEA/terms) | نه | بسته | ✘ |
| cloudflare | ✔ adapter | `@cf/meta/llama-3.1-8b-instruct` (disabled) | نه | بسته | ✘ |
| openai | ✔ adapter | `gpt-4o-mini` (disabled: بدون free tier) | نه | بسته | ✘ |
| anthropic | ✔ adapter | `claude-3-5-haiku-latest` (disabled) | نه | بسته | ✘ |
| openrouter | ✔ adapter | `openai/gpt-oss-20b:free` (disabled) | نه | بسته | ✘ |
| openai_compatible | ✔ adapter | `*` (disabled) | نه | بسته | ✘ (نیازمند verify دستی) |
| kev / laya | ✔ adapter (local) | مدل محلی | خاموش (`LOCAL_SCREENING_ENABLED=false`) | خاموش | ✘ (بدون runtime) |

### F.3 ارزیابی

**درست:** Provider ≠ Model در کد واقعاً رعایت شده است؛ `check_provider` و `check_model` جدا اجرا می‌شوند و پیش از هر HTTP صدا زده می‌شوند؛ `expired` بودن verification باعث مسدودشدن خودکار می‌شود؛ fallback پولی پنهان وجود ندارد؛ mock در production از زنجیره حذف می‌شود.

**ناقص:** 
1. با سیاست فعلی، عملاً **هیچ مسیر ابری رایگان معتبری برای taskهای واقعی وجود ندارد** جز groq که وضعیت شبکه‌اش نامعلوم است.
2. پنل Provider در DB خالی است؛ یعنی «Provider engine» هرگز در این محیط فعال نشده و ادعای «verified» در اسناد به یک اجرای تاریخی محدود است.
3. Test connection و Model verification وجود دارد اما **هیچ شاهد اجرای واقعی در این ممیزی** نیست (`NOT VERIFIED`).
4. `ai_token_ledger` / `provider_run_stats` وجود دارند اما پر بودنشان بررسی نشد.

---

## بخش G — بررسی منابع و Ingestion

### G.1 اعداد واقعی (read-only)

| سنجه | تعداد | شاهد |
|---|---:|---|
| منابع ثبت‌شده | ۱۹ | `select count(*) from sources` |
| منابع فعال (`active=true`) | ۱۹ | همان query |
| منابع با `last_success` | **۵** | `count(*) filter (where last_success is not null)` |
| منابع با `last_error` | ۰ | `count(*) filter (where last_error is not null)` |
| منابع دارای fetch موفق | ۵ (۲۶٪) | همان |
| توزیع نوع | dataset ۶ / official ۵ / rss ۵ / api ۳ | `group by type` |
| اسناد خام | ۸۷۲ | `documents` |
| مقالات | ۸۷۲ (۷۷۷ done / ۹۵ failed) | `articles` |

### G.2 جدول ۵ — وضعیت منابع خبری

| وضعیت منبع | تعداد | توضیح | شواهد |
|---|---:|---|---|
| ثبت‌شده (registered) | ۱۹ | ردیف در `sources` | query مستقیم |
| پیکربندی‌شده | ۱۹ | همه `active=true` | query |
| قابل دسترس (verified reachable) | ۵ | فقط این‌ها `last_success` دارند | query |
| دارای داده ذخیره‌شده | ≥۵ | ۸۷۲ سند از این مسیرها | `documents` |
| دارای پردازش موفق | ۷۷۷ مقاله `done` | ۸۹٪ مقالات | `articles.classification_status` |
| خطادار (last_error) | ۰ | هیچ خطای ثبت‌شده‌ای نیست | query |

> **نکتهٔ مهم:** «۱۹ active» به معنی «۱۹ منبع کارآمد» نیست. ۱۴ منبع هیچ‌گاه `last_success` نداشته‌اند و ۰ منبع خطای ثبت‌شده دارد — یعنی خطاها به فیلد ثبت نمی‌شوند یا این منابع هرگز اجرا نشده‌اند. این یک شکاف observability در Source Management است.

### G.3 ارزیابی فنی

- **قوت:** `connection_check` سخت‌گیرانه (scheme allowlist، رد userinfo، همهٔ IPهای DNS باید عمومی باشند، fail-closed روی DNS بی‌پاسخ)، `vetted_ip` برای Scrapy که IP تأییدشده را پین می‌کند، `redact_headers`, `preview` غیرمخرب (بدون ingest).
- **ضعف:** رابط کاربری «افزودن منبع» ساخته شده اما **فعال‌سازی/validate کامل E2E نشده** (خودِ سند UX7 آن را PARTIAL می‌داند). همچنین `last_error` هرگز پر نمی‌شود → تشخیص منبع خراب از UI ناممکن است.

---

## بخش H — اخبار، Deduplication و Inbox

### H.1 Dedup

| مورد | وضعیت | شاهد |
|---|---|---|
| الگوریتم | shingling + MinHash (۶۴ perm) + LSH (۳۲ band) + Union-Find | `domains/news/dedup.py` |
| آستانهٔ near-dup | ۰٫۷ (قابل تنظیم) | `NEAR_DUP_THRESHOLD` |
| hard delete | **هرگز** | خروجی فقط cluster id و رابطهٔ pairs |
| فعال بودن در جریان ingest | **پیش‌فرض خاموش** | `dedup_on_ingest: bool = False` در `backend/core/config.py` |
| تست | ✔ | `tests/test_dedup*.py` |

**یافته:** موتور dedup وجود دارد و تست دارد، اما به‌صورت پیش‌فرض در ingest اجرا نمی‌شود. این با الزام «engine باید در جریان ingest فعال باشد نه فقط endpoint» (§F07) مغایر است، مگر مالک آگاهانه آن را خاموش نگه داشته باشد.

### H.2 Inbox و تصمیم انسانی

| مورد | وضعیت |
|---|---|
| صف بازبینی | ✔ `GET /api/screening/queue` (page/page_size) |
| نمایش provenance | ✔ `loadInboxDetail` → source→document→article→event + dispatch + evidence |
| تصمیم انسانی | ✔ `POST /api/screening/review/{id}/decision` (approve/reject/request_evidence) |
| تفکیک AI از انسان | ✔ خروجی ماشین در `classification_meta.local_screening`، تصمیم انسان در `human_reviews` |
| ممیزی تصمیم قبلی | ✔ endpoint + صفحه؛ **اما `human_reviews` = ۰ ردیف** |
| بازبینی تکراری | ✔ ack endpoint + قفل UI |

**راه‌حل صادقانه:** در دیتابیس فعلی هیچ تصمیم انسانی ثبت نشده است، پس «کارکرد ذخیره‌سازی تصمیم انسانی» از نظر داده `NOT VERIFIED` است (کد و تست دارد، اجرای واقعی بی‌شاهد).

### H.3 dispatch — مهم‌ترین یافتهٔ گزارش

```sql
select status, count(*) from article_dispatches group by 1;
-- terminal | 711
select task_name, status, count(*) from article_dispatches group by 1,2;
-- screening@v1 | terminal | 711
select substr(last_error,1,50), count(*) ... ;
-- max attempts reached: screening unavailable: LOCAL… | 711
```

**تفسیر:** در `enqueue_after_screening`، وقتی تصمیم `relevant=None` باشد یک ردیف `screening` ساخته می‌شود. این ردیف‌ها سه بار retry کرده و چون screening محلی در دسترس نبوده، `terminal` شده‌اند. هیچ ردیفی به `completed` نرسیده و هیچ‌یک از `ANALYSIS_TASKS` (رویداد، ادعا، گراف، شواهد، دامنه) از این مسیر ساخته نشده است. این با وجود ۷۷۴ رویداد و ۷۷۵ ادعا در DB نشان می‌دهد آن داده‌ها از مسیر دیگری (فراخوانی مستقیم endpointها/اسکریپت‌ها) تولید شده‌اند.

**اثر:** «مسیر مرکزی و بادوام» نقشه‌راه (F09/F10/F11) عملاً کار نمی‌کند؛ هر مقالهٔ جدید در وضعیت بدون پیشرفت متوقف می‌شود.

---

## بخش I — Event Extraction و Geospatial

| مورد | وضعیت | شاهد |
|---|---|---|
| استخراج event | فعال | ۷۷۴ ردیف |
| نوع/زمان/مکان/کشور | ✔ (نگاشت نوع قطعی + gazetteer) | `domains/geo/`, `domains/events/extractor.py` |
| بازیگر (actor) | ✔ کد جدید untracked | `domains/events/actor_extraction.py` + `tests/test_actor_extraction.py` |
| اعتبارسنجی AI vs rules | ✔ | `tests/test_ai_extraction_validation.py` |
| اتصال event به article | ✔ | FK/rel |
| مختصات جغرافیایی | ۴۰ رویداد با مختصات، ۴۶۳ بدون موقعیت | سند UX7 + کد `without_location` |
| نقشهٔ دوبعدی | ✔ MapLibre vendored | `backend/static/vendor/maplibre-gl/` |
| دادهٔ نقشه از Backend | ✔ `GET /api/geo/events` با `X-API-Key` | کد UI |
| فیلتر زمانی/جغرافیایی | ✔ (range/layer) | UI |
| clustering | NOT VERIFIED | — |
| عملکرد با حجم بالا | NOT VERIFIED | — |

**ارزیابی:** استخراج رویداد واقعاً کار می‌کند (۷۷۴/۸۷۲ = ۸۹٪). ضعف اصلی geospatial است: **۹۲٪ رویدادها مختصات ندارند**، یعنی نقشه تصویر ناقصی از جهان می‌دهد. وابستگی به tile/style خارجی (OpenFreeMap) رفتار offline را شکننده می‌کند.

---

## بخش J — Claim، Evidence و Entity Resolution

| قابلیت | کد | داده | وضعیت |
|---|---|---|---|
| استخراج claim | ✔ `domains/claims/extractor.py` | **۷۷۵** | فعال |
| اتصال claim→article | ✔ | — | فعال |
| استخراج evidence | ✔ `domains/claims/evidence.py` | **۰** | **غیرفعال در عمل** |
| شواهد موافق/مخالف | ✔ در schema | ۰ | NOT OPERATIONAL |
| استقلال منابع | ✔ `domains/news/independence.py` + `source_dependency` | — | کد فعال، داده نامعلوم |
| موجودیت‌ها (Entity) | ✔ `domains/graph/engine.py` | **۰** | **غیرفعال** |
| روابط (EntityRelationship) | ✔ | **۰** | **غیرفعال** |
| هم‌نامی/ادغام اشتباه | ✔ منطق alias | — | NOT VERIFIED |
| Knowledge Graph واقعی؟ | — | **نه** | فقط جدول؛ گراف بدون گره |

**پاسخ صریح به پرسش نقشه‌راه:** پروژه **Knowledge Graph عملیاتی ندارد**. ۵۳ جدول و دو جدول `entities`/`entity_relationships` وجود دارد، اما صفر گره و صفر یال. صفحهٔ `entity-graph` صادقانه empty state نشان می‌دهد؛ این درست است، اما یعنی زنجیرهٔ «event/claim → entity → graph → GraphRAG» در محصول کار نمی‌کند.

---

## بخش K — AI و Analysis Engine

### K.1 Gateway

| ویژگی | وضعیت | شاهد |
|---|---|---|
| همهٔ فراخوانی‌ها از Gateway | ✔ | `AIGateway.generate` تنها مسیر |
| retry/backoff سقف‌دار | ✔ (۲ retry، backoff نمایی، احترام به `retry_after`) | `_call_with_retry` |
| بودجهٔ توکن اتمیک | ✔ (`reserve`/`settle`) | `backend/ai/budget.py` |
| budget پیش‌فرض | **غیرفعال** (`ai_daily_token_budget=None`) | `config.py` |
| تفکیک Mock/Real | ✔ `response.is_mock`, حذف mock در prod | `generate` |
| error taxonomy | ✔ ۱۰ نوع + انتخاب قطعی خطای نهایی | `_CHAIN_FAILURE_ORDER` |
| ثبت آماری برای AdaptiveRouter | ✔ best-effort، در MOCK صفر ثبت | `_record_run` |
| redis/queue خارجی | ندارد (عمدی) | — |

### K.2 موتور تحلیل

| قابلیت | وضعیت واقعی | شاهد |
|---|---|---|
| importance/priority | ✔ قواعد + provenance | `config/priority_keywords.toml`, F08 |
| relevance (مشورتی) | ✔ rules/local/AI، پیش‌فرض خاموش | `local_screening` |
| event/claim analysis | ✔ | ۷۷۴/۷۷۵ |
| debate چندمدلی | ✔ کد + UI | `debate_runs` |
| forecast | ✔ ۳۷ ردیف | `forecasts` |
| risk/scenario | ✔ کد + UI | `risk_assessments` |
| decision | کد ✔، خروجی **۰** | `recommendations` |
| ارزیابی/کالیبراسیون | کد ✔ (Brier/LogLoss) | `domains/forecast/metrics.py` |
| backtesting walk-forward | ✔ (بدون shuffle) | `evaluation.py` |
| confidence/INSUFFICIENT_EVIDENCE | ✔ در schema و UI | — |
| تحلیل سرمایه‌گذاری (اثر خبر بر بازار) | **NOT IMPLEMENTED** | فقط `markets/portfolio` مشاهده‌گر |

**نتیجه:** موتور «جمع‌آوری و استخراج» واقعی است؛ موتور «تصمیم و توصیه» کد دارد ولی خروجی تولید نمی‌کند (۰ recommendation). فاصلهٔ پروژه با «سیستم پشتیبان تصمیم» همین‌جاست.

---

## بخش L — Memory System

| مورد | وضعیت |
|---|---|
| مدل/کد | ✔ `domains/memory/{service,run_archive}.py`, `memory_records` |
| API | ✔ `POST /api/memory/archive`, `GET /timeline`, `/stats`, `/records` |
| UI | ✘ هیچ صفحه‌ای ندارد |
| داده | **۰ ردیف** |
| لایه‌های زمانی (ساعتی/روزانه/…) | تعریف نشده؛ فقط timeline بر اساس timestamp |
| بازیابی گذشته برای تحلیل جدید | NOT VERIFIED (بدون داده قابل آزمون نیست) |
| جست‌وجوی معنایی | **وجود ندارد** (بدون embedding/vector store) |

**ارزیابی:** «Memory» در سطح کد یک آرشیو رکورد و timeline است، نه حافظهٔ زمانی/معنایی. نقشه‌راه لایه‌های HOT→COMPRESSED→SUMMARIZED→DELETION_ELIGIBLE را می‌خواهد؛ این لایه‌بندی پیاده نشده است.

---

## بخش M — Database و Migration

| مورد | مقدار | شاهد |
|---|---|---|
| موتور | PostgreSQL **16.15** (alpine) در `gi_postgres` روی `127.0.0.1:15432` | `/health/db` |
| جداول | **۵۳** | `information_schema.tables` |
| Migrationها | ۴۹ فایل | `ls db/migrations/versions/*.py` |
| Head | **`c8f2d3e4a5b6`** (تک‌head) | `alembic heads` |
| Head در DB زنده | `c8f2d3e4a5b6` | `/health/db` |
| Migration جدید (uncommitted) | `c8f2d3e4a5b6_phase6a_risk_probability_impact.py` (۲ ستون Float) | فایل |
| مدل‌های ORM | ۴۱ فایل | — |
| لاین SQLite | `create_all` (نه migration) | `tests/conftest.py` |

**زنجیرهٔ migration (بالا):**

```text
b8c4d5e6f7a8 → e1f2a3b4c5d6 → f17d4e5f6a7b → b7e1c2d3f4a5 → c8f2d3e4a5b6 (head)
```

**ارزیابی:**
- تک‌head بودن ✔، بدون branch/shism.
- `alembic upgrade head` و `downgrade base` در این ممیزی **اجرا نشد** (تغییردهنده روی DB واقعی — ممنوع). آخرین شاهد مالک: `QA_BASELINE.md` (۱۱-۰۴) upgrade از schema خالی exit 0.
- migration زنجیره روی SQLite پشتیبانی نمی‌شود (F-12) → هر ادعای «migration سبز» فقط PG-valid است. تست‌های SQLite با `create_all` جدول می‌سازند، پس **انحراف schema بین دو لاین ممکن است بی‌صدا بماند** (مثلاً `CREATE INDEX`های PG-only).
- دادهٔ Orphan/تکراری اندازه‌گیری نشد (`UNKNOWN`)؛ هیچ constraint violation مشاهده نشد.
- Backup/Restore در این ممیزی **انجام نشد** (تغییردهنده)؛ سند `docs/BACKUP.md` و ادعای مالک در `STAGE_STATUS` وجود دارد، اما restore در این ممیزی تأیید نشد.

---

## بخش N — Archive، Backup و Purge

| مورد | وضعیت | شاهد |
|---|---|---|
| `ARCHIVE_ENABLED` | **غیرفعال** | `domains/archive/service.py: env_bool(..., False)` + تست `test_archive_local.py` |
| `TELEGRAM_ARCHIVE_ENABLED` | **غیرفعال** | همان |
| `ARCHIVE_AUTO_PURGE_ENABLED` | **غیرفعال** | همان + `test_archive_api.py` |
| `PURGE_DRY_RUN` | **فعال (true)** | همان |
| `ARCHIVE_MAX_ZIP_BYTES` | ۱۸٬۰۰۰٬۰۰۰ (پیش‌فرض) | همان |
| ZIP/Manifest/Checksum | ✔ | `build_archive_zip`, `SHA256SUMS` |
| Split چندبخشی | ✔ | `build_archive_zips`, `test_archive_split.py` |
| Catalog | ✔ `archive_catalog` + `archive_articles` | migration `b8c4d5e6f7a8` |
| آپلود Telegram | ✔ کد، gated | `domains/archive/telegram.py` |
| Re-download + roundtrip verify | ✔ کد | `verify_archive_roundtrip` |
| Restore dry-run / restore | ✔ کد | `restore.py` |
| **حذف واقعی (purge)** | **وجود ندارد** | فقط `purge_candidates` + `/purge/preview` |
| UI | ✔ صفحهٔ Archive (verify/restore dry-run/purge preview) | ۷۷ endpoint |

**ارزیابی:** رفتار امنیتی همان است که نقشه‌راه می‌خواهد (پیش‌فرض خاموش، dry-run روشن، هیچ مسیر حذف). آرشیو/بازیابی «کد کامل + یک اجرای تاریخی موفق» است، نه قابلیتی که در این ممیزی اجرا شده باشد. `ARCHIVE_ENABLED=false` یعنی حتی ساخت آرشیو در محیط فعلی مجاز نیست.

---

## بخش O — Alert و Telegram

| مورد | وضعیت |
|---|---|
| مدل | `alerts`, `alert_rules`, `alert_deliveries` |
| Rule engine | ✔ (`domains/alerts/`, `POST /api/alerts/evaluate`) |
| Cooldown/dedup | ✔ (کد + تست) |
| Delivery Telegram | ✔ `sendMessage` با retry/backoff/idempotency |
| Delivery Email | ✔ SMTP (credential-gated) |
| Live ارسال | در سند ۱۱-۰۳ «VERIFIED» گزارش شده؛ در این ممیزی **اجرا نشد** |
| Live SMTP | `BLOCKED` (بدون credential) |
| اتصال Alert به رویدادهای تحلیل | PARTIAL — evaluation دستی/زمان‌بندی‌شده؛ آلارم خودکار «dispatch متوقف شد» وجود ندارد |
| UI | ✔ ack/resolve |

**یافته:** هیچ آلارمی برای شرایط بحرانی مثل «۰ dispatch موفق» یا «۹۵ article failed» تعریف نشده است — دقیقاً همان جاهایی که سیستم نیاز به هشدار دارد.

---

## بخش P — Security

| کنترل | وضعیت | شاهد |
|---|---|---|
| Authentication | ✔ session کوکی HttpOnly + `X-API-Key` | `backend/auth/deps.py` |
| Authorization (RBAC) | ✔ viewer/analyst/admin با نگاشت متد+مسیر | `required_role` |
| CSRF | ✔ double-submit برای متدهای تغییردهنده با نشست | `x_csrf_token` |
| مقایسهٔ کلید | ✔ `secrets.compare_digest` | — |
| Password | ✔ هش‌شده (مدل `users`)، login attempt ثبت می‌شود | models |
| رمزنگاری secret | ✔ Fernet با `APP_ENCRYPTION_KEY` (بدون کلید، ذخیره رد می‌شود) | `config.py`, `credentials_store` |
| نشت secret در پاسخ | ✔ GET فقط `configured` می‌دهد | `settings.py` |
| SSRF | ✔ چندلایه: scheme، userinfo، metadata IP، همهٔ A/AAAA، fail-closed، pin در Scrapy | `source_bot/security.py` |
| SQL Injection | ✔ SQLAlchemy ORM/پارامتری؛ هیچ f-string SQL یافت نشد | — |
| XSS | ✔ `esc()` در تولید HTML؛ محتوای مقاله untrusted | UI |
| CORS | ✔ allowlist صریح؛ `*` در prod رد می‌شود | `validate_production` |
| Rate limiting | ⚠ فقط درون‌فرایندی (`600/min`) | `config.py` |
| File upload security | ✔ آرشیو: path traversal/zip bomb در restore بررسی می‌شود (کد) | `restore.py` |
| Container security | ✔ پورت‌ها روی `127.0.0.1` bind شده‌اند | `docker-compose.yml` |
| Dependency audit | ✘ هیچ `pip-audit`/`npm audit` در CI نیست | `.github/workflows/ci.yml` |
| Production fail-fast | ✔ `validate_production` (SECRET/API_KEY/MOCK/DEBUG/POSTGRES_PASSWORD/CORS/ADMIN_PASSWORD) | `config.py` |
| Logging secret | ✔ لاگ‌ها نوع خطا می‌نویسند نه payload؛ `redact_headers` | — |

### P.1 یافته‌های امنیتی

| ID | یافته | شدت | توضیح |
|---|---|---|---|
| S-01 | **dev auth bypass**: اگر `API_KEY` خالی و `APP_ENV != production` باشد، هر درخواست محلی نقش `admin` می‌گیرد (شامل `/api/settings`, `/api/archive`) | Medium | `_dev_bypass_active()` — برای dev طراحی شده و پورت‌ها loopback‌اند، اما هر process محلی یا malware می‌تواند از آن سوءاستفاده کند. توصیه: در `.env` محلی مقدار API_KEY تنظیم شود یا bypass به `localhost` + هدر صریح محدود شود. |
| S-02 | rate limit فقط single-process | Medium | در چند worker بی‌اثر؛ مستند شده (F-23) اما بسته نشده |
| S-03 | نبود dependency scanning | Low | زنجیرهٔ تأمین بدون کنترل خودکار |
| S-04 | token تلگرام در URL درخواست | Low/Info | الگوی رسمی Bot API؛ ریسک فقط در صورت لاگ‌کردن URL؛ کد آن را لاگ نمی‌کند (بررسی سطحی) |
| S-05 | backup فایل‌های UI در temp سیستم | Low | `C:\Users\…\Temp\opencode\legacy_ui_backup` — با پاک‌سازی temp از بین می‌رود |
| S-06 | هیچ test نفوذ/اسکن مخرب اجرا نشد | Info | خارج از scope این ممیزی |

**هیچ آسیب‌پذیری Critical در کد مشاهده نشد.** موارد بالا ریسک‌های کنترل‌شده‌اند.

---

## بخش Q — Docker و محیط محلی

### Q.1 Compose واقعی

| سرویس | image | پورت | healthcheck |
|---|---|---|---|
| postgres | postgres:16-alpine | 127.0.0.1:15432→5432 | `pg_isready` ✔ |
| backend | build از `docker/backend.Dockerfile` | 127.0.0.1:8000 | — (بسته به postgres) |
| n8n | n8nio/n8n:2.42.6 | 127.0.0.1:5678 | — |

**⚠ سرویس `frontend` در compose وجود ندارد**، در حالی که هدر فایل و README آن را با پورت `5173` تبلیغ می‌کنند.

### Q.2 کانتینرهای در حال اجرا (اندازه‌گیری)

| نام | image | وضعیت | پورت |
|---|---|---|---|
| `gi_backend_parity` | `globalintelligence-backend:candidate-step6a42-r3-20261111` | Up 24h (healthy) | 8000 |
| `gi_backend_cand_6a39` | `…candidate-step6a39-20261111` | Up 27h (healthy) | 8010 |
| `gi_frontend` | `globalintelligence-frontend` (ساختهٔ ۱۱-۰۵، `npm run dev`) | Up 2d | **5173 (orphan)** |
| `gi_postgres` | postgres:16-alpine | Up 2d (healthy) | 15432 |
| `gi_staging_postgres` | postgres | Up 2d (healthy) | 15433 |
| `gi_n8n` | n8nio/n8n:2.42.6 | Up 2d | 5678 |
| `gi_staging_backend` | `gi_staging-backend` | Up 2d (healthy) | 8001 |

### Q.3 بررسی زندهٔ runtime

| بررسی | نتیجه |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /health/db` | `ok`, PostgreSQL 16.15, migration `c8f2d3e4a5b6` |
| `GET /` | ۲۰۰، ۴۰۶٬۲۷۴ بایت، `<html lang="fa" dir="rtl">` |
| متای صفحه | ⚠ «Demo data only; backend not connected» (کهنه/گمراه‌کننده) |

### Q.4 ارزیابی

- **قوت:** اجرای محلی واقعاً پایدار است؛ ۳ backend/staging در حال اجرا، health سالم، DB متصل و در head.
- **ضعف:** (۱) کانتینر orphan `gi_frontend` از دورانی که React وجود داشت باقی مانده و source آن (`apps/web`) دیگر در tree نیست؛ (۲) README/compose ناهمخوان؛ (۳) ساخت image جدید در گذشته با خطای شبکه (pip) شکست خورده بود و مبنای image فعلی `candidate-step6a42` است، پس **کد در حال اجرا دقیقاً همان working tree نیست** (`NOT VERIFIED` برابری باینری).

---

## بخش R — Tests و CI/CD

### R.1 جدول ۶ — وضعیت تست‌ها

| مجموعه | تعداد | موفق | ناموفق | رد‌شده | اجرا نشده | نتیجه |
|---|---:|---:|---:|---:|---:|---|
| کل `tests/` (SQLite درون‌حافظه) | **۱۷۶۵ collected** | **۱۷۶۴** | **۰** | ۱ | ۰ | **PASS** (۴۷۰٫۳۳s، exit 0) |
| PostgreSQL lane | ~۱۷۶۵ | ۱۷۳۵ (سند ۱۱-۰۷) | ۰ | ۰ | ۰ | **در این ممیزی اجرا نشد** |
| `ruff check` | — | ✔ | — | — | — | **PASS** |
| E2E (`tests/e2e/*.spec.js`) | ۳ فایل | — | — | — | **✔ اجرا نشد** | **NOT RUN** |
| coverage | — | — | — | — | ✔ | **اندازه‌گیری نشد** |
| تست live Provider | — | — | — | — | ✔ | **NOT RUN** |
| تست ارسال SMTP | — | — | — | — | ✔ | **BLOCKED** |

**محیط اجرا:** Windows، Python 3.14.4، pytest از `.venv`، `--basetemp` در temp سیستم، `-p no:cacheprovider`، `API_KEY=""`, `MOCK_MODE=true`، SQLite `StaticPool` (طبق `tests/conftest.py`).

**دسته‌بندی تست‌ها (۱۴۷ فایل):** unit/domain (اکثریت)، API/contract، DB/migration، security/SSRF، dispatch/concurrency، AI gateway/policy، archive/restore، screening، UI-wiring (untracked).

### R.2 CI واقعی

| Job | محتوا | وضعیت |
|---|---|---|
| `backend` | Python 3.12، postgres:16 service، ruff، `alembic upgrade/downgrade/upgrade`، `alembic heads`، `pytest tests -q` | ✔ وجود دارد؛ **اجرای راه‌دور تأیید نشده** |
| `backend-sqlite` | `pytest ../tests -q -m "not pg"` | ✔ وجود دارد؛ اما **`-m "not pg"` هیچ تستی را حذف نمی‌کند** (هیچ `pytest.mark.pg` در تست‌ها وجود ندارد) |
| `docker` | build فقط image بک‌اند | ✔ |
| **`frontend`** | — | **وجود ندارد** |
| **`e2e`** | — | **وجود ندارد** |

`AGENTS.md` ادعا می‌کند CI پنج job دارد شامل `frontend` و `e2e` — این ادعا با فایل واقعی `ci.yml` **مغایر است** (سه job).

### R.3 ارزیابی

- تست‌ها واقعاً خوب‌اند: ۱۷۶۴ پاس بدون skip مخفی، `conftest` با ایزوله‌سازی temp و پاک‌سازی جدول‌ها، DNS آفلاین fail-closed.
- اما **پوشش UI صفر خودکار در CI** است و E2E وجود دارد ولی commit/اجرا نمی‌شود. این بزرگ‌ترین شکاف کیفیت است.

---

## بخش S — مستندات

### S.1 اسناد موجود (انتخاب مهم)

| سند | نقش | وضعیت |
|---|---|---|
| `README.md` | معرفی/شروع سریع | کهنه: تست ۱۴۸۰ (واقعی ۱۷۶۴)؛ سرویس frontend :5173 که وجود ندارد |
| `AGENTS.md` | راهنمای عامل | کهنه: ۴۵ router (واقعی ۵۲)، ۱۵۷۰ تست، ۵ job CI (واقعی ۳) |
| `ARCHITECTURE.md` | معماری | خوب، اما `domains/entities` و `workers/` را «فعال» می‌پندارد |
| `DECISIONS.md` (ADR) | تصمیمات | معتبر |
| `docs/ROADMAP_STAGE96_104.md` | برنامهٔ قدیمی | تاریخی، با نقشه‌راه v1.8 هم‌راستا نیست |
| `docs/GlobalIntelligence_Roadmap_v1.5_*` | نقشه‌راه قدیمی | **v1.8 در repo نیست** |
| `docs/STAGE_STATUS.md` | وضعیت مراحل | متناقض (ردیف F04.1 تکراری؛ F03.UX=VERIFIED در حالی که manifest می‌گوید WITHHELD) |
| `docs/ROADMAP_COMPLIANCE_MATRIX.md` | ماتریس انطباق v1.5 | F03.UX=VERIFIED_COMPLETE با شاهد `apps/web` که **دیگر وجود ندارد** |
| `docs/UI_MIGRATION_MANIFEST.md` | manifest مهاجرت UI | **کهنه**: hash `f5f57d…` (فعلی `61079b6…`)، `ui-data.js/css` حذف‌شده ولی ثبت‌شده، state `ACCEPTANCE_WITHHELD` (در حالی که UX7 می‌گوید ACCEPTED) |
| `docs/qa/UX7_ACCEPTANCE_20261107.md` | پذیرش UX.7 | متناقض درون‌سند: «PASS=18 · PARTIAL=3 · FAIL=4» در حالی که جدول هیچ FAIL ندارد |
| `docs/qa/QA_BASELINE.md` | baseline QA | معتبر برای ۱۱-۰۴ اما بر مبنای `apps/web` منقضی |
| `docs/FIXES_BACKLOG.md` | دفتر نقص | خوب؛ اما ردیف F-11 هم «اندازه‌گیری‌شده» و هم «VERIFIED» ثبت شده |
| `docs/qa/STEP_6A_13_LEGACY_UI_RETIREMENT.md` | حذف فایل UI | حاوی artifact مدل (`<|end|>`) در انتهای سند |
| `docs/CODE_CLEANUP_REGISTER.md` | مرجع نقشه‌راه v1.8 | **وجود ندارد** |
| `docs/qa/*` (۴۲ فایل) | گزارش هر مرحله | ارزشمند؛ حجم زیاد و بدون index مرکزی |

### S.2 فهرست تناقض‌های مستندات (قابل اقدام)

1. **وضعیت F03.UX:** سه سند، سه وضعیت (`VERIFIED_COMPLETE` / `ACCEPTANCE_WITHHELD` / `ACCEPTED`).
2. **شاهد فرانت:** ماتریس انطباق به `apps/web` و `npm run build/lint/typecheck` ارجاع می‌دهد؛ این اپ حذف شده و `package.json` هیچ script ندارد.
3. **CI:** AGENTS.md پنج job می‌گوید، واقعیت سه job.
4. **شمارش تست:** README ۱۴۸۰، AGENTS ۱۵۷۰، QA ۱۷۳۵، واقعیت **۱۷۶۴**.
5. **Frontend container:** README/compose هدر :5173، compose سرویس ندارد.
6. **نقشه‌راه:** v1.8 در repo نیست؛ اجرای بعدی نقشه‌راه نمی‌تواند مبنای خود را از repo بخواند.
7. **manifest UI:** فایل‌های حذف‌شده، hashهای منقضی، state قدیمی.

---

## بخش T — تطبیق با Roadmap (v1.8)

### T.1 جدول ۲ — وضعیت مراحل

| شناسه | عنوان | معیار پذیرش (خلاصه) | وضعیت واقعی | موارد ناقص | نتیجه |
|---|---|---|---|---|---|
| F00 | Baseline و حفاظت | ثبت checkout/داده/محیط بدون تغییر | این ممیزی همان کار را انجام داد؛ اسناد F00 موجود | snapshot قابل‌بازیابی از کار uncommitted وجود ندارد | `PARTIALLY_VERIFIED` |
| F01 | Build/Container | image جدید + health + اجرای کد جدید | ۳ بک‌اند healthy و `/health` ok؛ اما برابری image با working tree اثبات نشد | build جدید (خطای شبکه در سابقه) | `PARTIALLY_VERIFIED` |
| F02 | PostgreSQL و CI | suite کامل PG + آفلاین واقعی + laneها | suite PG توسط مالک ۱۷۳۵/۰ (۱۱-۰۷)؛ CI دارد ولی راه‌دور تأیید نشده | اجرای PG در این ممیزی؛ CI remote | `PARTIALLY_VERIFIED` |
| F02.5 | Test hygiene | temp/cwd مستقل | `test_temp_isolation.py`، `PYTEST_DEBUG_TEMPROOT` | — | `VERIFIED` |
| **F03.UX** | مهاجرت UI | ۰ تا ۸ + cutover + retirement | ۲۵ صفحه متصل، cutover انجام شده | gate خودکار، WCAG، UX.8 | `PARTIALLY_VERIFIED` |
| F03.UX.0 | Inventory/manifest | mapping ۲۵ صفحه + مالکیت فایل | `DELTA_IMPLEMENTATION_INVENTORY.md` + manifest | manifest کهنه | `VERIFIED` (زمان خودش) |
| F03.UX.1 | Design System | token/component واحد، RTL، focus | tokenهای inline، `focus-visible` | فایل token مستقل ندارد | `PARTIALLY_VERIFIED` |
| F03.UX.2 | Shell/route | refresh/deep-link/404/auth | hash routing + ۴۰۴ + ۴۰۱ | ۴۰۳ با role واقعی تست نشده | `VERIFIED` |
| F03.UX.3 | صفحات و workflow | اتصال واقعی + stateها | ۷۷ endpoint، ۲۵ صفحه | entity/evidence/memory بدون داده | `PARTIALLY_VERIFIED` |
| F03.UX.4 | chart/map/viz | دادهٔ timestamped + offline | نقشهٔ واقعی ۴۰ feature | ۴۶۳ بدون مختصات، tile خارجی | `PARTIALLY_VERIFIED` |
| F03.UX.5 | فرم/تنظیمات/عملیات | API واقعی + secret write-only | providers/sources/archive/settings متصل | validate/enable منبع E2E نشده؛ configuration UI نیست | `PARTIALLY_VERIFIED` |
| F03.UX.6 | Responsive/a11y/perf | ۳۶۰/۷۶۸/۱۰۲۴/۱۴۴۰ + WCAG | فقط ۳۹۰ و ۱۴۴۰ | keyboard/WCAG/baseline perf | `PARTIALLY_VERIFIED` |
| F03.UX.7 | پذیرش/cutover | ۹ گیت | cutover انجام شده؛ سند ACCEPTED | ۱۹ سند و manifest متناقض؛ E2E در CI نیست | `PARTIALLY_VERIFIED` |
| F03.UX.8 | حذف legacy با approval | approval دقیق روی فهرست | **انجام نشده** (و باید نشود) | approval مالک، allowlist | `BLOCKED` |
| F03.0 | UI-Driven Control Plane | descriptor/revision/audit + فرم‌ها | ۱۰ endpoint + مدل + تست | **UI آن را مصرف نمی‌کند** | `BACKEND_ONLY` |
| F03 | Provider/Gateway/Free | مسیر واقعی مجاز + catalog | Gateway کامل، catalog کامل | هیچ provider واقعی، ۰ ردیف DB | `PARTIALLY_VERIFIED` / `BLOCKED` |
| F03.1 | Provider Catalog | کشف/افزودن از Settings | کاتالوگ + فرم + test | verify زنده ندارد | `PARTIALLY_VERIFIED` |
| F04 | Gold Set انسانی | ۱۰۰–۲۰۰ برچسب + held-out | ۴۰ نمونه subset | Gold Set انسانی | `BLOCKED` (انسانی) |
| F05 | Source Bot→ingest | یک قرارداد + raw + provenance | ۸۷۲ سند، ۱۹ منبع | ۱۴ منبع بدون fetch موفق | `PARTIALLY_VERIFIED` |
| F06 | SSRF/adapter security | همهٔ گیت‌ها | guard چندلایه + تست | — | `VERIFIED` (کد/تست) |
| F07 | dedup غیرتخریبی | E2E ingest + cluster | موتور + تست | **در ingest خاموش** | `PARTIALLY_VERIFIED` |
| F08 | Priority/relevance | مرزها + provenance | F08 سند VERIFIED، تست دارد | relevance محلی خاموش | `PARTIALLY_VERIFIED` |
| F09 | Dispatch بادوام | دو worker، resume، idempotent | کد و تست دارد | **۷۱۱/۷۱۱ terminal، ۰ completed** | `FAILED` (عملیاتی) |
| F10 | Pending/Mock recovery | pilot واقعی | کد recovery | هیچ pilot | `PARTIALLY_VERIFIED` |
| F11 | Analysis pipeline | کل زنجیره traceable | event/claim ✔ | evidence/graph/decision ✘ | `PARTIALLY_VERIFIED` |
| F12 | UI/API/alert delivery | صفحات + delivery | UI کامل، Telegram کد + سابقهٔ live | SMTP BLOCKED، آلارم پایشی ندارد | `PARTIALLY_VERIFIED` |
| F12.1.1 | Source mgmt UI | wizard + preview + SSRF | form/preview/recheck متصل | enable/validate E2E | `PARTIALLY_VERIFIED` |
| F13 | Archive/Recovery/purge | ZIP→upload→verify→restore | کد کامل، roundtrip سابقه‌دار | اجرای این ممیزی؛ purge عمداً خاموش | `PARTIALLY_VERIFIED` |
| F14 | Debt/perf/hygiene | موارد F-xx + frontend gates | F-11..F-19 عمدتاً بسته | F-20 (JSONB)، F-22 (lint/typecheck)، F-23 | `PARTIALLY_VERIFIED` |
| F15 | پذیرش محلی + backup/restore + soak | گیت نهایی | laneها سبز (SQLite) | PG E2E، soak، restore شاهد جاری | `NOT_STARTED` |
| F16 | Forecast/کالیبراسیون | outcome واقعی + baseline | ۳۷ forecast | ۰ outcome؛ فواصل زمانی | `BLOCKED` (داده) |

### T.2 قابلیت‌های خارج از نقشه‌راه (کشف‌شده در کد)

| قابلیت | مسیر | توضیح |
|---|---|---|
| Actor extraction/backfill | `domains/events/actor_extraction.py`, `domains/geopolitics/backfill_actors.py` | مرحلهٔ ۶A.37/38 — در نقشه‌راه v1.8 ذکر نشده |
| Analyses aggregate | `domains/analyses/service.py`, `/api/analyses` | نمای تجمیعی Recommendation+Debate+Forecast |
| Dashboard overview | `/api/dashboard/overview` | KPI تجمیعی با stateهای صادقانه |
| Risk probability/impact | migration `c8f2d3e4a5b6` | ستون‌های جدید ریسک |
| UI wiring guard test | `tests/test_ui_page_wiring.py` | تست ایستای wiring بدون مرورگر |

### T.3 درصد تخمینی تکمیل (روش: ۴۰٪ کد + ۳۰٪ اتصال + ۳۰٪ شاهد اجرا)

| دسته | مرحله‌ها | تکمیل تخمینی |
|---|---|---:|
| زیرساخت/کیفیت | F00, F01, F02, F02.5, F14 | ~۷۰٪ |
| UI/UX | F03.UX.0–.7 (+F03.0 UI) | ~۶۵٪ |
| AI/Provider | F03, F03.0, F03.1 | ~۵۰٪ |
| Ingestion/Security/Dedup/Priority | F05–F08 | ~۷۵٪ |
| Pipeline/Dispatch | F09–F11 | ~۴۵٪ |
| Alerts/Archive | F12, F13 | ~۶۰٪ |
| ارزیابی/کالیبراسیون | F04, F16 | ~۲۰٪ |
| پذیرش نهایی | F15 | ~۲۵٪ |
| **میانگین وزنی** | — | **≈ ۵۶–۶۰٪** |

> این عدد **درصد تکمیل نقشه‌راه** است، نه «آمادگی محصول». با توجه به توقف dispatch و نبود provider واقعی، آمادگی عملیاتی پایین‌تر است.

---

## بخش U — نقاط قوت پروژه (با شاهد)

1. **انضباط دامنه‌ای:** ۴۶٬۷۸۵ خط پایتون با مرز روشن router/domain/AI؛ هیچ منطق دامنه‌ای در router یافت نشد.
2. **پایایی تست:** ۱۷۶۴ پاس / ۰ fail در ۴۷۰s؛ `conftest` با ایزوله‌سازی temp، پاک‌سازی جدول، reset تنظیمات و gateway.
3. **عدم جعل داده:** UI در نبود داده empty state می‌دهد؛ `INSUFFICIENT_EVIDENCE`/`UNAVAILABLE` در schema؛ «No Fake Precision» در README رعایت شده.
4. **Dedup غیرتخریبی:** MinHash/LSH/Union-Find بدون وابستگی خارجی و بدون delete.
5. **امنیت adapterها:** SSRF چندلایه، fail-closed، pinning IP در Scrapy، redact هدرها — از سطح معمول پروژه‌های مشابه بالاتر است.
6. **تفکیک Mock/Real:** `is_mock`, حذف mock از زنجیره در prod، `decided_by`, `model/provider/version` در نتایج.
7. **آرشیو محافظه‌کارانه:** پیش‌فرض‌های خاموش، dry-run، ZIP/manifest/checksum، بدون مسیر حذف.
8. **UI واقعی و متصل:** ۲۵ صفحه، ۷۷ endpoint، نقش‌محور، با `aria`/`focus-visible` و برچسب «دادهٔ واقعی».
9. **مستندسازی پرحجم:** ۴۲ سند QA مرحله‌به‌مرحله + ADR + ROLE_MATRIX + traceability — سرمایهٔ قابل توجه.
10. **اجرای محلی پایدار:** ۳ backend healthy، DB در head migration، `/health/db` سالم.

---

## بخش V — مشکلات و بدهی‌های فنی

### V.1 جدول ۷ — مشکلات اولویت‌دار

| ID | مشکل | شدت | محل | اثر | راهکار |
|---|---|---|---|---|---|
| GI-AUD-01 | ۷۱۱/۷۱۱ dispatch = terminal، ۰ completed؛ علت: `screening unavailable: LOCAL…` | **Critical** | `backend/ai/dispatch/*`, `domains/inbox/decisions.py`, `ArticleDispatch` | هیچ مقالهٔ جدیدی به تحلیل دامنه نمی‌رسد؛ pipeline متوقف | مسیر جایگزین صریح برای نبود screening محلی (قواعد قطعی/ Gateway) یا `pending` صادق به‌جای terminal؛ + آلارم «۰ completed»؛ تست regression با وضعیت واقعی |
| GI-AUD-02 | تمام کار مرحلهٔ ۵/۶A uncommitted (۱۵ modified + ۶۶ untracked، ۱ commit unpushed) | **Critical** | کل repo / `backend/static/index.html`, `analyses.py`, `dashboard.py`, migration | ریسک از دست رفتن UI جدید و migration | commit بازبینی‌شده توسط مالک + push شاخه؛ snapshot قابل‌بازیابی |
| GI-AUD-03 | Evidence=0 و Entity/Relationship=0 در حالی که UI/API آن را ارائه می‌دهند | High | `domains/claims/evidence.py`, `domains/graph/` | ادعاها بدون شاهد؛ گراف دانش وجود ندارد | اجرای زنجیرهٔ evidence/graph یا برچسب صریح `NOT_OPERATIONAL` در UI |
| GI-AUD-04 | Free Policy همهٔ مدل‌های ابری را می‌بندد (فقط groq active، با سابقهٔ 403) | High | `backend/ai/free_policy.py` | هیچ inference واقعی در دسترس نیست؛ F04/F16 قفل | بازبینی سیاست با شاهد رسمی و/یا provider رایگان معتبر؛ ثبت `FREE_UNAVAILABLE` صادقانه |
| GI-AUD-05 | ۰ provider و ۰ model در DB | High | `ai_providers`, `ai_models` | کنترل‌پلین Provider هرگز فعال نشده | ثبت provider با credential از UI و اجرای test واقعی |
| GI-AUD-06 | هیچ gate خودکار فرانت (lint/typecheck/build/E2E) در CI نیست؛ ۲٬۷۰۷ خط inline | High | `.github/workflows/ci.yml`, `package.json` | شکست UI بی‌صدا | job مستقل: `node --check` + تست wiring + Playwright specs (commit‌شده) |
| GI-AUD-07 | تناقض سه‌گانهٔ وضعیت F03.UX در سه سند؛ شاهد `apps/web` دیگر وجود ندارد | High | `STAGE_STATUS.md`, `ROADMAP_COMPLIANCE_MATRIX.md`, `UI_MIGRATION_MANIFEST.md`, `UX7_ACCEPTANCE` | تصمیم‌گیری بر پایهٔ وضعیت غلط | یک منبع حقیقت؛ برچسب `EVIDENCE_STALE` روی اسناد React-era |
| GI-AUD-08 | dedup در جریان ingest خاموش (`dedup_on_ingest=False`) | Medium | `backend/core/config.py` | ورود تکراری بی‌سروصدا | فعال‌سازی پس از اندازه‌گیری و تست cluster |
| GI-AUD-09 | ۹۵ مقاله `classification_status=failed` بدون triage/نمایش | Medium | `articles`, UI inbox | دادهٔ ناموفق پنهان می‌ماند | فیلتر failed + صفحهٔ retry کنترل‌شده |
| GI-AUD-10 | ۱۴ از ۱۹ منبع هرگز `last_success` نداشته‌اند و `last_error` همیشه خالی است | Medium | `sources`, source runner | تشخیص منبع خراب ناممکن | ثبت error/status و نمایش health واقعی |
| GI-AUD-11 | ۴۶۳ رویداد بدون مختصات (۹۲٪)؛ وابستگی tile خارجی | Medium | `geo/events`, UI world | نقشه تصویر ناقص/شکننده | backfill مختصات + tile محلی/fallback |
| GI-AUD-12 | متای صفحهٔ سرو‌شده: «Demo data only; backend not connected» | Medium | `backend/static/index.html` | گمراهی کاربر/بازبین | اصلاح meta |
| GI-AUD-13 | dev auth bypass با `API_KEY` خالی = admin برای هر caller محلی | Medium | `backend/auth/deps.py` | افزایش سطح حملهٔ محلی | الزام API_KEY در محیط توسعهٔ مشترک یا محدودسازی به loopback+هدر |
| GI-AUD-14 | rate limit درون‌فرایندی | Medium | `middleware`, `config.py` | در چند worker بی‌اثر | مستندسازی صریح سقف یا backend مشترک در صورت نیاز اثبات‌شده |
| GI-AUD-15 | حذف `ui-data.js/css` بدون approval مالک (نقض §30.2/UX.8)؛ backup فقط در temp | Medium | `docs/qa/STEP_6A_13…` | ریسک حکمرانی/بازیابی | ثبت approval یا بازگرداندن فایل‌ها از Git/temp به مسیر امن پروژه |
| GI-AUD-16 | manifest UI کهنه (hash/فایل/state) | Medium | `docs/UI_MIGRATION_MANIFEST.md` | rollback/حذف legacy بر مبنای داده غلط | بازتولید manifest با hash فعلی |
| GI-AUD-17 | نقشه‌راه v1.8 در repo نیست (فقط v1.5) | Medium | `docs/` | اجرای بعدی بدون مبنای معتبر | افزودن v1.8 به repo (تصمیم مالک) |
| GI-AUD-18 | `/api/configuration/*` بدون UI | Medium | `backend/configuration/`, UI settings | کنترل‌پلین تنظیمات عملاً بلااستفاده | اتصال صفحهٔ Settings به descriptorها |
| GI-AUD-19 | ۱۰ روتر بدون UI (memory, society, world-state, research, self-eval, tournaments, learning, analogues, narratives, independence) | Medium | routers | قابلیت Backend-only | تصمیم: UI یا `OUT_OF_SCOPE` مستند |
| GI-AUD-20 | مستندات کهنه: AGENTS (۴۵ router/۱۵۷۰ تست/۵ job)، README (۱۴۸۰ تست/frontend :5173)، `CODE_CLEANUP_REGISTER.md` غایب، artifact `<|end|>` | Low | docs | هزینهٔ کشف وضعیت | همگام‌سازی با شواهد جاری |
| GI-AUD-21 | کانتینر orphan `gi_frontend` روی :5173 با image قدیمی | Low | Docker | منبع سردرگمی/سطح حمله | توقف کانتینر (با تصمیم مالک) و اصلاح README/compose |
| GI-AUD-22 | نبود dependency vulnerability scanning | Low | CI | ریسک زنجیرهٔ تأمین | افزودن `pip-audit` (بدون تغییر نسخه‌ها) |
| GI-AUD-23 | `-m "not pg"` در CI هیچ تستی را فیلتر نمی‌کند (marker استفاده نشده) | Low | `ci.yml`, tests | lane SQLite اعتبار تمایزی ندارد | استفاده از marker یا حذف ادعای تفکیک |
| GI-AUD-24 | idempotency عمومی برای POSTهای نوشتنی | Low/Medium | routers | دوبار کلیک = دو عملیات | idempotency key مشترک |

### V.2 تفکیک قطعی از احتمالی

- **قطعی (با شاهد مستقیم):** GI-AUD-01, 02, 03, 05, 06, 08, 09, 10, 11, 12, 15, 16, 17, 20, 21, 23.
- **قطعی از کد ولی بدون اجرای این ممیزی:** GI-AUD-04, 07, 13, 14, 18, 19, 22, 24.
- **نیازمند اندازه‌گیری:** عملکرد N+1، کیفیت استخراج، کالیبراسیون، رفتار offline نقشه.

---

## بخش W — ارزیابی بلوغ (نمره‌دهی)

### W.1 جدول ۸ — نمرهٔ حوزه‌ها

| حوزه | نمره | معیار | نقاط قوت | نواقص |
|---|---:|---|---|---|
| معماری | ۸۲ | مرز لایه‌ها، وابستگی، توسعه‌پذیری | تفکیک واقعی، بدون microservice زودهنگام | placeholderهای خالی، دو مسیر موازی event/claim |
| Backend | ۸۴ | پوشش endpoint، خطا، DI، schema | ۲۲۰ op، ApiError، RBAC | idempotency عمومی، rate limit |
| Frontend | ۷۰ | کد، stateها، اتصال | ۲۵ صفحه متصل، گارد race | بدون build/gate، یک فایل ۳۹۲KB |
| UI/UX | ۷۴ | ناوبری، stateها، RTL، a11y | RTL کامل، empty state صادق | WCAG/keyboard تأییدنشده |
| API | ۸۵ | طراحی، validation، pagination | یکنواخت و مستند | docs در prod خاموش (درست) اما بدون OpenAPI snapshot در repo |
| Database | ۸۵ | schema، migration، head | ۵۳ جدول، تک‌head | SQLite با create_all، backup/restore بی‌شاهد جاری |
| Data Integrity | ۷۲ | provenance، point-in-time، dedup | غیرتخریبی، timestampها | evidence/graph خالی، dedup خاموش |
| Source Management | ۸۰ | CRUD، preview، security | SSRF قوی، preview غیرمخرب | error/health ناقص، validate E2E |
| News Ingestion | ۸۰ | funnel واقعی | ۸۷۲ سند، ۸۹٪ پردازش | ۱۴ منبع بدون success |
| Inbox/Screening | ۷۲ | صف، تصمیم، تفکیک | UX کامل، provenance | ۰ تصمیم ثبت‌شده، screening محلی خاموش |
| Event Extraction | ۷۰ | استخراج، typing | ۷۷۴ رویداد، اعتبارسنجی AI | کیفیت دقت سنجیده نشده |
| Geospatial/Map | ۶۸ | مختصات، نقشه، فیلتر | MapLibre محلی، feed واقعی | ۹۲٪ بدون مختصات، tile خارجی |
| Claim/Evidence | ۵۵ | claim+شاهد | ۷۷۵ claim | ۰ شاهد |
| Entity Resolution | ۳۰ | موجودیت/ادغام/گراف | مدل و کد | ۰ گره، ۰ یال، ماژول خالی |
| AI Provider Mgmt | ۵۵ | catalog/CRUD/test | طراحی کامل، secret-safe | ۰ provider، بدون verify زنده |
| AI Model Routing | ۶۰ | نقش‌ها، assignment، adaptive | role-based routing، free policy | مسیر واقعی مسدود |
| Analysis Engine | ۵۵ | اهمیت/روند/ریسک/پیش‌بینی | forecasts ۳۷، risk کد | ۰ recommendation، evidence صفر |
| Memory | ۲۵ | حافظهٔ زمانی/معنایی | مدل/API | ۰ رکورد، بدون embedding |
| Archive/Backup | ۶۰ | ZIP/verify/restore | کد کامل، پیش‌فرض امن | اجرای جاری، restore شاهد |
| Alert/Telegram | ۶۰ | rule+delivery | کد کامل، retry/idempotency | SMTP BLOCKED، بدون آلارم پایشی |
| Security | ۷۶ | authZ/authN/SSRF/secrets | چندلایه، fail-closed | dev bypass، rate limit، no dep-scan |
| Testing | ۸۵ | پوشش، ایزولاسیون | ۱۷۶۴ پاس، conftest بالغ | PG lane/coverage/E2E شاهد جاری |
| CI/CD | ۴۵ | laneها، اجرای راه‌دور | ۳ job صحیح، Docker build | بدون frontend/e2e، remote نامعلوم |
| Documentation | ۵۰ | دقت، همگامی | حجم و دقت ساختاری بالا | تناقض‌های متعدد |
| Performance | ۴۵ | benchmark، index | N+1/heavy در F14 بررسی شده | هیچ benchmark جاری |
| Local Deployment | ۷۰ | compose، health، پایداری | ۳ سرویس healthy | orphan frontend، عدم برابری image |

### W.2 نمرهٔ کلی

**نمرهٔ کلی: ۶۸ / ۱۰۰** (میانگین وزنی: Backend/API/DB با وزن ۲، Testing/Architecture وزن ۲، بقیه وزن ۱؛ پاسخ‌های `NOT_VERIFIED` در جهت محافظه‌کارانه کسر شده‌اند).

**محدودیت‌های نمره:** (۱) لاین PostgreSQL در این ممیزی اجرا نشد؛ (۲) هیچ benchmark عملکرد اجرا نشد؛ (۳) کیفیت inference واقعی سنجیده نشد؛ (۴) هیچ تصمیم انسانی/screening pilot وجود نداشت. این نمره **آمادگی محصول نیست**؛ «بلوغ مهندسی کدبیس» است.

---

## بخش X — برنامهٔ پیشنهادی ادامهٔ توسعه

### X.1 جدول ۹ — برنامه

| اولویت | مرحله | کارهای باقی‌مانده | وابستگی | معیار پذیرش |
|---:|---|---|---|---|
| ۱ | **T-01 تثبیت دارایی (Git)** | بازبینی ۱۵ modified + ۶۶ untracked؛ commit مرحله‌ای (backend/UI/docs/data)؛ push شاخه؛ snapshot قابل‌بازیابی از UI | تصمیم مالک (خارج از scope عامل) | working tree تعیین‌تکلیف‌شده؛ صفر فایل ارزشمند فقط-دیسکی |
| ۲ | **T-02 رفع توقف dispatch** | مسیر صریح برای نبود screening محلی (rules یا Gateway یا `pending` صادق)، حذف `terminal` انبوه؛ نمایش و آلارم؛ تست regression با سناریوی ۷۱۱ ردیف | T-01 جزئی؛ F04 نیست (نیاز به judgment انسانی ندارد) | ≥۱ رکورد `completed` واقعی؛ صفر `terminal` بدون دلیل؛ آلارم فعال |
| ۳ | **T-03 Triage دادهٔ ناموفق** | endpoint/فیلتر `classification_status=failed` (۹۵ مورد) + retry کنترل‌شده؛ `last_error` منابع | T-02 | ۰ مقالهٔ failed بدون دلیل ثبت‌شده؛ منبع خراب قابل تشخیص |
| ۴ | **T-04 Gate کیفیت فرانت** | job CI: `node --check` روی inline scripts + `pytest tests/test_ui_page_wiring.py` + Playwright specs؛ commit تست‌ها | T-01 | job سبز روی PR؛ شکست UI مانع merge |
| ۵ | **T-05 زنجیرهٔ Evidence و Graph** | اجرای `evidence_collection` و `graph_extraction` روی subset کنترل‌شده؛ یا برچسب `NOT_OPERATIONAL` در UI | T-02، provider/rules | ≥N شاهد و ≥N موجودیت با provenance قابل ردیابی |
| ۶ | **T-06 فعال‌سازی Provider واقعی** | ثبت provider از UI، test اتصال، verify مدل، policy approval؛ ثبت نتیجه | credential مالک | test=200، `ai_models` ≥۱، usage ثبت‌شده |
| ۷ | **T-07 بازتولید شاهد PG** | اجرای suite کامل PG روی tree جاری + migration up/down/up در DB دورریختنی | T-01 | گزارش با تعداد/زمان/exit code جاری |
| ۸ | **T-08 همگام‌سازی مستندات** | manifest UI (hash فعلی)، STAGE_STATUS، compliance matrix، AGENTS/README، افزودن v1.8 به repo، `CODE_CLEANUP_REGISTER.md` | T-01 | صفر تناقض شناخته‌شده؛ هر ادعا به شاهد جاری |
| ۹ | **T-09 پذیرش UX.7/UX.8** | بازثبت UX.7 با E2E واقعی؛ آماده‌سازی allowlist دقیق برای legacy + approval مالک | T-04، T-08 | acceptance یکتا؛ approval hash-bound |
| ۱۰ | **T-10 Archive/restore واقعی** | verify + restore dry-run و restore یک archive؛ اندازه‌گیری disk/WAL | T-07 | checksum/count/restore مطابق؛ purge همچنان خاموش |
| ۱۱ | **T-11 dedup در ingest** | اندازه‌گیری نرخ تکرار، سپس فعال‌سازی + تست cluster | T-03 | duplicate ratio قبل/بعد؛ صفر hard delete |
| ۱۲ | **T-12 F16 outcome** | ثبت outcome برای ۳۷ forecast؛ Brier/LogLoss با baseline | T-05 | گزارش کالیبراسیون با نمونه و افق مشخص |

**قاعده:** در هر نوبت فقط یک مرحلهٔ اصلی فعال؛ T-01 و T-02 بحرانی‌اند و بقیه به آن‌ها وابسته‌اند. **هیچ کاری از VPS/deployment در این برنامه نیست** (طبق §۳۱ نقشه‌راه).

### X.2 فایل‌های درگیر برای دو مرحلهٔ اول

| مرحله | فایل‌ها |
|---|---|
| T-01 | همهٔ ۱۵ modified + ۶۶ untracked (به‌ویژه `backend/static/index.html`, `backend/api/routers/{analyses,dashboard}.py`, `domains/analyses/*`, migration `c8f2d3e4a5b6`, `data/labeling/*`) |
| T-02 | `backend/ai/dispatch/{service,runner,routing}.py`, `domains/inbox/decisions.py`, `backend/ai/local_screening/orchestrator.py`, `backend/api/routers/{dispatch,ops}.py`, `backend/static/index.html` (Operations), `tests/test_dispatch.py` |

### X.3 ریسک‌ها

| ریسک | اثر | کاهش |
|---|---|---|
| commit نامنظم کار نیمه‌کاره | شکستن build | commit مرحله‌ای + اجرای suite پس از هر batch |
| تغییر مسیر screening | از دست رفتن provenance | حفظ `classification_meta` و افزودن `decided_by` جدید |
| فعال‌سازی provider | هزینه/نقض free policy | فقط جفت allowlist، budget، audit |
| حذف legacy | از دست رفتن rollback | approval hash-bound + backup |
| اجرای migration روی DB ارزشمند | از دست رفتن داده | فقط DB دورریختنی؛ `downgrade` ممنوع |

---

## بخش Y — موارد بررسی‌نشده و محدودیت‌های ممیزی

| مورد | وضعیت | دلیل |
|---|---|---|
| اجرای لاین PostgreSQL و migration up/down/up | **NOT RUN** | تغییردهنده روی DB؛ نیازمند DB دورریختنی که در این ممیزی ساخته نشد |
| E2E مرورگر (`tests/e2e/*.spec.js`) | **NOT RUN** | نیازمند سرور ایزوله + Chromium؛ و specها untracked |
| Playwright/axe/lighthouse | **NOT RUN** | همان |
| coverage واقعی | **NOT MEASURED** | ابزار در requirements نیست |
| تست live Provider / SMTP / Telegram | **NOT RUN** | credential مالک؛ `BLOCKED_EXTERNAL` |
| آزمون نفوذ/اسکن آسیب‌پذیری | **NOT RUN** | خارج از scope و ممنوعیت تست تهاجمی |
| backup/restore دیتابیس | **NOT RUN** | تغییردهنده |
| purge / archive live | **NOT RUN** | ممنوعیت تغییر داده |
| benchmark عملکرد (latency/query) | **NOT MEASURED** | نیازمند اجرای بار روی دادهٔ واقعی |
| WCAG رسمی / screen reader / keyboard | **NOT RUN** | نیازمند ابزار/انسان |
| کیفیت inference (Kev/Laya/AI) | **UNKNOWN** | مدل فعال نیست؛ Gold Set انسانی ندارد |
| صحت داده‌های `data/labeling/*` | **NOT INSPECTED در محتوا** | داده محافظت‌شده؛ فقط فایل‌ها فهرست شدند |
| محتوای `.env` | **خوانده نشد** | سیاست عدم افشای secret |
| وضعیت GitHub (PR/CI/Issues) | **NOT CHECKED** | دسترسی شبکه/توکن در دسترس نبود؛ فقط Git محلی |
| برابری باینری image با working tree | **NOT VERIFIED** | image با تاریخ ۱۱-۱۱ ساخته شده و فایل‌های working tree ۱۱-۱۲ تغییر دارند |

---

## بخش Z — نتیجه‌گیری نهایی

GlobalIntelligence یک کدبیس **جدی، منسجم و مهندسی‌شده** است که از «خبرخوان» بسیار فراتر رفته: ۵۳ جدول، ۲۲۰ endpoint، ۸۷۲ سند واقعی، ۷۷۴ رویداد، ۷۷۵ ادعا، نقشهٔ دوجانبهٔ امن، آرشیو قابل‌بازیابی و رابط کاربری ۲۵ صفحه‌ای متصل به دادهٔ واقعی. کیفیت انضباطی (ruff پاک، ۱۷۶۴ تست پاس، SSRF چندلایه، عدم جعل داده) بالاتر از میانگین پروژه‌های مشابه است.

اما دو شکاف، محصول را از «سیستم عملیاتی» دور می‌کند:

1. **زنجیرهٔ پردازش در عمل قطع است** — ۷۱۱/۷۱۱ dispatch ردیف `terminal` دارند و صفر `completed`؛ evidence و گراف موجودیت صفرند. موتور «جمع‌آوری و استخراج» کار می‌کند، موتور «پیوند شواهد → تصمیم» نه.
2. **دارایی اصلی روی دیسک محافظت‌نشده است** — کل UI جدید، روترهای تحلیلی و migration با ۶۶ فایل untracked و ۱۵ فایل modified فقط locally وجود دارند و ۱ commit هم push نشده است.

پروژه **برای ادامهٔ توسعه آماده است** (زیرساخت، تست و اجرای محلی سالم‌اند)، اما **برای استفاده به‌عنوان سیستم پشتیبان تصمیم آماده نیست**. منطقی‌ترین گام بعدی، تثبیت دارایی در Git و سپس رفع توقف dispatch است — نه افزودن صفحه یا قابلیت جدید.

---

## خلاصهٔ مدیریتی نهایی (پاسخ به ۸ پرسش)

1. **پروژه واقعاً در چه وضعیتی است؟** یک monolith بالغ با ۴۶٫۸k خط پایتون، ۵۳ جدول، ۲۲۰ endpoint و UI متصل ۲۵ صفحه‌ای؛ در شاخه‌ای با حجم بزرگ کار commit‌نشده و یک زنجیرهٔ پردازش متوقف (`711 terminal / 0 completed`).
2. **کدام بخش‌ها تکمیل و تأیید شده‌اند؟** مدیریت منابع و امنیت adapter، dedup غیرتخریبی، priority/screening قواعدی، استخراج رویداد و ادعا، لایهٔ Gateway و Free Policy، آرشیو محلی/کاتالوگ، RBAC/CSRF، سلامت محلی و `/health/db` (شاهد مستقیم: ۱۷۶۴ تست پاس، ۸۷۲ سند، ۷۷۴ رویداد، ۷۷۵ ادعا).
3. **کدام بخش‌ها ناقص یا ظاهری‌اند؟** Evidence (۰)، Entity/Knowledge Graph (۰)، Memory (۰)، Recommendation (۰)، کنترل‌پلین Provider (۰ provider در DB)، UI کنترل‌پلین configuration، و مسیر AI واقعی (سیاست عملاً بسته).
4. **مهم‌ترین مشکلات فنی؟** توقف dispatch، نبود gate خودکار فرانت، dedup خاموش در ingest، ۹۵ مقالهٔ failed، health/error ناقص منابع، و تناقض مستندات وضعیت.
5. **مهم‌ترین قابلیت‌های باقی‌مانده؟** زنجیرهٔ evidence و گراف موجودیت، provider واقعی + کالیبراسیون، outcome پیش‌بینی، حافظهٔ زمانی/معنایی، و UI کنترل‌پلین تنظیمات.
6. **آیا پروژه برای ادامهٔ توسعه آماده است؟** بله — زیرساخت، تست و اجرای محلی سالم‌اند؛ اما ابتدا باید دارایی commit/push شود.
7. **منطقی‌ترین مرحلهٔ بعدی؟** تثبیت Git (T-01) و سپس رفع توقف dispatch با مسیر جایگزین صریح برای screening در دسترس‌نبودن (T-02).
8. **فاصله تا هدف نهایی؟** حدود **۴۰–۴۵٪** راه باقی است؛ و این فاصله عمدتاً در «زنجیرهٔ شاهد→تصمیم» و «اعتبارسنجی کیفیت» است، نه در ساختن ماژول جدید.

---

## Execution Log

> تمام دستورهای زیر واقعاً در همین ممیزی اجرا شده‌اند. هیچ‌کدام تغییری در پروژه، دیتابیس یا Git ایجاد نکرده است (به‌جز آرتیفکت‌های temp در مسیر سیستم که در پایان پاک شدند: `PYTEST_DEBUG_TEMPROOT` و `--basetemp` بیرون از repo).

| # | دستور (خلاصه) | هدف | نتیجه | تغییر در پروژه؟ | تست؟ |
|---:|---|---|---|---|---|
| ۱ | `git status --porcelain=v1 -b`, `git branch -a`, `git rev-parse HEAD`, `git log --oneline -20`, `git remote -v` | ثبت وضعیت Git | ۱۵ modified / ۶۶ untracked / ۰ staged؛ HEAD `31b4ca4` | نه | نه |
| ۲ | `git diff --stat`, `git diff --cached --stat`, `git ls-files --others`, `git rev-list --left-right --count main...HEAD` / `origin/main...HEAD` | inventory تغییرات | `0/0` با main، `0/1` با origin/main | نه | نه |
| ۳ | `git for-each-ref --sort=-committerdate …` | تاریخ branchها | ۱۸ branch محلی؛ جدیدترین `step6a-risk-forecast-decisions` | نه | نه |
| ۴ | `python --version`, `node --version`, `npm --version` | محیط | Python 3.14.4، Node 24.16.0، npm 11.13.0 | نه | نه |
| ۵ | `ls backend/api/routers/*.py \| wc -l` | شمارش روتر | ۵۲ | نه | نه |
| ۶ | `grep -rhoE "@router\.(get\|post\|patch\|put\|delete)\(" …` | شمارش عملیات | ۲۲۰ | نه | نه |
| ۷ | `find … \| xargs wc -l` روی backend/domains/tests/source_bot | LOC | ۴۶٬۷۸۵ کل / ۳۲٬۷۱۲ تست | نه | نه |
| ۸ | `ls db/migrations/versions/*.py \| wc -l` | شمارش migration | ۴۹ | نه | نه |
| ۹ | `.venv/Scripts/python.exe -m alembic heads` | head | `c8f2d3e4a5b6 (head)` | نه | نه |
| ۱۰ | `.venv/Scripts/python.exe -m alembic history \| head -4` | زنجیره | ۴ گرهٔ آخر سالم | نه | نه |
| ۱۱ | `.venv/Scripts/python.exe -m ruff check backend domains tests scripts source_bot` | lint | `All checks passed!` | نه | بله (lint) |
| ۱۲ | `.venv/Scripts/python.exe -m pytest tests -q --collect-only` | شمارش تست | ۱۷۶۵ تست در ۸٫۹۰s | نه | نه (collect) |
| ۱۳ | `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=$TEMP/…` (BACKGROUND) | suite کامل | **۱۷۶۴ passed / ۱ skipped / ۰ failed** در ۴۷۰٫۳۳s، exit 0 | نه (temp بیرون repo) | **بله** |
| ۱۴ | `sha256sum backend/static/index.html` و `git show HEAD:…` | شاهد UI | فعلی `61079b6…` (۳۹۱٬۷۵۹B) · HEAD `2714b24…` (۲۹۱٬۴۳۳B) | نه | نه |
| ۱۵ | `grep -oE "data-page=\"…\""` | شمارش صفحه | ۲۵ صفحه | نه | نه |
| ۱۶ | `grep -oE "api\(\s*'(GET\|POST\|…)'"` | نقشهٔ اتصال API | ۸۵ فراخوانی / ۷۷ جفت یکتا | نه | نه |
| ۱۷ | `git show HEAD:backend/static/index.html \| grep -c loadMacro` | اثبات uncommitted بودن UI جدید | HEAD=۰ / working=۷ | نه | نه |
| ۱۸ | `curl -s http://127.0.0.1:8000/health` | سلامت runtime | `{"status":"ok"}` | نه (GET) | نه |
| ۱۹ | `curl -s http://127.0.0.1:8000/health/db` | سلامت DB | `ok`, PG 16.15, migration `c8f2d3e4a5b6` | نه (GET) | نه |
| ۲۰ | `curl -s http://127.0.0.1:8000/ \| wc -c` | حجم UI سرو‌شده | ۴۰۶٬۲۷۴ بایت | نه (GET) | نه |
| ۲۱ | `docker ps --format …` | کانتینرها | ۷ کانتینر؛ `gi_backend_parity` healthy | نه | نه |
| ۲۲ | `docker exec gi_postgres psql -At -c "select … from sources"` | شمارش منابع (read-only) | ۱۹ total / ۱۹ active / ۵ success / ۰ error | نه (SELECT) | نه |
| ۲۳ | `… select type, count(*) from sources group by 1` | توزیع نوع | dataset ۶ / official ۵ / rss ۵ / api ۳ | نه (SELECT) | نه |
| ۲۴ | `… counts from articles/documents/events/claims/evidence/forecasts/recommendations/entities/dispatches` | وضعیت داده | ۸۷۲/۸۷۲/۷۷۴/۷۷۵/**۰**/۳۷/۰/**۰**/۷۱۱ | نه (SELECT) | نه |
| ۲۵ | `… select classification_status, count(*) from articles group by 1` | funnel | `done 777` / `failed 95` | نه (SELECT) | نه |
| ۲۶ | `… select status, count(*) from article_dispatches group by 1` | dispatch | `terminal 711` | نه (SELECT) | نه |
| ۲۷ | `… select substr(last_error,1,50), count(*) …` | علت terminal | `max attempts reached: screening unavailable: LOCAL…` | نه (SELECT) | نه |
| ۲۸ | `… select task_name,status,count(*)` | تفکیک task | `screening@v1 terminal 711` | نه (SELECT) | نه |
| ۲۹ | `… count(*) from information_schema.tables` | شمارش جدول | ۵۳ | نه (SELECT) | نه |
| ۳۰ | `git status --porcelain=v1 -b` (پایان) | کنترل نهایی | **۱۵ modified / ۰ staged / ۶۶ untracked (بدون تغییر)** | نه | نه |
| ۳۱ | `ls docs/CODE_CLEANUP_REGISTER.md`, `ls apps/`, `cat playwright.config.js`, `cat package.json`, `tail ci.yml` | بازرسی مستندات/CI | فایل مرجع غایب؛ `apps/web_leftover_locked/.pytest_cache`؛ CI سه‌جاب | نه | نه |

**دستورهایی که اجرا نشدند (و در فهرست بالا نیستند):** `alembic upgrade/downgrade`، هر `pytest` روی PostgreSQL، E2E/Playwright، `docker build`، `docker compose down`، هر عملیات archive/purge/restore، هر `git add/commit/push/reset/clean/checkout/stash`، و هر نوشتن در دیتابیس.

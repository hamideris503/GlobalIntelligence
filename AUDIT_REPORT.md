# AUDIT_REPORT.md — Full Project Audit (Evidence-Based)

> تاریخ ممیزی: 2026-10-09
> مبنا: repo در `main` (HEAD `7d7ed17`) + ۴ ممیز موازی + راستی‌آزمایی مستقل مجری
> اصل: هیچ ادعایی بدون شواهد (فایل:خط، خروجی دستور، رفتار زنده) پذیرفته نیست.

---

## 0. محدودیت‌های ممیزی (مهم)

1. **فایل MASTER PROMPT در repo وجود ندارد** (جست‌وجوی کامل `*MASTER*`/`*PROMPT*` در repo و پوشه‌ی والد: فقط `evidence_prompts.py` و `prompts.py` یافت شد).
   مبنای الزامات = `ARCHITECTURE.md` + `ROADMAP.md` (۵۳ فاز) + بندهای «بند N» داخل کد
   (۲۵ بند یکتا: 10–12، 15–19، 21–26، 33، 40–42، 45، 47–49، 69، 72–73) + `DECISIONS.md`.
2. **کلید واقعی Provider در دسترس نیست** (کلید قبلی Gemini روی API واقعی 403 داد) → همه‌ی
   بررسی‌های Provider واقعی BLOCKED است؛ mock هرگز به‌جای واقعی جا نزده شد.
3. **VPS در دسترس نیست** → استقرار زنده BLOCKED است (Phase 48 قبلاً همین را ثبت کرده).
4. هیچ secret در این گزارش چاپ نشده؛ `.env` فقط خوانده شد (هدر تست‌های زنده).

---

## 1. یافته‌ها بر اساس شدت

### Critical — هیچ موردی تأیید نشد
سیستم بالا می‌آید، migration خطی و جاری است (تک‌head)، هیچ data-loss فعالی دیده نشد
(orphan=0، نقض unique=0)، احراز هویت روی همه‌ی routerها برقرار است (تست ۲۹+۱۴ مسیر).

### High (۴ مورد — هر ۴ تعمیر شدند، بخش 3)

| # | یافته | شواهد | تعمیر |
|---|---|---|---|
| H1 | شکست AI در Evidence به‌صورت `done` جعلی ثبت می‌شد؛ retry ناممکن بود | `domains/claims/evidence.py:132-137` (قبل): `except` فقط log، سپس `evidence_extracted=True`؛ تست زنده: ۷۸ claim با ۷۵ single_source | re-raise در `collect_for_claim`؛ `run()` آن را failed می‌شمارد؛ تست `test_evidence_failure_not_marked_done` |
| H2 | طبقه‌بندی فقط title (+summary تهی) را می‌دید؛ `Document.raw_text` هرگز خوانده نمی‌شد | `domains/news/classifier.py:99` (قبل) + `ingestion.py:130` (`summary=None`) + DB زنده: ورودی عملاً تک‌خطی | افزودن `raw_text` به ورودی + prompt `v2→v3`؛ تست بدنه‌محور |
| H3 | خطای شمارش در مانیتورینگ (`-1`) چون از آستانه کمتر بود `pass` می‌شد | `domains/ops/service.py` (قبل): `except → -1` + `_band(-1)` → pass | `count_check` با `None→fail`؛ تست رگرسیون |
| H4 | آرگومان `target_db` اسکریپت بکاپ بدون اعتبارسنجی در SQL قرار می‌گرفت | `scripts/db_backup.py` (قبل): `f"DROP/CREATE DATABASE {target_db}"` | `valid_target_db` (regex شناسه) + تست؛ کانتینر پارامتری (`PG_CONTAINER`) + پوشش KEY_TABLES از ۱۳ به ۲۰ جدول |

### Medium (۱۱ مورد — همه تعمیر شدند)

| # | یافته | شواهد | تعمیر |
|---|---|---|---|
| M1 | انتساب همه‌ی Evidenceها به مقاله‌ی اول رویداد (تخریب استقلال منابع) | `evidence.py:180-193` (قبل): فقط `articles[0]` | `article_index` اختیاری در schema + prompt v2 با مقالات شماره‌دار + fallback مستند + تست ۲ منبعه |
| M2 | `json_schema` روی Gemini/OpenRouter نادیده گرفته می‌شد | `gemini.py:37-56`, `openrouter.py:31-39` در برابر `openai.py:39-40` | `responseMimeType` / `response_format` + ۲ تست payload |
| M3 | `?fetcher=mock` در production ردیف جعلی می‌نوشت | `routers/economic.py:74`, `routers/markets.py:59` بدون guard | 422 وقتی `mock_mode=false` + ۲ تست |
| M4 | بازه‌ی سناریو روی نقطه‌ی جابه‌جاشده مرکز نبود | `scenarios/engine.py:155-156` (قبل) + assumptions «copied» | مرکزسازی مجدد با حفظ پهنا + تست midpoint |
| M5 | cooldown هشدار با ack دور زده می‌شد | `alerts/engine.py:56-68` (قبل): فقط `status==active` | شامل `acknowledged` + تست |
| M6 | `VITE_API_BASE_URL` در ایمیج prod قفل بود (env زمان اجرا بی‌اثر) | `frontend.prod.Dockerfile` بدون ARG | ARG + build-arg در prod compose |
| M7 | سیستم تهی نمره‌ی میانی C می‌گرفت | `selfeval/checks.py:overall` (قبل) | همه-warn → D + تست |
| M8 | fail-fast شکاف داشت (رمز DB، CORS `*`) | `config.py:validate_production` (قبل) | ۲ شرط جدید + تست |
| M9 | `/` از rate-limit معاف بود (قابل اسکن) | `security.py` exempt پیش‌فرض | حذف `/` + تست معافیت health پابرجاست |
| M10 | root نشت `env` + لینک ثابت `/docs` (غلط در prod) | `routers/health.py:17-25` (قبل) | حذف `env` + docs شرطی + تست عدم‌نشت |
| M11 | ریسک‌های brief از همه‌ی دوره‌ها قاطی می‌شد | `briefings/daily.py` (قبل): بدون فیلتر period | فقط آخرین دوره + تست |

### Low (تعمیرشده: dead code و ناسازگاری‌های کوچک)

- ثابت مرده‌ی `INDEPENDENCE_CORROBORATION_THRESHOLD`، خروجی `json` در `__all__`، تابع مرده‌ی `_parse_csv_rows` (+ importهای csv/io)، پارامتر مرده‌ی `needsKey` در فرانت‌اند (با `npm run build` راستی‌آزمایی شد).
- نرخ stats در `ai_routing` خام بود ولی suggest هموار → یکدست‌سازی به لاپلاس + assert در تست.
- `_validate` بدون jsonschema ساکت می‌گذشت → warning صریح.
- واگرایی فیلتر منبع بین CLI و API ingest → یکسان‌سازی CLI با API.
- نرخ stats در `ai_routing` خام بود ولی suggest هموار → یکدست‌سازی به لاپلاس + assert در تست.

### پذیرفته‌شده بدون تغییر کد (مستند، کم‌ریسک‌تر از دست‌کاری)

- تکرار `verify_status` در evidence/independence: ورودی متفاوت (شواهد خام در برابر منابع مستقل) و رفتار موردنیاز متفاوت؛ یکپارچه‌سازی ریسک رگرسیون دارد.
- تکرار UnionFind/`_safe_json`/`rank_key`/`_series_values`: کوچک و پایدار؛ بازنویسی توجیه ندارد.
- جدول مرده‌ی `scenarios` (موتور روی `forecasts.scenario` می‌نویسد): حذف جدول migration مخرب می‌خواهد؛ ثبت شد.
- `expired`/`actual_bool` مسیرهای رزرو آینده‌اند (تست پوشش دارد)؛ حذف نمی‌شوند.
- تطبیق نام بازیگر↔موجودیت رشته‌ای، وزن‌های EXPOSURES ثابت، `brief articles[:10]`، N+1ها و loadهای O(N) (adjacency/replay/collect): محدودیت‌های مقیاس ثبت‌شده، نه باگ صحت.
- `_rerank` سراسری تصمیم‌ها، حذف آبشاری پورتفوی، `localStorage` کلید، dev-image به‌عنوان root: تصمیمات طراحی ثبت‌شده.
- staging با secret مشترک base: محیط غیرproduction؛ پذیرفته‌شده با ذکر.

---

## 2. وضعیت M1–M4 (خلاصه‌ی ممیزان + تأیید مجری)

| مسیر | وضعیت |
|---|---|
| ingest → dedup → classify → event → claim → evidence → independence → graph | متصل end-to-end؛ ۲ MAJOR بالا تعمیر شد؛ بقیه MINOR/پذیرفته‌شده |
| economic/market/worldstate/memory/analogue + AI gateway | متصل؛ mock guard اضافه شد؛ routing استاتیک (by design، تطبیقی جدا در Phase 37) |
| forecast/outcome/eval/tournament/scenario/risk/decision/iran/portfolio/narrative/society/geo/macro | متصل؛ بازه‌ی سناریو تعمیر شد؛ بقیه MINOR/پذیرفته‌شده |
| auth/security/backup/docker/staging/monitoring/learning/research/audit/briefings/alerts/routing/n8n/frontend | متصل؛ ۱۰ تعمیر بالا اعمال شد |

---

## 3. تست‌های سطحی شناسایی‌شده (بدون رفتار واقعی — اصلاح‌نشده، فقط گزارش)

طبق دستور (تست را برای سبز شدن دست‌کاری نکن): `test_smoke.py` (لیست‌طول + قطع اتصال)،
`test_mock_schema.py` (اعتبار فیکسچر، نه رفتار)، `test_health_db_shape` (شکل با monkeypatch)،
`test_models.py` (نام جدول/ستون)، `test_briefings/weekly empty_db` (همیشه `stored==1`)،
`test_audit append-only` (عدم‌تغییرپذیری واقعی آزمون نشده)، چند assert شکلی
(`type==object`، `normalize_name` ساده). این‌ها نگه داشته شدند و در ماتریس علامت خوردند.

---

## 4. توصیه‌ها (به ترتیب اولویت)

1. **P0 — واقعی‌سازی داده**: Provider واقعی + اجرای Phase 10 redo (BLOCKED: کلید معتبر).
2. **P0 — استقرار**: VPS (BLOCKED: دسترسی)؛ سپس TLS، cron بکاپ، Prometheus جدا.
3. **P1 — مقیاس**: N+1ها و loadهای تمام‌جدولی (adjacency گراف، replay، briefings) با رشد داده.
4. **P1 — CI واقعی**: workflow با pytest/ruff/build (الان TODO است).
5. **P2 — workers پس‌زمینه** برای endpointهای سنگین؛ JSONB برای topics/entities.
6. **P2 — فعال‌سازی workflowهای n8n** (فعلاً `active:false`) پس از مشاهده‌ی پایداری.

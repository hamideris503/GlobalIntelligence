# DECISIONS.md

> ثبت تصمیمات معماری (Architecture Decision Records)
> قالب: Date / Context / Decision / Alternatives / Why selected / Consequences

---

## ADR-0001 — انتخاب معماری Modular Monolith + Workers
**Date:** 2026-10-07
**Context:** پروژه باید سریع قابل توسعه باشد و تیم/عامل به‌تنهایی آن را بسازد. Microserviceها هزینه عملیاتی و پیچیدگی زودهنگام ایجاد می‌کنند.
**Decision:** شروع با Modular Monolith (Backend واحد) + Workers برای پردازش پس‌زمینه. مرزهای ماژولار رعایت می‌شوند.
**Alternatives:** (1) Microservices کامل، (2) سرورلس، (3) Monolith بدون Workers
**Why selected:** Rule Against Premature Complexity (بند 105). Workers برای jobs زمان‌بندی‌شده ضروری است اما استخراج سرویس هنوز لازم نیست.
**Consequences:** امکان استخراج سرویس در آینده با حفظ مرزها؛ اجتناب از سربار عملیاتی.

---

## ADR-0002 — PostgreSQL به‌عنوان منبع اصلی داده
**Date:** 2026-10-07
**Context:** به یک منبع داده تراکنشی، رابطه‌ای و قابل اتکا برای اخبار، رویدادها، حافظه و پیش‌بینی‌ها نیاز داریم. TimescaleDB برای سری‌های زمانی در آینده ممکن است لازم شود.
**Decision:** PostgreSQL به‌عنوان Single Source of Truth. TimescaleDB در صورت نیاز بعداً به‌عنوان extension اضافه می‌شود.
**Alternatives:** MongoDB، ClickHouse، SQLite، TimescaleDB از روز اول
**Why selected:** بلوغ، قابلیت‌های JSONB، پشتیبانی geospatial/زمانی، و مسیر ارتقا به TimescaleDB.
**Consequences:** Redis از روز اول اضافه نمی‌شود مگر نیاز واقعی (Queue/Cache/RateLimit) اثبات شود.

---

## ADR-0003 — AI Gateway مستقل و Provider-Agnostic (Mock-First)
**Date:** 2026-10-07
**Context:** پروژه نباید به یک مدل یا Provider خاص (مثلاً Ollama یا یک شرکت) وابسته باشد، و باید بدون API پولی هم قابل توسعه باشد.
**Decision:** ساخت لایه AI Gateway با Provider Adapter. Mock Provider به‌عنوان Provider پیش‌فرض/توسعه. نام Providerها در منطق اصلی Hard-code نمی‌شود.
**Alternatives:** اتصال مستقیم به یک SDK، استفاده از LangChain به‌عنوان هسته، Ollama اجباری
**Why selected:** Free-First، قابلیت جایگزینی، تست بدون هزینه، انطباق با MOCK_MODE.
**Consequences:** همه‌ی فراخوانی‌های AI باید از Gateway عبور کنند. Gateway مسئول Fallback/Retry/Cost/Tracking است.

---

## ADR-0004 — محاسبات آماری Deterministic، تفسیر با LLM
**Date:** 2026-10-07
**Context:** Brier، Log Loss، VaR، Monte Carlo و … نباید به LLM سپرده شوند.
**Decision:** محاسبات کمّی در Python (کتابخانه‌های آماری) انجام و صرفاً تفسیر آن‌ها به LLM واگذار می‌شود.
**Alternatives:** واگذاری محاسبات به LLM، تولید اعداد توسط LLM
**Why selected:** دقت، تکرارپذیری، اجتناب از No Fake Precision.
**Consequences:** تفکیک صریح لایه «compute» از لایه «interpret».

---

## ADR-0005 — رعایت Point-in-Time Integrity از ابتدا
**Date:** 2026-10-07
**Context:** خطر look-ahead / future leakage در backtest و تحلیل.
**Decision:** ثبت زمان‌های published_at / retrieved_at / available_at / observed_at / revision_at برای داده‌ها؛ ممنوعیت Random Shuffle در backtest.
**Alternatives:** اصلاح بعدی داده‌ها، نادیده گرفتن زمان انتشار
**Why selected:** جلوگیری از نتایج گمراه‌کننده و غیرقابل‌اعتماد.
**Consequences:** طراحی مدل داده از Phase 3 این فیلدها را الزامی می‌کند.

---

## ADR-0012 — Gateway-First و رفتار بدون API Key
**Date:** 2026-10-08
**Context:** پروژه نباید به هیچ Provider خاصی وابسته باشد و بدون API پولی هم باید اجرا شود.
**Decision:**
- تمام فراخوانی‌های AI از `AIGateway` عبور می‌کنند؛ Providerها فقط در `registry.py` شناخته می‌شوند.
- نام Provider در منطق اصلی hard-code نمی‌شود.
- زنجیره‌ی هر route همیشه با `mock` پایان می‌یابد تا سیستم هرگز کاملاً از کار نیفتد.
- Provider بدون API Key → `not configured` (نه crash).
**Alternatives:** اتصال مستقیم به یک SDK، وابستگی به یک Provider، خطای سخت هنگام نبود کلید
**Why selected:** Free-First (بند 71)، API Key Independence (بند 72)، Provider-Agnostic (بند 11).
**Consequences:** هر task جدید باید نقش (role) خود را در routing تعریف کند.

---

## ADR-0011 — مرز n8n و Backend
**Date:** 2026-10-08
**Context:** n8n می‌تواند convert به مغز سیستم شود، که خلاف بند 8 است.
**Decision:** n8n فقط trigger/زمان‌بندی/webhook/هماهنگی انجام می‌دهد و از طریق API به backend وصل می‌شود. هیچ منطق علمی/تحلیلی در n8n نوشته نمی‌شود. ارتباط با یک endpoint روشن (`/api/jobs/trigger`) و جدول `job_runs` انجام می‌شود.
**Alternatives:** نوشتن logic در n8n، اجرای مستقیم SQL از n8n به Postgres
**Why selected:** حفظ منبع حقیقت در Backend/Python (بند 8)، قابلیت تست و Reproducibility.
**Consequences:** هر job جدید باید endpoint مربوطه در backend داشته باشد؛ n8n فقط صدا می‌زند.

---

## ADR-0010 — نگهداری JSON در ستون‌های Text برای موجودیت‌های تازه
**Date:** 2026-10-08
**Context:** مدل‌های Article/Event/Claim فیلدهایی مثل topics/entities/actors دارند که در نسخه اول ساختار متغیر دارند؛ جداول واسط کامل، پیچیدگی زودهنگام ایجاد می‌کند.
**Decision:** این فیلدها در نسخه اول به‌صورت JSON (stringified در ستون Text) نگهداری می‌شوند. در Phase 15 (Knowledge Graph) در صورت نیاز به جداول رابطه‌ای تبدیل می‌شوند.
**Alternatives:** ستون JSONB از ابتدا، جداول واسط کامل، MongoDB
**Why selected:** Rule Against Premature Complexity (بند 105)؛ PostgreSQL همچنان منبع واحد است و مسیر مهاجرت باز است.
**Consequences:** کوئری‌های پیشرفته روی این فیلدها فعلاً محدود است؛ در صورت نیاز به PostgreSQL JSONB مهاجرت می‌کنیم (migration جدید).

---

## ADR-0009 — مقاوم‌سازی Docker build در برابر شبکه‌ی محدود
**Date:** 2026-10-08
**Context:** در build تصویر backend، دسترسی به `files.pythonhosted.org` (محل دانلود پکیج‌های PyPI) با خطای SSL EOF شکست خورد؛ اما `pypi.org` و آینه‌ی `mirror-pypi.runflare.com` در دسترس بودند.
**Decision:** Dockerfile بکاند از `PIP_INDEX_URL`/`PIP_TRUSTED_HOST` (build-arg) پشتیبانی می‌کند؛ پیش‌فرض PyPI رسمی است و در `.env` می‌توان آینه را ست کرد. Dockerfile فرانت‌اند نیز `NPM_REGISTRY` قابل تنظیم دارد.
**Alternatives:** hard-code کردن آینه، حذف build از Docker و نصب محلی
**Why selected:** حفظ پیش‌فرض استاندارد (Free-First و portable) و امکان override بدون تغییر کد؛ پروژه نباید به یک آینه‌ی خاص وابسته شود.
**Consequences:** در محیط‌های با شبکه‌ی محدود باید `PIP_INDEX_URL` در `.env` ست شود؛ روی سرور عادی، پیش‌فرض کافی است.

---

## ADR-0008 — ساختار کد Backend و Frontend در Phase 2
**Date:** 2026-10-07
**Context:** نیاز به اسکلت اجرایی که هم محلی (بدون Docker) و هم در Docker کار کند.
**Decision:**
- Backend به‌صورت package پایتونی (`backend.*`) با Application Factory (`create_app`) و اجرای `uvicorn backend.main:app`.
- تنظیمات مرکزی با `pydantic-settings` از `.env`؛ نام Providerهای AI و DSN در کد hard-code نمی‌شود.
- بررسی دیتابیس به‌صورت **non-fatal**: نبود DB باعث خطای سرور نمی‌شود بلکه وضعیت `degraded`.
- Frontend با React 18 + Vite + TypeScript، `dir="rtl"`، Dark Mode، و آدرس API از `VITE_API_BASE_URL`.
**Alternatives:** ساختار flat بدون package؛ اتصال اجباری به DB در startup؛ CRA به‌جای Vite
**Why selected:** قابلیت اجرا در محیط‌های مختلف، عدم Crash در نبود سرویس جانبی (قانون 72)، سرعت Vite.
**Consequences:** در Docker مسیر import باید از ریشه با پکیج `backend` کار کند؛ دیتابیس در Phase 3 کامل فعال می‌شود.

---

## ADR-0007 — نسخه‌های حداقلی و نبود uv/make
**Date:** 2026-10-07
**Context:** محیط توسعه روی ویندوز است. `uv` و `make` نصب نیستند؛ npm روی ویندوز به شکل `npm.cmd` اجرا می‌شود و کنسول cp1256 است.
**Decision:** استفاده از ابزارهای استاندارد (pip/venv، npm، Docker CLI/Compose). عدم افزودن وابستگی به `uv`/`make`. اسکریپت‌های کمکی به‌صورت Python cross-platform نوشته می‌شوند و کدگذاری خروجی UTF-8 می‌شود.
**Alternatives:** نصب uv به‌عنوان package manager، استفاده از Makefile، اسکریپت‌های shell
**Why selected:** کاهش وابستگی زودهنگام (Rule 9)، سازگاری کامل با ویندوز، اجرای بدون ابزار اضافه.
**Consequences:** همه اسکریپت‌ها باید cross-platform و UTF-8-safe باشند؛ اگر بعداً `uv` لازم شد، باید ADR جدید ثبت شود.

---

## ADR-0006 — مجوز پروژه (Open)
**Date:** 2026-10-07
**Context:** مجوز پروژه هنوز تعیین نشده است.
**Decision:** تصمیم به تأخیر افتاد تا پیش از انتشار عمومی گرفته شود.
**Alternatives:** MIT، Apache-2.0، AGPL-3.0، Proprietary
**Why selected:** —
**Consequences:** تا آن زمان هیچ فایلی منتشر نمی‌شود. باید در LICENSES.md و اینجا پیگیری شود.

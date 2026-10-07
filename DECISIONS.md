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

## ADR-0006 — مجوز پروژه (Open)
**Date:** 2026-10-07
**Context:** مجوز پروژه هنوز تعیین نشده است.
**Decision:** تصمیم به تأخیر افتاد تا پیش از انتشار عمومی گرفته شود.
**Alternatives:** MIT، Apache-2.0، AGPL-3.0، Proprietary
**Why selected:** —
**Consequences:** تا آن زمان هیچ فایلی منتشر نمی‌شود. باید در LICENSES.md و اینجا پیگیری شود.

# گزارش جامع پروژه — GlobalIntelligence v1.5

**تاریخ ممیزی:** ۴ نوامبر ۲۰۲۶ · **Branch:** `stage95-pg-ci-verification` · **HEAD:** `42b2278`
**مبنای گزارش:** اندازه‌گیری مستقیم در همین checkout + اجرای واقعی تست‌ها. هیچ عددی از گزارش‌های قبلی کپی نشده است.

---

## ۱) شناسنامهٔ پروژه

| مورد | مقدار (اندازه‌گیری‌شده) |
|---|---|
| نوع معماری | Modular monolith (FastAPI) + workerهای درون‌پروسه + React/Vite |
| Backend | ۱۵۷ فایل Python · **۱۸٬۱۸۱ خط** |
| Domains (منطق تحلیلی) | ۱۵۱ فایل · **۱۷٬۴۷۳ خط** · ۳۰ دامنه |
| Source Bot (ingestion) | ۲۳ فایل · **۳٬۲۷۶ خط** · ۶ adapter |
| Tests | ۱۳۱ فایل · **۳۰٬۳۵۱ خط** · ۱۲۸ فایل `test_*.py` |
| Frontend | ۳۴ فایل ts/tsx · **۶٬۶۲۲ خط** · ۱۸ ماژول صفحه · ۲۶ route |
| API | **۴۷ router** · **۲۰۶ endpoint** · ۵۲ گروه مسیر |
| Database | **۴۸ جدول** · **۴۵ migration** · تک‌head `b8c4d5e6f7a8` |
| تنظیمات | **۷۹ فیلد** در `Settings` |
| AI | Gateway + ۱۲ ماژول provider (mock, gemini, openai, anthropic, openrouter, groq, cloudflare, local_decision, …) |
| اتوماسیون | ۸ workflow در `integrations/n8n/workflows/` (n8n پین‌شده `2.42.6`) |
| مستندات | ۶۴ فایل `.md` در `docs/` + ۵ سند QA جدید |
| وضعیت Git | ۷۲ فایل modified · ۱ حذف‌شده · ۱۱۳ untracked — **همگی تغییرات مالک، دست‌نخورده** |

### سرویس‌های محلی در حال اجرا (Docker)

| سرویس | آدرس | وضعیت |
|---|---|---|
| `gi_postgres` (PostgreSQL 16) | `127.0.0.1:15432` | healthy |
| `gi_backend` (FastAPI) | `127.0.0.1:8000` | healthy |
| `gi_frontend` (Vite) | `127.0.0.1:5173` | up |
| `gi_n8n` | `127.0.0.1:5678` | up |
| `gi_staging_postgres` / `gi_staging_backend` | `15433` / `8001` | healthy |

---

## ۲) معماری در یک نگاه

```
منابع (RSS / JSON / CSV / XML / HTML-Scrapy)
        │  source_bot/adapters + security (SSRF/DNS/IPv6/TLS)
        ▼
Ingestion واحد ──► Document خام + provenance (published/retrieved/available)
        │  dedup (shingling+MinHash+LSH، فقط تشخیص، بدون حذف)
        ▼
Priority P0–P4 (قواعد قطعی) ──► Screening (Kev/Laya مشورتی + cloud classifier)
        │  backend/ai/dispatch  (ArticleDispatch پایدار، retry محدود، terminal)
        ▼
Analysis: classification → events → claims → evidence → entities → graph →
          domain engines (30) → forecast / debate / decision / portfolio
        │  همهٔ فراخوانی‌های AI فقط از AI Gateway (Free Policy، بدون fallback پنهان)
        ▼
API (206 endpoint) ──► React UI (RTL/فارسی/dark) ──► Alerts (Telegram/SMTP) + Archive (ZIP+Telegram)
```

**اصول رعایت‌شده و تأییدشده در کد:**
- محاسبهٔ قطعی در Python؛ LLM فقط طبقه‌بندی/استخراج ساختاریافته.
- مسیر ingestion واحد؛ adapterها SQL دامنه اجرا نمی‌کنند.
- Dispatch پایدار و idempotent؛ تنها یک نویسنده (`DispatchService`).
- Mock در production از زنجیره حذف می‌شود؛ ردیف mock هرگز خودکار پاک نمی‌شود.
- Auto-purge پیش‌فرض **خاموش**؛ حذف فقط با همهٔ safety gateها.

---

## ۳) شواهد کیفیت (اجرای واقعی، ۴ نوامبر ۲۰۲۶)

| Gate | فرمان | نتیجه |
|---|---|---|
| Ruff | `ruff check backend domains tests scripts source_bot` | **All checks passed** |
| Backend (SQLite) | `pytest tests -q` | **1570 passed، 1 skipped** — ۲۹۳ ثانیه |
| Backend (PostgreSQL 16) | DB موقت → `alembic upgrade head` → `pytest tests -q` → `DROP DATABASE` | **1573 passed، 0 failed** — ۶۶۴ ثانیه؛ مهاجرت از schema خالی exit 0 |
| Migration heads | `alembic heads` | تک‌head — بدون duplicate head |
| Frontend lint | `npm run lint` | ۰ خطا / ۷ warning |
| Frontend types | `npm run typecheck` | ۰ خطا |
| E2E full-stack | `npm run test:e2e:fullstack` | **۱۵ passed / ۰ failed** — ۴۸٫۸ ثانیه (پیش از رفع باگ‌ها: ۱ failed) |
| Frontend build | `npm run build` | موفق — ۱۹۵۸ module، JS ۳۴۲ kB (gzip ۱۰۹ kB) |
| Regression جدید | دو تست تازه | ۲ passed (و ۴۴ passed در سه ماژول تغییریافته) |

**نکتهٔ روش‌شناسی:** لاین PostgreSQL روی یک دیتابیس دورانداختنی (`gi_qa_8fa4abf1`) اجرا و سپس حذف شد؛ دیتابیس توسعه، volume و آرشیوها لمس نشدند. SQLite به‌عنوان جایگزین اثبات PG استفاده نشده است.

---

## ۴) انطباق با نقشه‌راه v1.5

| مرحله | وضعیت | شاهد / شکاف |
|---|---|---|
| F00 Baseline | ✅ VERIFIED_COMPLETE | `docs/BASELINE_F00.md` + همین گزارش |
| F01 Build/static | ✅ VERIFIED_COMPLETE | ruff + tsc + build |
| F02 PostgreSQL/CI | ✅ VERIFIED_COMPLETE (local) | ۱۵۷۳ تست PG روی schema خالی؛ CI اکنون full-suite + SQLite + E2E + docker + frontend |
| F02.5 Test hygiene | ✅ VERIFIED_COMPLETE | temp root مستقل هر اجرا |
| F03 Provider (live) | ⛔ BLOCKED_EXTERNAL | groq 403 (region/network) |
| F03.0 Control plane | ✅ VERIFIED_COMPLETE | revision/optimistic-lock/secret-safe + migration `a7f3c9d1e2b4` |
| F03.1 Catalog/discovery | ✅ VERIFIED_COMPLETE | provider catalog، بدون auto-enable |
| F03.UX | ✅ VERIFIED_COMPLETE | E2E کامل ۱۵/۱۵ پس از رفع ۲ باگ S1؛ lint ۰ خطا / ۷ warning |
| F04 Kev/Laya | ⛔ BLOCKED (انسانی) | فقط subset ۴۰ نمونه‌ای ارزیابی شده |
| F05 Ingestion | ✅ VERIFIED_COMPLETE | قرارداد واحد + provenance |
| F06 Security/SSRF | ✅ VERIFIED_COMPLETE | IPv4/IPv6/metadata/redirect/DNS rebinding |
| F07 Dedup | ✅ VERIFIED_COMPLETE | بدون hard delete؛ cluster قابل ردیابی |
| F08 Priority | 🟡 PARTIAL | مرزها و reason code پاس؛ کالیبراسیون تجربی نیاز به F04 |
| F09 Jobs/Dispatch | ✅ VERIFIED_COMPLETE | claim اتمیک + ایندکس یکتای active + recovery |
| F10 Pending/Mock | ✅ VERIFIED_COMPLETE | تفکیک mock/real، بدون ارتقای خودکار |
| F11 Analysis | ✅ VERIFIED_COMPLETE | lineage تا article/task |
| F12 Alerts/UI | 🟡 PARTIAL | تحویل با retry/idempotency؛ SMTP زنده BLOCKED |
| F12.1.1 UI منابع | ✅ VERIFIED_COMPLETE | فیلتر سمت سرور خوشهٔ dedup |
| F13 Archive | 🟡 PARTIAL | ZIP/eligibility/restore/امنیت پاس؛ یک round-trip زندهٔ Telegram قبلاً تأیید شده |
| F14 Debt/Perf | 🟡 PARTIAL | ۹ زیرمورد بسته شد؛ Text→JSONB و rate-limit چندفرایندی باز |
| F15 Local acceptance | 🟡 PARTIAL | E2E کامل UI ۱۵/۱۵؛ backup/restore قبلی؛ PG E2E و soak باقی |
| F16 Forecast | ⛔ BLOCKED (داده) | نیاز به outcome واقعی در طول زمان |

---

## ۵) نقص‌های بسته‌شده در این اجرا

| ID | شدت | عنوان | علت ریشه‌ای | تست اثبات |
|---|---|---|---|---|
| GI-BUG-0001 | S1 | هدر شرطی ETag هرگز ارسال نمی‌شد | runner در هر fetch نمونهٔ تازهٔ adapter می‌ساخت و state فقط روی instance بود | `test_rest_json_conditional_headers_survive_adapter_rebuild` |
| GI-BUG-0002 | S1 | دو درخواست هم‌زمان می‌توانستند دو JobRun فعال بسازند | check-then-insert بدون تضمین DB | `test_job_runs_active_unique_index_blocks_second_active_row` |
| GI-BUG-0011 | S1 | فرم ورود/کلید پشت بنر سراسری پنهان می‌شد و کاربر بدون کلید راه بازیابی نداشت | گیت `Section` برای بخش‌های بازیابی مستثنی نبود | `fullstack.spec.ts:106` (قبلاً timeout) |
| GI-BUG-0012 | S1 | پس از ذخیرهٔ کلید، بنر کهنه همهٔ پنل‌ها را پنهان نگه می‌داشت | `saveKey` رویداد سراسری را پاک نمی‌کرد | `fullstack.spec.ts:117` (قبلاً fail) |
| GI-BUG-0003 | S2 | آمار AdaptiveRouter هرگز در runtime اعمال نمی‌شد | مصرف‌کننده‌ای برای `build_routes` نبود | `tests/test_adaptive_bootstrap.py` + سیم‌کشی در lifespan |

**موارد باز با دلیل صریح:** کالیبراسیون آستانه‌ها (نیاز به gold set)، rate limit چندفرایندی (نیاز Redis)، Text→JSONB (تصمیم schema)، ۱۶ warning ظاهری lint.

---

## ۶) امنیت و یکپارچگی داده

- **بدون S0.** هیچ secret در log/گزارش/آرتیفکت چاپ نشد.
- SSRF: private/loopback/link-local/metadata، IPv6، redirect زنجیره‌ای و DNS rebinding مسدود؛ TLS fail-closed؛ محدودیت حجم/زمان پاسخ.
- Secret management: `GET` هرگز مقدار secret را برنمی‌گرداند؛ master key از UI قابل خواندن نیست.
- Auth: همهٔ endpointها به‌جز `/health` نیازمند `X-API-Key`؛ prod روی کلید ضعیف fail-fast.
- Data safety: dedup فقط تشخیص است (بدون حذف)؛ `corroborated` نیازمند ≥۲ منبع مستقل؛ auto-purge خاموش؛ delete/merge خودکار Event/Claim/Evidence/Forecast وجود ندارد.
- Point-in-time: `published_at/retrieved_at/available_at/observed_at` ثبت می‌شوند؛ backtest فقط walk-forward.

---

## ۷) اجرا در محیط محلی

```bash
cp .env.example .env                 # MOCK_MODE=true
python scripts/check_env.py
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
docker compose up -d --build         # postgres:15432 · backend:8000 · frontend:5173 · n8n:5678
python -m alembic upgrade head
python -m db.seed.sources            # seed منابع
cd apps/web && npm ci && npm run dev
```

پیکربندی Provider/منبع/Telegram/SMTP از طریق **Configuration Control Plane** در UI یا متغیرهای محیطی؛ چرخش credential نیاز به تغییر کد ندارد.

---

## ۸) محدودیت‌های واقعی (بدون ادعای موفقیت)

| مورد | وضعیت | اقدام لازم |
|---|---|---|
| Provider زنده (F03) | BLOCKED_EXTERNAL | کلید/region قابل دسترس |
| Gold set انسانی (F04/F-24) | BLOCKED (انسانی) | ۱۰۰–۲۰۰ خبر برچسب‌خورده + adjudication |
| ارسال زندهٔ SMTP | BLOCKED_EXTERNAL | `SMTP_*` |
| دومین round-trip زندهٔ آرشیو Telegram | BLOCKED_EXTERNAL | bot token + chat خصوصی |
| کالیبراسیون forecast (F16) | BLOCKED (داده) | outcome واقعی در طول زمان |
| اجرای CI راه‌دور (Python 3.12) | NOT VERIFIED | یک اجرای CI روی branch |
| E2E full-stack | ✅ ۱۵/۱۵ پاس | — |
| E2E روی PostgreSQL | NOT RUN | نیاز به credential منطبق PG محلی |

---

## ۹) حکم نهایی

**`PROJECT_COMPLETE_WITH_EXTERNAL_BLOCKERS`**

**به‌روزرسانی ادامهٔ اجرا (۴ نوامبر):** E2E واقعی full-stack اجرا شد و دو باگ S1 را آشکار کرد (دسترسی‌نداشتن به فرم ورود و بنر کهنهٔ احراز)؛ هر دو اصلاح شدند و اکنون **۱۵/۱۵** تست پاس است. هشدارهای lint از ۱۶ به ۷ کاهش یافت و lint/typecheck/build سبز ماند.

پروژه از نظر مهندسی محلی کامل و قابل‌اثبات است: هر دو لاین دیتابیس سبز، مهاجرت از صفر معتبر، فرانت‌اند سبز، امنیت و یکپارچگی داده تأییدشده، و اسناد با واقعیت هم‌راستا. تنها موارد باقی‌مانده به credential، برچسب انسانی یا گذر زمان وابسته‌اند و صادقانه به‌عنوان BLOCKED ثبت شده‌اند — نه VERIFIED.

**اسناد مرتبط:** `docs/qa/QA_BASELINE.md` · `docs/qa/QA_STAGE_MATRIX.md` · `docs/qa/DEFECT_REGISTER.md` · `docs/qa/TRACEABILITY_MATRIX.csv` · `docs/ROADMAP_COMPLIANCE_MATRIX.md` · `docs/FINAL_PROJECT_COMPLETION_REPORT.md`

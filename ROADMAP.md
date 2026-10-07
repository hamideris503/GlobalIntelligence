# ROADMAP.md

> نقشه راه GlobalIntelligence — ۵۲ فاز
> اصل: هر بار فقط یک Phase فعال است. از Phase فعلی جلوتر نمی‌رویم.

**Phase فعلی:** 0

---

## Milestoneها

| Milestone | مسیر | فازها |
|---|---|---|
| **M1 — Intelligence Core** | SOURCE → NEWS → PostgreSQL → AI Gateway → Classification → Event → Claim → Evidence → Dashboard | 7–15, 40 |
| **M2 — Memory & Forecast** | DATA → WORLD STATE → HISTORICAL MEMORY → FORECAST → OUTCOME → EVALUATION | 16–20, 25–29 |
| **M3 — Decision Support** | WORLD STATE → SCENARIOS → RISK → DECISION → RECOMMENDATION | 30–34 |
| **M4 — Full Platform** | GLOBAL DATA → … → SELF-IMPROVEMENT | همه |

> ⚠️ اگر مسیر M1 سالم نبود، وارد بخش Forecast نمی‌شویم.

---

## Phase 0 — تعریف نهایی پروژه ✅ (این مرحله)
- Product specification، Architecture، Constraints
- Free-first rules، Goals، Non-goals
- ساخت اسناد پایه (README, ARCHITECTURE, ROADMAP, TASKS, PROGRESS, DECISIONS, LICENSES, DATA_SOURCES, AI_MODELS)

## Phase 1 — آماده‌سازی محیط ✅ (این مرحله)
- Git، Python، Node.js، Docker، Docker Compose (بررسی و تأیید شد)
- Repository، `.gitignore`، `.env.example`، اسکلت اجرایی (dependency files)

## Phase 2 — Skeleton ✅ (این مرحله)
- Backend FastAPI + endpoints: `/`, `/health`, `/health/db`
- Frontend React + Vite (RTL/Dark) + build موفق
- PostgreSQL در docker-compose + admin قرارداد اتصال
- n8n در docker-compose
- Health checkها + تست‌های pytest + Dockerfiles
- هدف محقق‌شده: بالا آمدن همه سرویس‌های پایه (Backend/DB به‌صورت پیوسته)

## Phase 3 — PostgreSQL ✅ (این مرحله)
- ORM models برای موجودیت‌های اصلی (۱۵ جدول)
- Alembic + migration اولیه (autogenerate) + اجرا در entrypoint بکاند
- session factory + `get_db` dependency
- Point-in-Time columns روی Document/Article/Event
- seed منابع اولیه + تست‌های مدل‌ها

## Phase 4 — n8n ✅ (این مرحله)
- راه‌اندازی n8n (در docker-compose از Phase 2)
- Workflow نمونه: Schedule Trigger → Backend → Database
- endpoint `/api/jobs/trigger` + جدول `job_runs` + migration
- import/publish خودکار workflow با اسکریپت
- تست شد: اجرای زمان‌بندی‌شده‌ی واقعی n8n رکورد در PostgreSQL ثبت کرد

## Phase 5 — AI Gateway ✅ (این مرحله)
- اینترفیس یکسان Provider (`generate`, `structured_generate`, `classify`, `extract`, `health`)
- Mock Provider (پیش‌فرض، بدون هزینه) + Providerهای HTTP (openai, anthropic, gemini, openrouter)
- Registry + routing مبتنی بر نقش/وظیفه
- Gateway با fallback/retry/timeout/logging/usage tracking
- endpointهای `/api/ai/generate` و `/api/ai/providers`
- تست شد: mock پاسخ داد، Providerهای بدون کلید → `not configured` (بدون crash)

## Phase 6 — Mock AI

## Phase 7 — Data Source Registry ✅ (این مرحله)
- مدل `Source` (از Phase 3) + سرویس `SourceRegistry` (CRUD + health tracking)
- API کامل `/api/sources` (list/create/get/update/health)
- seed ۱۴ منبع معتبر رایگان با امتیاز اولیه
- تست شد: ۱۵ منبع، فیلتر، ساخت، ثبت سلامت

## Phase 8 — News Ingestion ✅ (این مرحله)
- fetcherها: RSS/Atom (stdlib) + Mock (آفلاین)
- normalizer: پاک‌سازی، تشخیص زبان، hash/content_hash، Point-in-Time
- pipeline: SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE
- dedup سبک بر اساس content_hash
- API: `/api/ingest`, `/api/ingest/all`, `/api/ingest/documents`
- CLI worker: `python -m domains.news.run_ingest`
- workflow n8n زمان‌بندی‌شده برای ingestion
- تست شد: ۳ سند ذخیره، اجرای دوباره dedup شد

## Phase 9 — Deduplication ✅ (این مرحله)
- shingling + MinHash + LSH banding (بدون وابستگی خارجی)
- Union-Find برای خوشه‌بندی
- تشخیص exact / near-duplicate / repost (بین منابع)
- سرویس `DedupService` + CLI + API `/api/dedup/run`
- ادغام اختیاری با ingestion (`DEDUP_ON_INGEST`)
- آستانه‌ی قابل تنظیم (`DEDUP_NEAR_THRESHOLD`)
- تست شد: repost بین دو منبع تشخیص داده شد

## Phase 10 — Article Classification ✅ (این مرحله)
- prompt نسخه‌دار طبقه‌بندی/استخراج + JSON Schema
- `ArticleClassifier` با AI Gateway (نقش fast_extraction)
- محاسبه‌ی deterministic Importance Score (بند 22)
- استخراج topics/entities/country/sentiment/stance/summary
- API `/api/classify/*` + CLI
- تست شد: ۳ مقاله طبقه‌بندی شدند

## Phase 11 — Event Extraction
- چند مقاله مرتبط → یک Event

## Phase 12 — Claim Extraction
- Event / Article → Claims

## Phase 13 — Evidence Engine
- supporting + contradicting evidence

## Phase 14 — Source Independence
- تشخیص وابستگی منابع

## Phase 15 — Knowledge Graph
- Entity + Relationship

## Phase 16 — Economic Data
- inflation، GDP، employment، rates، trade، liquidity

## Phase 17 — Market Data
- FX، Gold، Oil، Stocks، Bonds، Commodities

## Phase 18 — World State
- ساخت Current World State

## Phase 19 — Historical Memory
- historical events، states، snapshots

## Phase 20 — Historical Analogue
- Current state ↔ Historical similar states

## Phase 21 — Macro Engine
## Phase 22 — Geopolitical Engine
## Phase 23 — Social Intelligence
## Phase 24 — Narrative Engine
## Phase 25 — Forecast Engine
- ابتدا Baselineها (naive, historical mean, random walk) سپس ARIMA/ETS/Theta/ML/Bayesian

## Phase 26 — Forecast Ledger
## Phase 27 — Outcome Engine
## Phase 28 — Forecast Evaluation (Brier, Log Loss, MAE, RMSE, Calibration)
## Phase 29 — Forecast Tournament
## Phase 30 — Scenario Engine (Base/Bull/Bear/Tail)
## Phase 31 — Risk Engine
## Phase 32 — Decision Engine
## Phase 33 — Iran Mode
## Phase 34 — Iran Transmission
## Phase 35 — Portfolio Intelligence
## Phase 36 — Model Performance
## Phase 37 — Adaptive AI Router
## Phase 38 — Audit / Replay
## Phase 39 — Self Evaluation
## Phase 40 — Dashboard
## Phase 41 — Daily Intelligence
## Phase 42 — Weekly Intelligence
## Phase 43 — Alerts
## Phase 44 — Security Hardening
## Phase 45 — Backup
## Phase 46 — Docker Production
## Phase 47 — Staging
## Phase 48 — VPS Deployment
## Phase 49 — 24/7 Automation
## Phase 50 — Production Monitoring
## Phase 51 — Long-Term Learning
## Phase 52 — Advanced Research (GraphRAG, Bayesian networks, causal discovery, …)

---

## در Phase 0 عمداً ساخته نمی‌شود
Forecast Engine، Knowledge Graph، Trading، Complex AI agents، Microservices، VPS.

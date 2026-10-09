# ROADMAP.md

> نقشه راه GlobalIntelligence — ۵۲ فاز
> اصل: هر بار فقط یک Phase فعال است. از Phase فعلی جلوتر نمی‌رویم.

**Phase فعلی:** 24

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

## Phase 0 — تعریف نهایی پروژه ✅
- Product specification، Architecture، Constraints
- Free-first rules، Goals، Non-goals
- ساخت اسناد پایه (README, ARCHITECTURE, ROADMAP, TASKS, PROGRESS, DECISIONS, LICENSES, DATA_SOURCES, AI_MODELS)

## Phase 1 — آماده‌سازی محیط ✅
- Git، Python، Node.js، Docker، Docker Compose (بررسی و تأیید شد)
- Repository، `.gitignore`، `.env.example`، اسکلت اجرایی (dependency files)

## Phase 2 — Skeleton ✅
- Backend FastAPI + endpoints: `/`, `/health`, `/health/db`
- Frontend React + Vite (RTL/Dark) + build موفق
- PostgreSQL در docker-compose + admin قرارداد اتصال
- n8n در docker-compose
- Health checkها + تست‌های pytest + Dockerfiles
- هدف محقق‌شده: بالا آمدن همه سرویس‌های پایه (Backend/DB به‌صورت پیوسته)

## Phase 3 — PostgreSQL ✅
- ORM models برای موجودیت‌های اصلی (۱۵ جدول)
- Alembic + migration اولیه (autogenerate) + اجرا در entrypoint بکاند
- session factory + `get_db` dependency
- Point-in-Time columns روی Document/Article/Event
- seed منابع اولیه + تست‌های مدل‌ها

## Phase 4 — n8n ✅
- راه‌اندازی n8n (در docker-compose از Phase 2)
- Workflow نمونه: Schedule Trigger → Backend → Database
- endpoint `/api/jobs/trigger` + جدول `job_runs` + migration
- import/publish خودکار workflow با اسکریپت
- تست شد: اجرای زمان‌بندی‌شده‌ی واقعی n8n رکورد در PostgreSQL ثبت کرد

## Phase 5 — AI Gateway ✅
- اینترفیس یکسان Provider (`generate`, `structured_generate`, `classify`, `extract`, `health`)
- Mock Provider (پیش‌فرض، بدون هزینه) + Providerهای HTTP (openai, anthropic, gemini, openrouter)
- Registry + routing مبتنی بر نقش/وظیفه
- Gateway با fallback/retry/timeout/logging/usage tracking
- endpointهای `/api/ai/generate` و `/api/ai/providers`
- تست شد: mock پاسخ داد، Providerهای بدون کلید → `not configured` (بدون crash)

## Phase 6 — Mock AI ✅ (در Phase 5 پوشش داده شد)
- Mock Provider به‌عنوان Provider پیش‌فرض و schema-driven (بدون هزینه/اینترنت)

## Phase 7 — Data Source Registry ✅
- مدل `Source` (از Phase 3) + سرویس `SourceRegistry` (CRUD + health tracking)
- API کامل `/api/sources` (list/create/get/update/health)
- seed ۱۴ منبع معتبر رایگان با امتیاز اولیه
- تست شد: ۱۵ منبع، فیلتر، ساخت، ثبت سلامت

## Phase 8 — News Ingestion ✅
- fetcherها: RSS/Atom (stdlib) + Mock (آفلاین)
- normalizer: پاک‌سازی، تشخیص زبان، hash/content_hash، Point-in-Time
- pipeline: SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE
- dedup سبک بر اساس content_hash
- API: `/api/ingest`, `/api/ingest/all`, `/api/ingest/documents`
- CLI worker: `python -m domains.news.run_ingest`
- workflow n8n زمان‌بندی‌شده برای ingestion
- تست شد: ۳ سند ذخیره، اجرای دوباره dedup شد

## Phase 9 — Deduplication ✅
- shingling + MinHash + LSH banding (بدون وابستگی خارجی)
- Union-Find برای خوشه‌بندی
- تشخیص exact / near-duplicate / repost (بین منابع)
- سرویس `DedupService` + CLI + API `/api/dedup/run`
- ادغام اختیاری با ingestion (`DEDUP_ON_INGEST`)
- آستانه‌ی قابل تنظیم (`DEDUP_NEAR_THRESHOLD`)
- تست شد: repost بین دو منبع تشخیص داده شد

## Phase 10 — Article Classification ✅
- prompt نسخه‌دار طبقه‌بندی/استخراج + JSON Schema
- `ArticleClassifier` با AI Gateway (نقش fast_extraction)
- محاسبه‌ی deterministic Importance Score (بند 22)
- استخراج topics/entities/country/sentiment/stance/summary
- API `/api/classify/*` + CLI
- تست شد: ۳ مقاله طبقه‌بندی شدند

## Phase 11 — Event Extraction ✅
- گروه‌بندی مقالات بر اساس خوشه‌ی dedup
- استخراج Event با AI Gateway (structured JSON، prompt نسخه‌دار)
- اگر AI در دسترس نباشد، ساخت Event سبک از خود مقاله (fallback)
- اتصال مقالات به رویداد (`event_id`, `event_cluster`)
- API: `/api/events/extract`, `/api/events`
- CLI: `python -m domains.events.run_extract`
- تست شد: ۶۰ مقاله → ۳ رویداد

## Phase 12 — Claim Extraction ✅
- گروه‌بندی بر Event؛ یک‌بار به‌ازای هر رویداد (`claims_extracted`)
- استخراج Claimهای اتمی (subject-predicate-object) با AI Gateway
- fallback سبک در نبود AI
- API: `/api/claims/extract`, `/api/claims`
- CLI: `python -m domains.claims.run_extract`
- تست شد: ۳ رویداد → ۳ Claim

## Phase 13 — Evidence Engine ✅
- supporting + contradicting evidence (dir: supports/contradicts, weight, confidence)
- یک‌بار به‌ازای هر Claim (`evidence_extracted`)
- `verify_status` ماتریس قطعی: unverified/single_source/corroborated/contradicted/disputed
- پر کردن `source_id`/`document_id` برای استقلال منابع
- API: `/api/claims/evidence`, `GET /api/claims`, `GET /api/claims/{id}/evidence`
- CLI: `python -m domains.claims.run_evidence`
- تست شد: ۳ Claim → ۳ Evidence

## Phase 14 — Source Independence ✅
- جدول `source_dependencies` (گراف وابستگی منابع: syndication/aggregator/same_owner/repost)
- تشخیص heuristic هم‌دامنه + یال دستی؛ Union-Find برای فروکاست به منبع مستقل
- `Claim.supporting_source_count` (mention) و `independent_source_count` (تأیید مستقل) + `source_independence`
- `corroborated` فقط با ≥۲ منبع *مستقل* (نه صرفاً ≥۲ mention)
- API: `/api/independence/run`, `/api/independence/dependencies`, `/api/independence/groups`
- CLI: `python -m domains.news.run_independence`
- تست شد: ۱۹ منبع → ۱۸ گروه؛ ۳ Claim → corroborated با independence=0.947

## Phase 15 — Knowledge Graph ✅ (این مرحله)
- Entity resolution نام‌محور (canonical/casefold + aliases + ارتقای نوع)
- استخراج رابطه‌ی جهت‌دار با AI (enum از RelationType) + fallback هم‌رویدادی (`affects`)
- `Event.graph_extracted` برای idempotency؛ تقویت وزن یال تکراری
- فیلد `EntityRelationship.confidence` + migration `34b4e7f87ba7`
- API: `/api/graph/extract`, `/api/graph/entities`, `/api/graph/relationships`, `/api/graph/neighbors/{id}`
- CLI: `python -m domains.graph.run_graph`
- تست شد: Fed → Federal Reserve→affects→US Dollar

## Phase 16 — Economic Data ✅ (این مرحله)
- Enum های `EconomicIndicator` (inflation/gdp/unemployment/interest_rate/trade_balance/liquidity) + `DataFrequency`
- فیلدهای `series_id` و `meta` روی `MacroObservation` + migration `9800836e7fcc`
- `WorldBankFetcher` (API رایگان بانک جهانی، بدون کلید) + `MockFetcher` (deterministic)
- `EconomicDataService`: fetch → normalize → upsert idempotent
- API: `POST /api/economic/fetch`, `GET /api/economic/observations`, `/indicators`, `/latest`
- CLI: `python -m domains.macro.run_fetch`
- تست شد: ۹ تست پاس؛ کل ۱۲۰ تست پاس

## Phase 17 — Market Data ✅ (این مرحله)
- کاتالوگ ۱۳ نماد: FX (EURUSD/GBPUSD/USDJPY/USDCHF)، طلا/نقره (XAUUSD/XAGUSD)، نفت (WTI/BRENT/NATGAS)، سهام (SPX/AAPL)، اوراق (US10Y)، مس (COPPER)
- Fetcherهای رایگان بدون کلید: `ErApiFxFetcher` + `EcbFxFetcher` (fallback رسمی)، `GoldApiFetcher`، `YahooFetcher`، `MockFetcher`
- `MarketDataService`: زنجیره‌ی primary→fallback برای هر نماد + upsert idempotent در `MarketObservation` (بدون migration جدید)
- API: `POST /api/markets/fetch`, `GET /api/markets/observations`, `/symbols`, `/latest`
- CLI: `python -m domains.markets.run_fetch`
- تست شد: ۱۱ تست پاس؛ کل ۱۳۱ تست پاس؛ زنده هر ۱۳ نماد با مقادیر واقعی

## Phase 18 — World State ✅ (این مرحله)
- ۹ سیگنال قطعی 0..1 (growth/inflation/liquidity/stress/geopolitical/energy/trade/political/social) + رژیم کلان (overheating/expansion/stagflation/slowdown) و بازار (stress/risk_on/tight/neutral)
- `WorldStateBuilder`: macro + market + events/claims → snapshot با value_metadata کامل (value/timestamp/source/method/confidence)
- هر build یک snapshot جدید (State Memory)؛ YoY تک‌کشوری (ترجیح USA)
- API: `POST /api/world-state/build`, `GET /api/world-state/current`, `/history`
- CLI: `python -m domains.worldstate.run_build`
- بدون migration جدید (یافته‌ی ممیزی: ستون‌های `captured_at`/`confidence` از قبل موجود بودند)
- تست شد: ۱۰ تست پاس؛ کل ۱۴۱ تست پاس؛ زنده snapshot واقعی (slowdown/risk_on)

## Phase 19 — Historical Memory ✅ (این مرحله)
- جدول `memory_records` (layer/ref_type/ref_id + title/summary/importance + observed_at/recorded_at + record_metadata) + migration `672f88b5d692`
- Enum `MemoryLayer` (۷ لایه؛ Phase 19 فقط raw/event/state را پر می‌کند)
- `HistoricalMemoryService`: قوانین گزینش قطعی (event_score آستانه‌ی 0.3، importance≥7، همه‌ی snapshotها) + idempotent + `timeline(as_of)` Point-in-Time + `stats`
- API: `POST /api/memory/archive`, `GET /api/memory/timeline`, `/stats`, `/records`
- CLI: `python -m domains.memory.run_archive`
- تست شد: ۹ تست پاس؛ کل ۱۵۰ تست پاس؛ زنده ۱۳۵ raw + ۳ event + ۳ state، timeline گذشته=۰، اجرای دوباره=۱۴۱ duplicate

## Phase 20 — Historical Analogue ✅ (این مرحله)
- فاصله‌ی برداری ۹ سیگنال (`euclidean` پیش‌فرض + `cosine`) با توابع خالص؛ شباهت 0..1 + واگرایی هر سیگنال
- `AnalogueService`: مرجع (مشخص/آخرین) ↔ فقط snapshotهای قدیمی‌تر + رتبه‌بندی + `aftermath` (snapshotهای بعدی و رویدادهای حافظه‌ی بعدی)
- API: `GET /api/analogues`, `GET /api/analogues/{id}/aftermath` (404/422 دقیق)
- CLI: `python -m domains.analogue.run_analogues`
- فقط خواندنی: بدون migration، بدون AI
- تست شد: ۱۲ تست پاس؛ کل ۱۶۲ تست پاس؛ زنده ۲ آنالوگ با similarity=1.0

## Phase 21 — Macro Engine ✅ (این مرحله)
- توابع خالص `analytics`: yoy/شتاب/z-score/momentum برچسب‌دار + confidence بر اساس تعداد نقاط
- `MacroEngine`: تحلیل هر سری (indicator×country) + upsert idempotent در `macro_assessments` + migration `ce70a0fa41c3`
- API: `POST /api/macro/analyze`, `GET /api/macro/assessments`, `GET /api/macro/overview?country=`
- CLI: `python -m domains.macro.run_analyze`
- تست شد: ۱۰ تست پاس؛ کل ۱۸۷ تست پاس؛ زنده ۲ سری (USA inflation stable، IRN gdp decelerating)
## Phase 22 — Geopolitical Engine ✅ (این مرحله)
- تابع خالص `tension` (v1 مستند: 0.2 حجم + 0.3 غافلگیری + 0.3 مناقشه + 0.2 تحریم) + confidence از تعداد رویداد
- `GeopoliticalEngine`: گروه‌بندی رویدادها بر بازیگر (نرمال‌سازی نام) + شمارش یال‌های sanctions/competes گراف + upsert ماهانه در `geopolitical_assessments` + migration `5cf8f59a349b`
- API: `POST /api/geopolitics/analyze`, `GET /api/geopolitics/assessments`, `GET /api/geopolitics/tensions`
- CLI: `python -m domains.geopolitics.run_analyze`
- تست شد: ۹ تست پاس؛ کل ۱۹۶ تست پاس؛ زنده ۱ بازیگر (mock: tension=0.2)
## Phase 23 — Social Intelligence ✅ (این مرحله)
- تابع خالص `mood` (میانگین احساس، سهم ناآرامی از SOCIAL_TOPICS، ترکیب موضع) + confidence از تعداد مقاله
- `SocialEngine`: گروه‌بندی مقالات done بر قلمرو (topic|country) + upsert ماهانه در `social_assessments` + migration `bdd7eabe4da2`
- API: `POST /api/society/analyze`, `GET /api/society/assessments`, `GET /api/society/mood`
- CLI: `python -m domains.society.run_analyze`
- تست شد: ۸ تست پاس؛ کل ۲۰۴ تست پاس؛ زنده مسیر واقعی با مقاله تستی (۳ قلمرو) + پاک‌سازی
## Phase 24 — Narrative Engine ✅ (این مرحله)
- پیوند رویدادها (۱ موجودیت مشترک یا ۲ موضوع مشترک) + Union-Find + عنوان از عبارت‌های پربسامد + strength/واگرایی موضع
- `NarrativeEngine`: خوشه=روایت + signature هش + upsert ماهانه در `narratives` + migration `c5ae5339ede9`
- API: `POST /api/narratives/build`, `GET /api/narratives`, `GET /api/narratives/{id}`
- CLI: `python -m domains.narratives.run_build`
- تست شد: ۹ تست پاس؛ کل ۲۱۳ تست پاس؛ زنده ۱ روایت (۷۸ رویداد mock)
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

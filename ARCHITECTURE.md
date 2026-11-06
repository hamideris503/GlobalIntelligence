# ARCHITECTURE.md

> معماری فنی GlobalIntelligence
> نسخه: 0.2 (بازبینی ۲۸ اکتبر ۲۰۲۶ — پس از Stage 88–95)
> وضعیت: جاری و هم‌راستا با کد؛ فازهای 0–52 پیاده‌سازی شده‌اند و مراحل تثبیت/تکمیل در [`docs/ROADMAP_STAGE96_104.md`](docs/ROADMAP_STAGE96_104.md) است.

---

## 1. اصول معماری

1. **Modular Monolith + Workers** — در نسخه اول Microservice ساخته نمی‌شود. Backend + Database + Workers کافی است. مرزهای ماژولار از ابتدا رعایت می‌شوند تا استخراج سرویس در آینده ممکن باشد.
2. **Free-First** — هسته اصلی نباید به هیچ API پولی وابسته باشد.
3. **Provider-Agnostic AI** — همه‌ی تعامل با مدل‌های AI از طریق AI Gateway.
4. **PostgreSQL به‌عنوان منبع اصلی داده** (Single Source of Truth).
5. **Memory-First** — حافظه تاریخی از ابتدا در مدل داده لحاظ می‌شود.
6. **Point-in-Time Integrity** — ثبت زمان‌های published_at / retrieved_at / available_at / observed_at / revision_at.
7. **Deterministic Core** — محاسبات آماری در Python، تفسیر در LLM.
8. **Everything Replaceable** — هر Integration قابل حذف و جایگزینی است (Adapter Pattern).

---

## 2. نمای کلان سیستم (Runtime View)

```
                        ┌─────────────────────────────┐
        Internet ──────▶│      Reverse Proxy (prod)    │
                        └──────────────┬──────────────┘
                                       │
                       ┌───────────────┴────────────────┐
                       ▼                                ▼
              ┌─────────────────┐              ┌─────────────────┐
              │    Frontend     │              │   n8n (scheduler│
              │  React + Vite   │              │  & webhooks)    │
              └────────┬────────┘              └────────┬────────┘
                       │ HTTP                           │ HTTP
                       ▼                                ▼
              ┌──────────────────────────────────────────────────┐
              │                 Backend (FastAPI)                 │
              │  API · Auth · Services · AI Gateway · Domains    │
              └───────┬───────────────────────────────┬─────────┘
                      │                               │
                      ▼                               ▼
              ┌─────────────────┐            ┌─────────────────┐
              │   PostgreSQL    │            │    Workers      │
              │ (source of truth│◀──────────▶│ (ingest/analyze │
              │  + memory)      │            │  /forecast)     │
              └─────────────────┘            └────────┬────────┘
                                                       │
                                       ┌───────────────┼────────────────┐
                                       ▼               ▼                ▼
                                 AI Gateway      Data Sources     (optional)
                                 → Provider      (RSS/API/…)      Redis
```

---

## 3. نمای منطقی (Logical Pipeline)

```
WORLD
 ↓
DATA COLLECTION        (ingest adapters: RSS, APIs, datasets)
 ↓
NORMALIZATION          (unify schema, language, timestamps)
 ↓
DEDUPLICATION          (hash / near-duplicate / repost clusters)
 ↓
SOURCE & EVIDENCE ANALYSIS (credibility, independence)
 ↓
CLASSIFICATION & SCREENING (rules + advisory local models + AI Gateway)
 ↓
DISPATCH               (durable downstream tasks، idempotent، retry/terminal)
 ↓
EVENT / CLAIM / ENTITY EXTRACTION
 ↓
CENTRAL DATABASE       (PostgreSQL)
 ↓
WORLD STATE            (structured snapshot of the world)
 ↓
MACRO / MARKET / GEOPOLITICAL / SOCIAL ANALYSIS
 ↓
HISTORICAL MEMORY      (7 layers)
 ↓
FORECAST ENGINE
 ↓
SCENARIO ENGINE
 ↓
RISK ENGINE
 ↓
DECISION ENGINE
 ↓
RECOMMENDATION
 ↓
ACTUAL OUTCOME
 ↓
EVALUATION
 ↓
MODEL PERFORMANCE
 ↓
SELF-IMPROVEMENT
```

---

## 4. ساختار Repository

```
/apps
  /web                    # فرانت‌اند React + Vite

/backend
  /api                    # لایه HTTP: ۴۵ router, dependencies, schemas
  /core                   # config, logging, errors, base classes
  /auth                   # authentication + authorization
  /database              # engine, session, migrations glue
  /ai
    /gateway              # AI Gateway (orchestration، fallback، گیت mock در prod)
    /providers            # adapters: mock, gemini, openai, anthropic, openrouter, local_decision
    /schemas              # structured output schemas
    /routing              # task→model routing rules
    /prompts              # versioned prompt templates
    /evaluation           # AI performance tracking + هارنس ارزیابی/برچسب‌گذاری غربالگری
    /local_screening      # orchestrator/service/review غربالگری محلی (Kev/Laya)
    /local_runtimes       # supervisor اجرای محلی مدل‌ها (kev.serve / laya_wrapper)
    /dispatch             # صف تحویل بادوام: routing، service، runner
    free_policy.py        # سیاست مصرف رایگان؛ providerهای محلی معاف‌اند
  /services              # فعلاً placeholder (.gitkeep)؛ منطق کسب‌وکار در domains/ و backend/ai/ است

/workers                 # background jobs (collection, analysis, forecast) — فعلاً placeholder (.gitkeep)؛ اجرای فعلی درون‌پروسه‌ای است (`source_bot/jobs.py` + n8n)

/domains
  /news /events /claims /entities /macro /markets
  /geopolitics /society /forecast /risk /decision /iran
  /worldstate /scenarios /portfolio /memory /analogue /narratives
  /learning /research /briefings /alerts /audit /selfeval /ops /debate /ai_routing

/integrations
  /worldmonitor /investigator /openbb /tradingagents /n8n

/ml
  /features /models /evaluation /backtesting

/db
  /migrations /seed

/tests
/docs
/scripts
/config
/data
  /raw /sample
/docker
```

> **توجه:** این درخت وضعیت جاری است. تنها پوشه‌ای که هنوز placeholder است `workers/` است؛ اجرای پس‌زمینه فعلاً درون‌پروسه‌ای (`source_bot/jobs.py` + `BackgroundTasks`) یا از طریق workflowهای n8n انجام می‌شود.

---

## 5. AI Gateway

### 5.1 هدف
لایه‌ای مستقل بین Application و مدل‌های AI، تا هیچ Provider در منطق اصلی Hard-code نشود.

```
Application
  ↓
AI Gateway
  ↓
Provider Adapter
  ↓
Model
```

### 5.2 مسئولیت‌ها
- انتخاب مدل و Provider
- Fallback / Retry / Timeout
- Rate limit
- Structured output (JSON Schema)
- Logging
- Cost tracking / Token tracking
- Model version tracking / Prompt version tracking
- Error handling
- Provider health
- Task-specific routing

### 5.3 Interface پیشنهادی

```python
class AIProvider(Protocol):
    async def generate(self, prompt: str, **opts) -> AIResponse: ...
    async def structured_generate(self, prompt: str, schema: type, **opts) -> AIResponse: ...
    async def classify(self, text: str, labels: list[str], **opts) -> AIResponse: ...
    async def extract(self, text: str, schema: type, **opts) -> AIResponse: ...
    async def health(self) -> ProviderHealth: ...
```

### 5.4 نقش مدل‌ها (Logical Roles)
| نقش | کاربرد |
|---|---|
| Fast Extraction | classification، extraction، tagging، dedup assist |
| Deep Analysis | geopolitical، macro، multi-source synthesis، scenario |
| Critic | counter-evidence، contradiction، adversarial |
| Report | daily/weekly/executive reports |

نقش‌ها به مدل‌های مشخص Map می‌شوند (قابل تنظیم). جزئیات در [`AI_MODELS.md`](AI_MODELS.md).

### 5.5 مدل‌های تصمیم محلی (Kev / Laya)

- Kev و Laya مدل‌های تصمیم open-weight هستند، نه chat؛ API مشترک `POST /v1/systemone` با پرسش‌های typed (`noul` / `choice` / `score`).
- از طریق AI Gateway و adapter `providers/local_decision.py` صدا زده می‌شوند؛ supervisor در `ai/local_runtimes/` آن‌ها را به‌صورت subprocess مدیریت می‌کند.
- خروجی آن‌ها **مشورتی** است و در متادیتای classifier ثبت می‌شود؛ هیچ‌وقت جای قواعد قطعی یا classifier ابری را نمی‌گیرد. پیش‌فرض خاموش است.
- `ai/free_policy.py` این providerهای محلی را از سهمیهٔ مصرف رایگان معاف می‌کند (اجرا روی سخت‌افزار خودمان).
- در production زنجیرهٔ fallback نمی‌تواند به Kev/Laya به‌عنوان جانشین تصمیم پرریسک تکیه کند؛ جزئیات و وضعیت برچسب‌گذاری در [`docs/LOCAL_SCREENING.md`](docs/LOCAL_SCREENING.md).

---

## 6. مدل داده اصلی (Core Entities)

موجودیت‌های حداقلی (Phase 3+):

`Source`, `Document`, `Article`, `Claim`, `Evidence`, `Event`, `Entity`,
`Country`, `Company`, `Person`, `Organization`, `Asset`, `Indicator`,
`MarketObservation`, `MacroObservation`, `Narrative`, `WorldState`,
`Forecast`, `ForecastOutcome`, `Scenario`, `Recommendation`, `UserProfile`,
`Model`, `ModelRun`, `PromptVersion`, `AuditRecord`, `DecisionChange`,
`DataSnapshot`.

جدول‌های افزوده‌شده در Stage 88–95:

| موجودیت | نقش |
|---|---|
| `ArticleDispatch` | صف تحویل بادوام؛ کلید یکتا `(article_id, task_name)`، وضعیت‌های `pending/running/retryable/completed/terminal`، `attempts`، `next_retry_at` |
| `AIProviderRow`, `AIModelRow`, `AITokenLedger` | تنظیمات provider/مدل (کلید رمزشده) و دفتر مصرف روزانه با ردیابی برآورد/هزینه |
| `AlertRule`, `Alert` | قواعد آستانه و رکورد هشدار؛ تحویل کانالی هنوز پیاده نشده |
| `LearningInsight` | بینش‌های بلندمدت (روند خطا، نرخ رژیم، آستانهٔ چندک) |

فیلدهای کلیدی هرکدام در بخش 7 تا 10 توضیح داده شده‌اند.

---

## 7. Data Model — Ingestion

### Document
`id, source_id, url, title, raw_text, language, published_at, retrieved_at,
hash, content_hash, author, revision, license/terms metadata`

### Article
`title, summary, language, source, published_at, topics, entities, event_ids,
claims, sentiment, stance, importance, confidence, uncertainty,
duplicate_cluster, event_cluster`

### Source (Registry)
`source_id, name, domain, country, type, language, credibility_score,
historical_accuracy, correction_rate, independence_score,
primary_source_ratio, latency, license, terms, collection_method, active,
last_success, last_error`

---

## 8. Data Model — Analysis

### Event
`event_id, event_type, timestamp, location, actors, action, expected, actual,
surprise, affected_assets, affected_indicators, sources, confidence`

### Claim
`subject, predicate, object, claim_type, timestamp, sources,
supporting_evidence, contradicting_evidence, confidence, verification_status`

### Entity + Relationship
Entity types: Person, Country, Company, Organization, Government, Central Bank,
Asset, Commodity, Currency, Industry, Political Party, Event, Indicator.
Relationship types: owns, controls, exports_to, depends_on, allies_with,
sanctions, competes_with, supplies, affects, invests_in, regulates.

### WorldState
`growth_pressure, inflation_pressure, liquidity, financial_stress,
geopolitical_risk, energy_risk, trade_risk, political_risk, social_pressure,
macro_regime, market_regime`
هر مقدار دارای `value, timestamp, source, method, confidence`.

---

## 9. Data Model — Memory & Forecast

### حافظه ۷ لایه
1. Raw Memory — داده خام مهم
2. Event Memory — اتفاقات تاریخی
3. State Memory — snapshot وضعیت جهان
4. Forecast Memory — همه پیش‌بینی‌ها
5. Outcome Memory — نتیجه واقعی
6. Model Memory — عملکرد مدل‌ها
7. Decision Memory — تصمیم‌ها و تغییرشان

### Forecast (Ledger)
`forecast_id, created_at, valid_from, target_date, horizon, target, probability,
expected_value, interval, confidence, model, model_version, prompt_version,
evidence, assumptions, scenario, data_version`

### ForecastOutcome
اتصال `forecast → actual` پس از رسیدن target_date و ارزیابی.

### Scenario
Base / Bull / Bear / Tail — هرکدام: `probability, trigger, expected_effect,
affected_assets, risks, invalidation_criteria`.

### Recommendation
`asset, direction, horizon, score, confidence, expected_return, downside,
prob_up, prob_down, base/bull/bear/tail scenarios, evidence_for,
evidence_against, main_drivers, main_risks, invalidation, model, data_version,
timestamp`.

### Decision Enum
`STRONG_OPPORTUNITY, OPPORTUNITY, WATCH, NEUTRAL, REDUCE, AVOID, SPECULATIVE,
INSUFFICIENT_EVIDENCE`

---

## 10. Evaluation & Integrity

### Forecast Evaluation
- احتمالی: Brier Score، Log Loss، Calibration، ECE
- عددی: MAE، RMSE، MAPE (در صورت تناسب)، Prediction Interval Coverage، CRPS
- **ممنوعیت Random Shuffle**؛ فقط Walk-forward / Rolling / Expanding / Point-in-time.

### Point-in-Time Integrity
ثبت `published_at, retrieved_at, available_at, observed_at, revision_at`
برای جلوگیری از look-ahead، future leakage، revision leakage، survivorship bias.

### Reproducibility
هر Analysis ثبت می‌کند: input data version، model، provider، prompt version،
configuration، timestamp، code version.

---

## 11. Domainها (بخش‌های تحلیلی)

| Domain | مسئولیت |
|---|---|
| news | ingestion، normalize، dedup |
| events | event clustering |
| claims | claim + evidence extraction |
| entities | knowledge graph |
| macro | GDP, inflation, employment, … |
| markets | FX, gold, oil, stocks, bonds |
| geopolitics | actor interest/capability/constraint |
| society | demographics, unrest, sentiment |
| forecast | baseline + statistical + ML + Bayesian |
| risk | VaR/CVaR/Monte Carlo, tails |
| decision | decision framework + recommendation |
| iran | Iran Intelligence Mode + transmission model |
| worldstate | ۹ سیگنال قطعی + رژیم‌های macro/market |
| scenarios | چهار سناریو با احتمال و invalidation |
| portfolio | پورتفوی و snapshot |
| memory / analogue | حافظهٔ تاریخی چندلایه و مقایسهٔ آنالوگ |
| narratives | خوشه‌بندی روایت و قدرت آن |
| learning | یادگیرنده‌های قطعی بلندمدت |
| research | GraphRAG-lite |
| briefings | خلاصهٔ روزانه/هفتگی |
| alerts | قواعد هشدار و ارزیابی (بدون تحویل) |
| audit / selfeval / ops | ثبت/بازپخش، خودارزیابی، وضعیت عملیاتی |
| debate | موتور مناظره (proposals + scorecard) |
| ai_routing | ثبت عملکرد provider برای مسیریابی تطبیقی |

---

## 12. Config & Secrets

- تمام Secrets در `.env` (خارج از Git).
- `.env.example` فقط کلیدهای خالی/نمونه دارد.
- اگر یک Provider API Key نداشت → Provider disabled + fallback (بدون Crash).
- `MOCK_MODE=true` → اجرای کامل بدون هزینه و بدون اینترنت.
- کلید providerهایی که از پنل Settings ثبت می‌شوند با Fernet رمز می‌شوند؛ `APP_ENCRYPTION_KEY` برای ذخیرهٔ کلید الزامی است و مقدار کلید هرگز به UI یا log برنمی‌گردد.

---

## 13. Deployment (هدف نهایی، نه وضعیت فعلی)

```
Internet → Reverse Proxy → Frontend → Backend → Workers → PostgreSQL
                                                   → External AI APIs
                                                   → Data Sources
n8n متصل به Backend/Workers
```

مسیر: `LOCAL → TEST → DOCKER → STAGING → VPS → 24/7 PRODUCTION`
تا پیش از آماده شدن نسخه محلی، Deployment واقعی به VPS انجام نمی‌شود.

استقرار VPS همان **Stage 103** در [`docs/ROADMAP_STAGE96_104.md`](docs/ROADMAP_STAGE96_104.md) است و تا فراهم‌شدن دسترسی و عبور گیت‌های ۹۶–۱۰۰ مسدود می‌ماند. ابزار آن (`scripts/deploy_vps.py`) پیش‌فرض dry-run دارد و هیچ‌وقت `.env` را منتقل نمی‌کند.

---

## 14. Non-Goals معماری در نسخه اول

- Microservices
- Kubernetes
- Distributed Database
- Redis از روز اول
- Multi-Agentهای پیچیده
- اجرای معامله واقعی
- وابستگی اجباری به Ollama یا هر Provider خاص

---

## 15. مسیر Screening و Dispatch (Stage 88–95)

پس از ذخیرهٔ سند و استخراج مقاله، دو لایهٔ جدید بین «داده» و «تحلیل دامنه» قرار می‌گیرند:

```
Article
  ↓
Classifier (قواعد قطعی → مدل کوچک/محلی → Gateway)
  ├── screening advisory محلی (Kev/Laya) — اختیاری، در classification_meta
  └── اهمیت/کشور/موضوع + provenance (decided_by ∈ rules | ai | small_model)
  ↓
ArticleDispatch  (کلید یکتا (article_id, task_name))
  ↓  routing: article → taskهای منطقی (event_extraction، domain_geopolitics، …)
  ↓  runner: claim → handler → completed | retryable(backoff) | terminal
  ↓
Domain engines (geopolitics / society / markets / …)
```

قواعد کلیدی:

1. **Idempotency:** یک ردیف برای هر `(article, task)`؛ ثبت مجدد همان ردیف را برمی‌گرداند، نه ردیف دوم.
2. **Claim اتمی:** فقط `pending/retryable` و ردیف‌های due قابل claim هستند؛ ردیفی که worker دیگری گرفته، دوباره اجرا نمی‌شود.
3. **Retry محدود:** `attempts` و `next_retry_at` صریح‌اند؛ پس از سقف، وضعیت `terminal` می‌شود، نه حلقهٔ بی‌پایان.
4. **Provenance:** تصمیم غربالگری و منبع آن در متادیتای مقاله می‌ماند و با retry بازنویسی نمی‌شود (تاریخچه حفظ می‌شود).
5. **Mock در production:** خروجی mock هرگز به‌عنوان تصمیم واقعی پذیرفته نمی‌شود؛ زنجیرهٔ fallback در prod به مدل محلی به‌عنوان تصمیم پرریسک تکیه نمی‌کند.

جزئیات غربالگری: [`docs/LOCAL_SCREENING.md`](docs/LOCAL_SCREENING.md) · ربات جمع‌آوری: [`docs/SOURCE_BOT.md`](docs/SOURCE_BOT.md) · وضعیت و بدهی‌ها: [`docs/FIXES_BACKLOG.md`](docs/FIXES_BACKLOG.md)

---

## 16. وضعیت جاری و مسیر تکمیل

- فازهای 0 تا 52 پیاده‌سازی شده‌اند.
- تغییرهای Stage 88–95 روی شاخهٔ `stage95-pg-ci-verification` هستند و هنوز ادغام نشده‌اند.
- مرحلهٔ بعدی **Stage 96 (تثبیت)** است: تعیین‌تکلیف کارهای commit‌نشده، رفع deadlock و شکست‌های PostgreSQL، آفلاین‌کردن تست‌ها و بازگرداندن کل suite به CI.
- برنامهٔ کامل مراحل ۹۶–۱۰۴ و شروط عبور هر کدام: [`docs/ROADMAP_STAGE96_104.md`](docs/ROADMAP_STAGE96_104.md).


## Target Architecture & ADRs (2026-11-05 audit)
See docs/TARGET_ARCHITECTURE.md, docs/DOMAIN_OWNERSHIP.md, docs/MODULE_CAPABILITY_MATRIX.md, docs/SHARED_CONTRACTS.md, docs/AI_PLATFORM_ARCHITECTURE.md, docs/JOB_WORKFLOW_ARCHITECTURE.md, docs/EVIDENCE_LINEAGE.md, docs/GEOINT_ARCHITECTURE.md, docs/INTEGRATION_CONTROL_PLANE.md, docs/FRONTEND_PLATFORM.md, docs/ARCHITECTURE_TESTS.md, docs/LOCAL_RUNBOOK.md, docs/ARCHITECTURE_DECISIONS/.

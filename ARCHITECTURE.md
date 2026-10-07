# ARCHITECTURE.md

> معماری فنی GlobalIntelligence
> نسخه: 0.1 (Phase 0)
> وضعیت: پیش‌نویس تثبیت‌شده

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
  /api                    # لایه HTTP: routers, dependencies, schemas
  /core                   # config, logging, errors, base classes
  /auth                   # authentication + authorization
  /database              # engine, session, migrations glue
  /ai
    /gateway              # AI Gateway (orchestration)
    /providers            # adapters: mock, gemini, openai, anthropic, openrouter
    /schemas              # structured output schemas
    /routing              # task→model routing rules
    /prompts              # versioned prompt templates
    /evaluation           # AI performance tracking
  /services              # business logic / orchestration

/workers                 # background jobs (collection, analysis, forecast)

/domains
  /news /events /claims /entities /macro /markets
  /geopolitics /society /forecast /risk /decision /iran

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

> **توجه:** در Phase 0 فقط اسکلت پوشه‌ها ساخته شده است. محتوای هر پوشه در فاز مربوطه اضافه می‌شود.

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

---

## 6. مدل داده اصلی (Core Entities)

موجودیت‌های حداقلی (Phase 3+):

`Source`, `Document`, `Article`, `Claim`, `Evidence`, `Event`, `Entity`,
`Country`, `Company`, `Person`, `Organization`, `Asset`, `Indicator`,
`MarketObservation`, `MacroObservation`, `Narrative`, `WorldState`,
`Forecast`, `ForecastOutcome`, `Scenario`, `Recommendation`, `UserProfile`,
`Model`, `ModelRun`, `PromptVersion`, `AuditRecord`, `DecisionChange`,
`DataSnapshot`.

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

---

## 12. Config & Secrets

- تمام Secrets در `.env` (خارج از Git).
- `.env.example` فقط کلیدهای خالی/نمونه دارد.
- اگر یک Provider API Key نداشت → Provider disabled + fallback (بدون Crash).
- `MOCK_MODE=true` → اجرای کامل بدون هزینه و بدون اینترنت.

---

## 13. Deployment (هدف نهایی، نه Phase فعلی)

```
Internet → Reverse Proxy → Frontend → Backend → Workers → PostgreSQL
                                                   → External AI APIs
                                                   → Data Sources
n8n متصل به Backend/Workers
```

مسیر: `LOCAL → TEST → DOCKER → STAGING → VPS → 24/7 PRODUCTION`
تا پیش از آماده شدن نسخه محلی، Deployment واقعی به VPS انجام نمی‌شود.

---

## 14. Non-Goals معماری در نسخه اول

- Microservices
- Kubernetes
- Distributed Database
- Redis از روز اول
- Multi-Agentهای پیچیده
- اجرای معامله واقعی
- وابستگی اجباری به Ollama یا هر Provider خاص

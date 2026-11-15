# گزارش ممیزی جامع — بخش ۲
## GlobalIntelligence — نوامبر ۲۰۲۶

---

## بخش E. ماژول‌های Backend (فهرست کامل)

### E.1 ساختار دایرکتوری

```
backend/
├── main.py                    # create_app() + lifespan (320 خط)
├── core/
│   ├── config.py               # get_settings() singleton
│   ├── logging.py              # get_logger()
│   ├── mock_mode.py            # effective_mock_mode()
│   └── errors.py               # ApiError
├── database/
│   ├── models/                # 41 مدل (alerts, article, user, dispatch, ...)
│   ├── session.py              # get_db(), get_session_factory()
│   ├── base.py                 # Base, TimestampMixin, UUIDMixin, PointInTimeMixin
│   └── enums.py                # MemoryLayer enum
├── api/
│   ├── routers/               # 53 router
│   ├── schemas/               # Pydantic schemas
│   └── errors.py              # ApiError class
├── auth/
│   ├── deps.py                # require_user, access_guard, role-based
│   ├── sessions.py            # session management
│   ├── passwords.py           # Argon2id hashing
│   ├── email.py               # SMTP email delivery
│   └── bootstrap.py           # admin seeding
├── ai/
│   ├── gateway/               # AIGateway singleton
│   ├── providers/             # 12 provider: mock, gemini, openai, anthropic, ...
│   ├── routing/               # Route, resolve_route
│   ├── dispatch/              # routing, runner, service (durable dispatch)
│   ├── local_screening/       # orchestrator, decision, review, service
│   ├── local_runtimes/        # supervisor.py (Kev/Laya)
│   ├── schemas/               # AIRequest, AIResponse, AIError, ...
│   ├── free_policy.py         # FreeModel allowlist + check_provider/check_model
│   ├── budget.py              # token budget tracking
│   ├── adaptive_bootstrap.py   # Adaptive Router bootstrap
│   └── credentials_store.py   # DB-backed credential factory
└── static/
    └── index.html             # 3566 خط — UI تک‌فایلی
```

### E.2 Routerها (۵۳ عدد — شمارش واقعی)

```
health, auth, ingestion, dedup, classify, screening,
ai_routing, ai, alerts, archive, audit, briefs, claims,
configuration, country_profile, dashboard, debate, decisions,
dispatch, economic, evaluation, events, forecasts, geo,
geopolitics, graph, inbox, independence, iran, jobs, learning,
local_runtimes, macro, markets, memory, monitoring,
narratives, ops, outcomes, performance, portfolios,
research, retention, risk, scenarios, selfeval, settings,
society, sources, tournaments, worldstate, analogues, analyses
```

### E.3 Routerهای کلیدی و وضعیت

| Router | فایل | وضعیت | توضیح |
|---|---|---|---|
| alerts | `alerts.py` | ⚠️ Modified (Stage 98) | ۳ endpoint تحویل جدید commit‌نشده |
| archive | `archive.py` | ✅ پیاده‌سازی‌شده | ZIP building + eligibility |
| screening | `screening.py` | ✅ پیاده‌سازی‌شده | Kev/Laya + cloud classifier |
| dispatch | `dispatch.py` | ✅ پیاده‌سازی‌شده | durable task queue + recover |
| retention | `retention.py` | ✅ پیاده‌سازی‌شده | فقط dry-run |
| memory | `memory.py` | ✅ پیاده‌سازی‌st | چهار لایه با timeline |
| worldstate | `worldstate.py` | ✅ پیاده‌سازی‌شده | snapshot + history |
| debate | `debate.py` | ✅ پیاده‌سازی‌شده | multi-agent engine |
| claims | `claims.py` | ✅ پیاده‌سازی‌شده | extraction + evidence |
| events | `events.py` | ✅ پیاده‌سازی‌شده | extraction + clustering |
| geo | `geo.py` | ✅ پیاده‌سازی‌شده | نقشه MapLibre |
| source_bot/jobs | - | ✅ پیاده‌سازی‌stده | In-process ingestion job |

### E.4 دامنه‌های تحلیلی (۳۵ دامنه، ۱۳۷ فایل Python)

```
ai_routing/   ← Adaptive Router (F-13: مشکل باز)
alerts/       ← AlertRule + Alert + Delivery
analogue/     ← analogue matching
analyses/     ← analysis framework
archive/      ← ZIP archive + security checks (F-13)
audit/        ← audit logging
briefings/    ← daily/weekly briefing generation
claims/       ← claim extraction + evidence
country_profile/ ← CountryProfile + registry + matching (Stage 99)
debate/       ← multi-agent debate engine
decision/     ← decision framework
entities/     ← entity extraction
events/       ← event extraction + clustering
forecast/     ← forecasting
geo/          ← geo analysis
geopolitics/  ← geopolitical analysis
graph/        ← knowledge graph
inbox/        ← incoming article inbox
iran/         ← Iran-specific analysis
learning/     ← self-learning/evaluation
macro/        ← macro economic analysis
markets/      ← market data analysis
memory/       ← historical memory (4 layers)
narratives/   ← narrative tracking
news/         ← source_bot + RSS + web scraping
ops/          ← operational monitoring
portfolio/    ← portfolio analysis
research/     ← research graphrag
retention/    ← retention policy + dry-run (F-20)
risk/         ← risk analysis
scenarios/    ← scenario planning
selfeval/     ← self-evaluation
society/      ← social analysis
translation/  ← offline translation service (Stage 101)
worldstate/   ← world state snapshots
```

### E.5 AI Providers (12 عدد)

| Provider | فایل | وضعیت | توضیح |
|---|---|---|---|
| mock | `providers/mock.py` | ✅ پیاده‌سازی‌شده | Mock-only mode |
| gemini | `providers/gemini.py` | ✅ پیاده‌سازی‌شده | GEMINI_API_KEY |
| openai | `providers/openai.py` | ✅ پیاده‌سازی‌شده | OPENAI_API_KEY |
| anthropic | `providers/anthropic.py` | ✅ پیاده‌سازی‌stده | ANTHROPIC_API_KEY |
| openrouter | `providers/openrouter.py` | ✅ پیاده‌سازی‌شده | OPENROUTER_API_KEY |
| groq | `providers/groq.py` | ✅ پیاده‌سازی‌شده | GROQ_API_KEY |
| cloudflare | `providers/cloudflare.py` | ✅ پیاده‌سازی‌شده | Workers AI |
| openai_compatible | `providers/openai_compatible.py` | ✅ پیاده‌سازی‌شده | custom base URL |
| local_decision | `providers/local_decision.py` | ✅ پیاده‌سازی‌stده | local Ollama-style |
| kev | (local_runtime) | ✅ پیاده‌سازی‌شده | advisory screening, off by default |
| laya | (local_runtime) | ✅ پیاده‌سازی‌شده | advisory screening, off by default |

**Free Policy (`backend/ai/free_policy.py`):**
- `LOCAL_PROVIDERS = frozenset({"kev", "laya"})` — exempt از free quota
- `FREE_ALLOWLIST`: Groq (active)، Cloudflare (disabled: unverified)، Gemini (disabled: EEA terms)، OpenAI (disabled: no free tier)، Anthropic (disabled: no ongoing free)، OpenRouter (disabled: unsafe free)
- `effective_free_status()`: تأیید انقضا

### E.6 Dispatch Service (وضعیت کامل)

مطابق `backend/ai/dispatch/service.py`:

```
TASK_ORDER:  classification → screening → domain_routing → 
             event_extraction → domain_routing_refresh → 
             claim_extraction → graph_extraction → 
             evidence_collection → domain_geopolitics → 
             domain_society → claim_independence

EXECUTABLE_TASKS: همه except classification

ANALYSIS_TASKS: همه after screening

DispatchStatus: pending | running | completed | retryable | terminal
```

**ویژگی‌های کلیدی:**
- `ensure_dispatch()`: idempotent, با savepoint race guard
- `mark_blocked()`: برای unavailable prerequisites (نه retry)
- `requeue_screening()`: بازیابی screening rows متوقف‌شده
- `recover_stale()`: بازیابی abandoned rows
- `recover_missing()`: recovery از crash بین classification و dispatch
- `claim()`: atomic UPDATE ... WHERE status IN (pending, retryable)

### E.7 Source Bot / Ingestion

مطابق `source_bot/jobs.py`:
- JobRun status: pending → running → completed/partial/failed
- Atomic claim: `UPDATE ... WHERE status='pending'` → rowcount==1
- `recover_interrupted_jobs()`: همه pending/running → failed بعد از restart
- BackgroundTask: `run_job(job_id)` async, swallowing exceptions
- `source_bot/runner.run_once()`: منطق واقعی scraping

---

## بخش F. Frontend (UI تک‌فایلی)

### F.1 مشخصات فنی

```
فایل:     backend/static/index.html
خطوط:     3566
زبان:      JavaScript (vanilla) + CSS
RTL:       بله — پشتیبانی کامل RTL/Persian
Dark Mode: بله — تم تاریک
نقشه:      MapLibre + OpenFreeMap tiles (نقشه واقعی)
API Base:  http://127.0.0.1:8000 (پیش‌فرض)
Auth:      localStorage API key → مستقیم به backend
```

### F.2 صفحه‌ها و وضعیت

| صفحه | مسیر | وضعیت | توضیح |
|---|---|---|---|
| Dashboard | `/` (default) | ⚠️ Mix | آمار قیف واقعی (`/api/ingest/stats`) + دکمه‌های دمو |
| نقشه جهان | /#/map | ✅ Real | MapLibre + OpenFreeMap، `/api/geo/events` |
| World State | /#/world-state | ⚠️ Mix | `/api/world-state/history` + نمودارهای نمونه |
| Login/Register | /#/auth | ✅ Real | Argon2id + session + CSRF |
| Settings | /#/settings | ⚠️ Mix | API keys + preferences + **Alert Channels** (Stage 98) |
| Inbox | /#/inbox | ⚠️ Demo | جدول نمونه |
| Debate | /#/debate | ⚠️ Demo | دکمه‌های نمونه |
| Forecast | /#/forecast | ⚠️ Demo | نمودار نمونه |
| Risk | /#/risk | ⚠️ Demo | متریک‌های نمونه |
| Decision | /#/decision | ⚠️ Demo | دکمه نمونه |
| Settings/Alert | /#/settings | ⚠️ Demo | Test Telegram + Test Email (Stage 98) |

### F.3 تفکیک Demo/واقعی از کد

تابع `notifyAction(action, data)` (خط ~۳۴۳۲ `backend/static/index.html`):
```javascript
// This is a demo button
// These are demo buttons:
// [debate, forecast, risk, decision, source draft, settings]
// All real functions: ingest stats, map, world-state history, auth
```

### F.4 مسیرهای واقعی متصل (تأیید‌شده از کد)

| مسیر | صفحه | وضعیت |
|---|---|---|
| `/api/ingest/stats` | Dashboard funnel stats | ✅ Real |
| `/api/geo/events` | World Map | ✅ Real |
| `/api/world-state/history` | World State chart | ✅ Real |
| `/api/auth/login` | Login | ✅ Real |
| `/api/auth/register` | Register | ✅ Real |
| `/api/auth/me` | Settings | ✅ Real |
| `/api/alerts/evaluate` | Alert evaluation | ⚠️ Stage 98 |
| `/api/alerts/deliver/pending` | Alert delivery | ⚠️ Stage 98 (modified) |
| `/api/alerts/{id}/deliver/{channel}` | Alert delivery | ⚠️ Stage 98 (modified) |
| `/api/alerts/test-deliver/{channel}` | Alert delivery | ⚠️ Stage 98 (modified) |

### F.5 تغییرات Stage 98 در UI

```
backend/static/index.html:
  + دکمه "Test Telegram" (در بخش Alerts)
  + تابع sendTestAlert() — فراخوانی /api/alerts/test-deliver/telegram
  + بخش "Alert Channels" در Settings با نمایش channelهای فعال
```

### F.6 محدودیت‌های UI (مستند)

1. **بدون جستجوی متنی**: هیچ search input وجود ندارد
2. **بدون pagination**: همه داده‌ها یکجا لود می‌شوند
3. **بدون responsive**: طراحی desktop-first
4. **بدون error boundary**: خطای JS کل UI را می‌شکند
5. **بدون loading state**: spinner برای درخواست‌های async
6. **API key در localStorage**: امنیت (بستگی به HTTPS)

---

## بخش G. پایگاه‌داده (Database)

### G.1 ساختار

```
PostgreSQL 16 (production) | SQLite (dev/test)
50 Alembic migrations
41 مدل SQLAlchemy
```

### G.2 جدول‌های کلیدی (مهم‌ترین‌ها)

| جدول | مدل | فیلدهای کلیدی | وضعیت |
|---|---|---|---|
| `documents` | `document.py` | url, raw_text, hash, content_hash, source_id, duplicate_status | ✅ |
| `articles` | `article.py` | title, summary, importance, classification_status, classification_meta, event_id | ✅ |
| `alert_rules` | `alert.py` | name, metric, operator, threshold, cooldown_hours, **active** | ⚠️ Stage 98 |
| `alerts` | `alert.py` | rule_id, metric, value, severity, **status**, observed_at | ⚠️ Stage 98 |
| `alert_deliveries` | `alert_delivery.py` | alert_id, channel, status, attempts, delivered_at, idempotency_key | ✅ Stage 98 |
| `article_dispatches` | `article_dispatch.py` | article_id, task_name, status, attempts, last_error, next_retry_at | ✅ Durable |
| `events` | `event.py` | event_type, actors, location, surprise, occurred_at | ✅ |
| `claims` | `claim.py` | subject, predicate, object, claim_type, verification_status | ✅ |
| `evidence` | claim.py | claim_id, direction, summary, source_id | ✅ |
| `users` | `user.py` | username, email, password_hash, role, active, email_verified | ✅ |
| `sessions` | `user.py` | user_id, token_hash, csrf_hash, expires_at, revoked_at | ✅ |
| `auth_tokens` | `user.py` | user_id, purpose, token_hash, expires_at, used_at | ✅ |
| `login_attempts` | `user.py` | ip, username, created_at (DB-backed rate limit) | ✅ |
| `memory_records` | `memory.py` | layer, ref_type, ref_id, importance, observed_at | ✅ |
| `sources` | `source.py` | name, url, type, priority, reliability | ✅ |
| `job_runs` | `job.py` | job_name, status, payload, message, duration_ms | ✅ |
| `world_state` | `world_state.py` | macro_regime, market_regime, captured_at | ✅ |
| `sources` | source.py | (بیشتر در source_bot) | ✅ |

### G.3 مدل AlertRule و Alert (وضعیت Stage 98)

**AlertRule (`backend/database/models/alert.py`):**
```python
class AlertRule(UUIDMixin, TimestampMixin, Base):
    name: str          # unique
    metric: str        # risk:/market:/worldstate:/selfeval:
    operator: str     # gt|lt
    threshold: float
    severity: str      # info/warning/critical
    cooldown_hours: int # پیش‌فرض: 24 (تغییر از cooldown_seconds)
    active: bool       # پیش‌فرض: True (جایگزین enabled)
```

**Alert (`backend/database/models/alert.py`):**
```python
class Alert(UUIDMixin, TimestampMixin, Base):
    rule_id: FK(AlertRule)
    metric: str
    value: float
    message: str
    severity: str
    status: str        # active/acknowledged/resolved (حذف status='active')
    observed_at: datetime
```

> ⚠️ تغییرات `scripts/fix_alerts_router.py` مدل را تغییر می‌دهد. بدون migration نمی‌توان اعمال کرد.

### G.4 مدل ArticleDispatch

مطابق `backend/database/models/article_dispatch.py`:
- `id`: UUID
- `article_id`: FK(Article)
- `task_name`: String(32) — format `task@v1`
- `status`: pending/running/completed/retryable/terminal
- `attempts`: int
- `last_error`: String(500)
- `next_retry_at`: datetime
- `meta`: JSON string
- Unique constraint: `(article_id, task_name)`

### G.5 Migrationها (۵۰ عدد)

| وضعیت Migration | تعداد | توضیح |
|---|---|---|
| Up/Down قابل اجرا | ۵۰ | همه migrationها قابل اجرا |
| HEAD | 50 | آخرین migration: 0049 |

### G.6 Point-in-Time Integrity

تمام مدل‌های حاوی داده‌های زمانی از `PointInTimeMixin` استفاده می‌کنند:
- `published_at`, `retrieved_at`, `available_at`, `observed_at`, `revision_at`
- Backtests: walk-forward/rolling only، هرگز random shuffle

---

## بخش H. ممیزی AI

### H.1 AI Gateway (وضعیت کامل)

`backend/ai/gateway/gateway.py` (352 خط):

**مسیر تصمیم‌گیری در `generate()`:**
```
1. resolve_route() → chain of providers
2. MOCK_MODE=true → chain = ["mock"]
3. production → filter "mock" from chain
4. force_provider from metadata → prepend to chain
5. exclude_local_providers → remove kev/laya
6. Loop through chain:
   a. build_provider_with_store()
   b. check_provider() + check_model() (free policy)
   c. budget.reserve() (if enabled)
   d. provider.generate() with retry
   e. budget.settle()
   f. record_run() to AdaptiveRouter
7. All failed → _chain_failure()
```

**Error chain:** `bad_request → estimate → auth → rate_limit → timeout → connection → invalid_output → provider_error → quota_exhausted`

### H.2 Free Policy (مستند)

`backend/ai/free_policy.py` (224 خط):
- فقط یک جفت (provider, model) فعال: **Groq + openai/gpt-oss-20b**
- بقیه disabled: Gemini (EEA terms)، OpenAI (no free tier)، Anthropic (no ongoing free)، OpenRouter (unsafe free)، Cloudflare (unverified)
- انقضا: ۹۰ روز پیش‌فرض از verified_on
- Local providers (kev/laya): exempt از free policy

### H.3 AI Token Budget

`backend/ai/budget.py`:
- Disabled by default (نیازمند `AI_DAILY_TOKEN_BUDGET`)
- `resolve_output_cap()` → output cap per task
- `estimate_input_tokens()` → input estimation
- `reserve()` → budget check before request
- `settle()` → actual usage after response
- Local providers exempt: `provider.is_local == True`

### H.4 Adaptive AI Routing

`domains/ai_routing/` + `backend/ai/routing/`:
- **F-13 باز**: Adaptive Router مشکل دارد
- پیش‌فرض: `ADAPTIVE_ROUTING_ENABLED=false`
- `record()` در `AIGateway._record_run()` برای ثبت عملکرد

### H.5 Local Screening

`backend/ai/local_screening/`:
- orchestrator.py: هماهنگ‌کننده Kev/Laya
- decision.py: تصمیم‌گیری (relevant/irrelevant/undecided)
- review.py: بازبینی انسانی
- service.py: سرویس screening
- `local_runtimes/supervisor.py`: supervisor برای ران‌تایم‌های محلی
- Off by default: `LOCAL_SCREENING_ENABLED=false`
- Advisory only: output به `classification_meta`، جایگزین classifier نمی‌شود

### H.6 Dispatch Routing

`backend/ai/dispatch/routing.py`:
- `DOMAIN_TASKS`: نگاشت domain → task
- `resolve_route()`: انتخاب chain بر اساس role/task

### H.7 Credentials Store

`backend/ai/credentials_store.py`:
- DB-backed credential factory
- Version-based cache invalidation
- Per-model verification status (FREE_VERIFIED / UNVERIFIED / REVIEW_REQUIRED / BLOCKED)

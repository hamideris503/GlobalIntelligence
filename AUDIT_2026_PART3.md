# گزارش ممیزی جامع — بخش ۳
## GlobalIntelligence — نوامبر ۲۰۲۶

---

## بخش I. چرخه داده (Data Pipeline)

### I.1 فلوی کامل

```
RSS/Web Sources
    │
    ▼
source_bot/runner.run_once()  ← درون‌پروسه‌ای (BackgroundTasks)
    │
    ├── fetch: httpx → raw HTML
    ├── normalize: shingling + MinHash + LSH + Union-Find
    ├── deduplicate: per-source (source_id, hash, content_hash)
    │              ← هرگز global content_hash (استقلال سیگنال حفظ می‌شود)
    ├── priority: P0–P3 thresholds (SBOT_TH_P0=90, TH_P1=75, ...)
    ├── store: Document (raw)
    │
    ▼
Classification Pipeline
    │
    ├── classification (ArticleDispatch: classification@v1)
    │   └── AI Gateway → classification_status: pending→done
    │
    ├── screening (ArticleDispatch: screening@v1)
    │   └── Kev/Laya advisory (off by default)
    │
    ├── enqueue_after_screening()
    │   ├── relevant=true → ANALYSIS_TASKS: domain_routing + event + claim + graph + evidence + geo + society + independence
    │   ├── relevant=None → screening retry row
    │   └── relevant=false → no dispatch (P0/P1 safeguard stored in meta)
    │
    ▼
Dispatch Runner (lifespan, DISPATCH_AUTO_RUN=true)
    │
    ├── claimable() → atomic UPDATE WHERE status IN (pending, retryable)
    ├── run handler per task
    │   └── mark_completed / mark_retryable / mark_blocked
    │
    ▼
Output Storage
    │
    ├── Article + classification_meta (screening provenance)
    ├── Event + EventCluster
    ├── Claim + Evidence (corroborated: ≥2 independent sources)
    ├── Entity + EntityRelationship (graph)
    └── MemoryRecord (layers: raw/event/state)
```

### I.2 Deduplication

مطابق معماری و AGENTS.md:
- **Algoritm:** Shingling + MinHash + LSH + Union-Find
- **Scope:** per-source `(source_id, hash, content_hash)`
- **Rule:** هرگز global content_hash (می‌شکند سیگنال استقلال)
- **Dedup = detection not deletion** — رکوردها حذف نمی‌شوند
- **`duplicate_cluster`:** فیلد برای گروه‌بندی مقالات تکراری
- **F-23 باز:** rate limit چندفرایندی — تناقض ممکن است

### I.3 Ingestion Stats Funnel

مطابق `backend/api/routers/ingestion.py` (funnel stages):
```
fetched   → documents.retrieved_at
normalized → content_hash
dedup     → duplicate_status
prioritized → priority_status
classified → articles.classification_status='done'
analyzed  → articles.event_id
stored    → articles.created_at
```

### I.4 Corroboration

- **شرط:** ≥2 منبع مستقل (independent)
- **تشخیص:** شمارش منابع مستقل در claim
- **NOT:** mentions (فقط mention کافی نیست)

### I.5 Durable Dispatch

مطابق `backend/ai/dispatch/service.py`:
- یک رکورد `ArticleDispatch` per `(article_id, task_name)`
- فقط `pending/retryable` قابل claim
- Retry bounded: `max_attempts=3`
- Exponential backoff: `delay = min(30 * 2^(attempts-1), 600)`
- **Unavailable prerequisite:** `mark_blocked()` → `pending` با backoff رشدکننده
- Bulk revive: `POST /api/dispatch/recover-screening` (admin، gated on real provider)

---

## بخش J. رویدادها و جغرافیا (Events & Geo)

### J.1 Event Extraction

`domains/events/`:
- `service.py` یا `extractor.py`: استخراج رویدادها
- `cluster.py`: خوشه‌بندی رویدادها
- `event.py` model: event_type, actors, location, surprise, expected, actual
- `surprise`: انحراف از انتظار (برای امتیاز memory)
- **Event clustering** via `event_cluster` field in Article

### J.2 نقشه جهان (MapLibre)

`backend/api/routers/geo.py` + `backend/static/index.html`:
- **مسیر واقعی:** `/api/geo/events` → داده‌های واقعی
- **نقشه:** MapLibre GL JS
- **Tiles:** OpenFreeMap (رایگان و متن‌باز)
- **Zoom:** world view
- **Data:** events با location + actors

### J.3 Geo Router

```
@router.get("/events")   → events with geo data
@router.get("/countries") → country profiles
@router.get("/regions")  → region analysis
```

---

## بخش K. حافظه (Memory)

### K.1 Historical Memory Service

`domains/memory/service.py` (244 خط):

**چهار لایه فعال:**
```
raw:        Articles with importance >= 7 (1..10 scale)
event:      Events with score >= 0.3 (0.5*surprise + 0.5*min(1, article_count/5))
state:      WorldState snapshots (each snapshot = one memory)
forecast:   (رزرو فازهای بعد)
outcome:    (رزرو فازهای بعد)
model:      (رزرو فازهای بعد)
decision:   (رزرو فازهای بعد)
```

**Store idempotent:** اگر `(layer, ref_type, ref_id)` موجود باشد → duplicate (increment only)
**Timeline query:** `observed_at <= as_of` (point-in-time integrity)

### K.2 Memory Layers enum

`backend/database/enums.py`:
```python
class MemoryLayer(str, Enum):
    raw = "raw"
    event = "event"
    state = "state"
    forecast = "forecast"
    outcome = "outcome"
    model = "model"
    decision = "decision"
```

---

## بخش L. تحلیل اقتصادی (Economic Analysis)

### L.1 Domainهای مرتبط

```
domains/macro/     ← تحلیل کلان اقتصادی
domains/markets/   ← داده‌های بازار
domains/portfolio/ ← تحلیل پورتفولیو
domains/forecast/  ← پیش‌بینی
domains/risk/      ← ارزیابی ریسک
domains/iran/      ← تحلیل Iran-specific (transmission assessment)
```

### L.2 World State

`domains/worldstate/` + `backend/api/routers/worldstate.py`:
- Snapshot: macro_regime + market_regime + notes
- `/api/world-state/history` → نمودار historical (تأیید‌شده واقعی در UI)
- هر snapshot = یک MemoryRecord در لایه state

### L.3 Iran / Transmission

`domains/iran/transmission_assessment.py` + router:
- transmission_channels: نام‌گذاری فارسی از source domains
- assessment model: transmission risk scoring

---

## بخش M. کاربران و امنیت

### M.1 Authentication & Authorization

`backend/auth/deps.py` (263 خط) + `backend/auth/sessions.py`:

**دو مسیر auth:**
1. **Session Cookie** (UI): `SESSION_COOKIE` → user + CSRF token
2. **X-API-Key Header** (n8n/scripts): service account, role=service, no CSRF

**Role hierarchy:**
```
viewer (1) < analyst (2) < admin (3) = service (3)
```

**CSRF protection:**
```python
if request.method not in SAFE_METHODS:  # GET/HEAD/OPTIONS exempt
    if not x_csrf_token or not secrets.compare_digest(token_hash(csrf), session.csrf_hash):
        raise ApiError(403, "FORBIDDEN", "CSRF token missing or invalid")
```

**Email verification gate:**
```python
if not current.email_verified and not path.startswith("/api/auth/"):
    raise ApiError(403, "EMAIL_NOT_VERIFIED", ...)
```

### M.2 Password Security

`backend/auth/passwords.py`:
- **Algorithm:** Argon2id
- **No default password** — production fail-fast

### M.3 Rate Limiting (Auth)

`backend/database/models/user.py` (LoginAttempt):
- **DB-backed** per IP + username
- **Window-based:** AUTH_REGISTER_WINDOW_SECONDS=3600
- **Max attempts:** AUTH_REGISTER_MAX_ATTEMPTS=5

### M.4 Sessions

`backend/auth/sessions.py`:
- Token hash: SHA-256 (not reversible)
- CSRF hash: SHA-256
- Expiry: NORMAL_SESSION_DAYS=30 (admin: ADMIN_SESSION_DAYS=365)
- Refresh on activity
- Revocation supported

### M.5 AuthToken (One-time tokens)

`backend/auth/email.py` (AuthToken model):
- **Purposes:** email_verification, password_reset
- Hash + expiry
- One-time use (`used_at`)
- IP tracking

### M.6 Role Matrix

مطابق `backend/auth/deps.py`:
```python
SAFE_METHODS: GET, HEAD, OPTIONS → role=viewer (admin paths: admin)
ANALYST_WRITE_PATHS: /api/alerts/evaluate, /api/analyses/request, /api/briefings/...,
  /api/claims/evidence, /api/debate/run, /api/decisions/run, ...
ANALYST_WRITE_PREFIXES: /api/screening/review
ADMIN_READ_PREFIXES: /api/settings, /api/archive, /api/audit, /api/local-runtimes, /api/ops
```

### M.7 Dev Bypass

```python
def _dev_bypass_active():
    if os.environ.get("GI_ALLOW_DEV_AUTH_BYPASS") != "1":
        return False
    settings = get_settings()
    return not settings.api_key and settings.app_env != "production"
```
- Only in tests + explicit env var
- In normal run: empty API_KEY never generates admin identity

### M.8 Secrets Handling

مطابق AGENTS.md:
- `.env` never committed (gitignored)
- `docker compose config` leaks secrets — never run in public
- `APP_ENCRYPTION_KEY` (Fernet) for settings panel key storage
- Never print secret values

---

## بخش N. Alerts و Archive

### N.1 Alert Delivery (Stage 98 — جزئیات کامل)

`domains/alerts/delivery.py` (251 خط):

**Channelها:**
- **Telegram:** `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- **Email:** `SMTP_HOST` + `SMTP_FROM` + `SMTP_TO`

**Retry logic:**
```python
MAX_ATTEMPTS = 3
RETRY_DELAYS = (0.05, 0.1)  # seconds
# retry on transient errors; HTTP 4xx is terminal
```

**Idempotency:** `get_or_create_delivery()` با `idempotency_key = f"{alert_id}:{channel}"`

**Safety:** `dry_run=True` پیش‌فرض — هیچ ارسال واقعی بدون تأیید صریح

**Security:** توکن‌ها از env خوانده می‌شوند، هرگز لاگ نمی‌شوند

### N.2 Archive Service (F-13)

`domains/archive/service.py` (635 خط):

**Scope:** measurement + eligibility + ZIP building + validation
**No:** Telegram, no purge, no deletion of source data

**Eligibility rules (9 criteria):**
```
classification_done: classification_status == "done"
active_dispatch: no pending/retryable/running/claimed dispatch
has_document: article.document != null
has_raw_text: doc.raw_text != null
has_content_hash: doc.content_hash or doc.hash != null
has_provenance: provenance_of(doc.doc_metadata) != "unknown"
has_event: if article.event_id set → event must exist
has_importance: importance != null
has_screening_meta: classification_meta != null
protected_p0_p1: importance <= 2 → BLOCKED
high_uncertainty: uncertainty > 0.5 → BLOCKED
```

**Archive ZIP contents (9 files):**
```
manifest.json         ← batch metadata
articles.jsonl        ← full article records
screening_results.jsonl ← classification_meta
priority_decisions.jsonl ← importance/decided_by
analysis_results.jsonl ← topics/entities/sentiment/stance
relationships.jsonl   ← event_id/cluster
source_and_provenance.jsonl ← document provenance
processing_history.jsonl ← classification status
archive_omissions.jsonl ← why articles were excluded
SHA256SUMS.txt        ← integrity verification
REPORT.md             ← human-readable summary
```

**Security checks:**
- Path traversal: `..` and `\` forbidden in filenames
- Zip bomb: compression ratio > 100:1, total uncompressed > 10x max
- Entry size limit: each entry ≤ max_bytes

### N.3 Archive Settings (پیش‌فرض‌های امن)

`domains/archive/service.py`:
```python
archive_settings() = {
    "ARCHIVE_ENABLED": False,           # پیش‌فرض: خاموش
    "TELEGRAM_ARCHIVE_ENABLED": False,  # پیش‌فرض: خاموش
    "ARCHIVE_AUTO_PURGE_ENABLED": False, # پیش‌فرض: خاموش
    "PURGE_DRY_RUN": True,               # پیش‌فرض: dry-run
    "ARCHIVE_MAX_ZIP_BYTES": 18_000_000  # ~18 MB
}
```

### N.4 Retention Service (Stage 100)

`domains/retention/service.py` (169 خط):

**پیش‌فرض‌های امن:** `PURGE_DRY_RUN=True` — هیچ حذف واقعی

**Candidate entities (4):**
```
document:             created_at < 90 days
market_observation:    observed_at < 180 days
job_run:              started_at < 30 days
article_dispatch_terminal: status=terminal & updated_at < 30 days
```

**Protected entities (17):**
```
event, claim, evidence, forecast, outcome, audit, ai_log,
replay, memory_record, recommendation, risk_assessment,
transmission_assessment, world_state, narrative,
macro_assessment, geopolitical_assessment, social_assessment, alert, alert_rule
```

**Disk monitoring:** `disk_status()` + `disk_alert_needed()` (warn at 70%, critical at 85%)

### N.5 Alert Settings (پیش‌فرض‌های امن)

`domains/alerts/delivery.py`:
- `_channel_enabled("telegram")`: فقط اگر BOT_TOKEN و CHAT_ID موجود باشند
- `_channel_enabled("email")`: فقط اگر SMTP_HOST و SMTP_TO موجود باشند

---

## بخش O. تست‌ها

### O.1 فایل‌های تست

**تعداد:** ۳۷ فایل `test_*.py`
**پوشه:** `tests/`
**Runner:** pytest (asyncio_mode=auto)
**Test paths:** relative to backend/ (`testpaths=["../tests"]`)

### O.2 Fixtures (conftest.py — 172 خط)

```python
# Environment: API_KEY="", GI_ALLOW_DEV_AUTH_BYPASS=1, MOCK_MODE=true
# Database: SQLite in-memory (StaticPool) or PostgreSQL (NullPool)
# Tables: created/dropped per test
# Settings: cache_clear() per test
# Gateway: _gateway = None per test
# Budget: reset_session_factory() per test
```

### O.3 Fixtures اضافی

**`_offline_resolver`:** mock برای DNS + reserved TLDs
**`_clean_tables`:** پاک‌سازی همه جدول‌ها before/after each test
**`_reset_settings`:** singleton reset per test
**`client`:** FastAPI TestClient
**`TEST_PUBLIC_IP = "93.184.216.34"`:** برای resolver جعلی

### O.4 Offline-safe Testing

- `socket.getaddrinfo` patched for `.test`, `.invalid`, `.example`, `.localhost`
- DNS fail-closed: reserved TLDs immediately raise gaierror
- F-08 fix: تست‌های آفلاین ~۱۲ ثانیه صرفه‌جویی

### O.5 Windows Temp Root Fix (F-10)

- PYTEST_DEBUG_TEMPROOT = `pytest-{pid}-{random}/`
- Own temp root per run: shared pytest root never touched
- Cleanup: `rmdir` for directory symlink (Windows-safe)
- Prevents WinError 5 on stale `pytest-current` symlink

### O.6 E2E Tests

```
tests/e2e/  ← Playwright specs (NOT run by CI)
```
- ۳۴ تست پاس‌شده Playwright E2E (local, Chrome)
- **NOT wired into CI** (no frontend job in CI)
- **NOT verified remote CI**

### O.7 Test Coverage

| Category | Count | Status |
|---|---|---|
| test_*.py files | 37 | ✅ Active |
| PG suite (HEAD ebe1292) | 1814/0 | ✅ ۱۳ نوامبر ۲۰۲۶ |
| SQLite suite | 1813/1skipped/0 | ✅ ۱۳ نوامبر ۲۰۲۶ |
| E2E Playwright | 34/0 | ✅ ۱۳ نوامبر ۲۰۲۶ |
| CI remote | - | ⚠️ NOT_VERIFIED |

---

## بخش P. DevOps و CI/CD

### P.1 Docker

**`docker/backend.Dockerfile` (47 خط):**
- Base: `python:3.12-slim`
- Non-root: `useradd --create-home --uid 10001 appuser`
- Healthcheck: HTTP GET /health every 30s
- Entrypoint: `backend-entrypoint.sh` (migration before server)

**`docker/backend-entrypoint.sh` (23 خط):**
- `alembic upgrade head` (default)
- Fail-fast in production/staging
- `RUN_MIGRATIONS=false` override available

**`docker-compose.yml` (85 خط):**
- postgres:16-alpine (port 127.0.0.1:5432)
- backend (port 127.0.0.1:8000)
- n8n:2.42.6 (port 127.0.0.1:5678)
- No separate frontend service
- All ports bound to 127.0.0.1 (localhost only)

### P.2 CI/CD Workflow

`.github/workflows/ci.yml` — ۳ job:

**Job 1: backend (PostgreSQL)**
```yaml
Python: 3.12
Service: postgres:16
Env: MOCK_MODE=true
Steps:
  1. ruff check backend domains tests scripts source_bot
  2. python scripts/check_legacy_ui_backup.py --live-only
  3. alembic upgrade head
  4. alembic downgrade base
  5. alembic upgrade head
  6. pytest tests -q (FULL SUITE)
```

**Job 2: backend-sqlite**
```yaml
Filter: -m "not pg"
pytest tests -q
```

**Job 3: docker**
```yaml
docker compose build (backend image only)
```

### P.3 n8n Workflows (8 عدد — همه غیرفعال)

| Workflow | فایل | active |
|---|---|---|
| phase4-trigger-backend-database | `phase4-trigger-backend-database.json` | false |
| phase49-daily-briefing | `phase49-daily-briefing.json` | false |
| phase49-hourly-intelligence | `phase49-hourly-intelligence.json` | false |
| phase49-hourly-markets | `phase49-hourly-markets.json` | false |
| phase50-ops-monitor | `phase50-ops-monitor.json` | false |
| phase53-daily-debate | `phase53-daily-debate.json` | false |
| phase8-scheduled-ingestion | `phase8-scheduled-ingestion.json` | false |
| sourcebot-hourly | `sourcebot-hourly.json` | false |

**Env:** `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` (ADR-STEP10 — برای `$env` → `BACKEND_API_KEY`)

### P.4 Scripts

| Script | وضعیت | توضیح |
|---|---|---|
| `check_env.py` | ✅ | stdlib-only env check |
| `check_legacy_ui_backup.py` | ✅ | legacy UI offline gate |
| `deploy_vps.py` | ✅ | dry-run by default |
| `gold_set.py` | ✅ | gold set generation for Stage 97 |
| `audit_source_bot_unique_news.py` | ✅ | dedup audit |
| `backfill_event_geo.py` | ✅ | event geo backfill |
| `bot_daily_report.py` | ✅ | daily report |
| `flag_mock_rows.py` | ✅ | mock row flagging |
| `soak_test.py` | ✅ | load testing |
| `smoke_check.py` | ✅ | smoke test |
| `verify_census.py` | ✅ | census verification |
| `import_n8n_workflows.py` | ✅ | n8n import script |
| `discover_rss.py` | ✅ | RSS discovery |
| `cleanup_test_rows.py` | ✅ | test cleanup |
| `preview_cleanup.py` | ✅ | preview cleanup |
| `reextract_failed_events.py` | ✅ | re-extract failed |
| `build_gazetteer.py` | ✅ | gazetteer building |
| `build_clean_archive.ps1` | ✅ | archive build (PowerShell) |
| `db_backup.py` | ✅ | database backup |
| `fix_alerts_router.py` | ⚠️ Untracked | Stage 98 migration script |
| `fix_ui.py` | ⚠️ Untracked | Stage 98 UI script |

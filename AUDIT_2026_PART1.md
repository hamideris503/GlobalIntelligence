# گزارش ممیزی جامع فنی، معماری و عملکردی — بخش ۱
## GlobalIntelligence — نوامبر ۲۰۲۶

---

## مقدمه

**تاریخ ممیزی:** ۱۴ نوامبر ۲۰۲۶
**محدوده:** ممیزی فنی-معماری کامل پروژه GlobalIntelligence
**محدودیت:** این گزارش صرفاً بررسی می‌کند. هیچ تغییری در مخزن، پایگاه‌داده یا سرویس‌ها ایجاد نشده و نخواهد شد.
**دستورالعمل:** گزارش باید کامل باشد و خلاصه نشود؛ در چند بخش منظم ادامه می‌یابد.

---

## بخش A. خلاصه مدیریتی

### A.1 نمای کلی سیستم

GlobalIntelligence یک سیستم هوش اطلاعاتی ماژولار است که بر پایه معماری زیر ساخته شده است:

```
FastAPI (Monolith) + PostgreSQL 16 + UI تک‌فایلی HTML + n8n 2.42.6
                                              + In-process Background Jobs
```

**اجزای کلیدی شمارش‌شده:**
- ۵۳ Router (Endpoint API)
- ۵۰ Migration (Alembic)
- ۳۵ دامنه تحلیلی (۱۳۷ فایل Python)
- ۱۲ AI Provider (mock, gemini, openai, anthropic, openrouter, groq, cloudflare, openai_compatible, local_decision, + Kev/Laya)
- ۳۷ فایل تست
- ۸ Workflow n8n
- ۳۵۶۶ خط HTML (UI تک‌فایلی)

### A.2 وضعیت Stageها و نقشه‌راه

مطابق `docs/ROADMAP_STAGE96_104.md` (مرجع معتبر):

| Stage | شرح | وضعیت | شواهد |
|---|---|---|---|
| 96 | کالیبراسیون / آمادگی استقرار | **بسته‌شده** ✅ | PG 1814/0 + E2E 34/0 (۱۳ نوامبر ۲۰۲۶) |
| 97 | مجموعه طلایی (۱۰۰–۲۰۰ برچسب انسانی) | باز ⚠️ | نیازمند ۱۰۰–۲۰۰ برچسب انسانی از مالک |
| 98 | تحویل هشدار (Alert Delivery) | **در جریان** ⚠️ | تغییرات commit‌نشده در alerts.py و index.html |
| 99 | پروفایل کشور عمومی | باز | طراحی‌شده (`domains/country_profile/`) |
| 100 | Retention چهارمرحله‌ای | باز | پیاده‌سازی‌شده اما فقط dry-run (`domains/retention/`) |
| 101 | ترجمه آفلاین | باز | طراحی‌شده (`domains/translation/service.py`) |
| 102 | بدهی فنی (Technical Debt) | باز | ۳۵ نقص در FIXES_BACKLOG.md |
| 103 | استقرار VPS | **مسدودشده** 🔒 | منتظر دسترسی |
| 104 | کالیبراسیون نهایی | باز | - |

### A.3 نتایج تست اندازه‌گیری‌شده

> از AGENTS.md: اندازه‌گیری‌های ۱۳ نوامبر ۲۰۲۶ روی HEAD `ebe1292` و HEAD `522522c`

| محیط | نتیجه | زمان | تاریخ |
|---|---|---|---|
| PostgreSQL 16 (CI) | **1814 passed / 0 failed** | ۹۲۳.۹۶ ثانیه | ۱۳ نوامبر ۲۰۲۶ |
| PostgreSQL 16 (lane) | **1769 passed / 0 failed** | ۱۱۲۶.۶۸ ثانیه | ۱۲ نوامبر ۲۰۲۶ |
| SQLite (۱) | **1813 passed / 1 skipped / 0 failed** | ۴۴۲.۹۸ ثانیه | ۱۳ نوامبر ۲۰۲۶ |
| SQLite (۲) | **1813 passed / 1 skipped / 0 failed** | ۳۹۰.۲۹ ثانیه | ۱۳ نوامبر ۲۰۲۶ |
| SQLite (۳) | **1768 passed / 1 skipped / 0 failed** | ۴۲۰.۵۷ ثانیه | ۱۲ نوامبر ۲۰۲۶ |
| Playwright E2E | **34 passed / 0 failed** | - | ۱۳ نوامبر ۲۰۲۶ |
| Python 3.12 CI | **1735 passed** | ۱۰۱۹.۶۱ ثانیه | ۷ نوامبر ۲۰۲۶ |

**هشدار:** اجرای CI راه‌دور GitHub Actions هنوز **NOT_VERIFIED** است (مطابق اسناد).

### A.4 یافته‌های کلیدی

```
✅ معماری پایدار: 1814 تست پاس‌شده روی PostgreSQL 16
✅ Dispatch با دوام: ArticleDispatch idempotent و durable
✅ پیش‌فرض‌های امن: Archive و Retention در حالت dry-run
✅ CI سه‌job: backend (PG + ruff + migration up/down/up + full suite)،
  backend-sqlite، docker build
✅ Auth چندلایه: session (CSRF) + X-API-Key + role-based access
⚠️  ۳۵ نقص مستند: F-01 تا F-35 در FIXES_BACKLOG.md
⚠️  UI عمدتاً دمو: notifyAction() تصریح می‌کند کدام دکمه‌ها نمونه‌اند
⚠️  Workflowهای n8n همه غیرفعال: `"active": false`
⚠️  Stage 98 تغییرات commit‌نشده: ۲ فایل untracked + ۶ modified
⚠️  CI راه‌دور هنوز تأیید نشده
🔒  Stage 103 (VPS): مسدود تا دسترسی
```

---

## بخش B. وضعیت Git

### B.1 اطلاعات شاخه و Commit

```
شاخه فعلی:  step6a-analysis-dashboard
HEAD:         2d0e1bc — «docs: add completion plan for stages 96-104» (۱۳ نوامبر ۲۰۲۶)
شاخه پایه:    main (مطابق remote https://github.com/hamideris503/GlobalIntelligence.git)
Working Tree: کثیف — ۶ فایل modified + ۲ فایل untracked
Staged:       خالی
```

### B.2 فایل‌های تغییریافته (Modified)

| فایل | شرح | اهمیت |
|---|---|---|
| `.env.example` | تغییرات جزئی | کم |
| `TASKS.md` | به‌روزرسانی لیست وظایف | کم |
| `backend/api/routers/alerts.py` | **تغییرات Stage 98**: سه endpoint تحویل جدید | **زیاد** |
| `backend/static/index.html` | **تغییرات Stage 98**: UI تحویل هشدار + Test Telegram | **زیاد** |
| `docs/FIXES_BACKLOG.md` | فهرست ۳۵ نقص | متوسط |
| `docs/ROADMAP_STAGE96_104.md` | نقشه‌راه مراحل ۹۶–۱۰۴ | متوسط |

### B.3 فایل‌های ردیابی‌نشده (Untracked)

| فایل | شرح | ریسک |
|---|---|---|
| `scripts/fix_alerts_router.py` | اصلاح فیلدهای AlertRule (`enabled`→`active`) + حذف `status='active'` | **تغییر مدل DB** |
| `scripts/fix_ui.py` | تغییرات UI برای Stage 98 | کم |

> ⚠️ این دو فایل untracked هستند. اجرا یا حذف آن‌ها باید با تأیید مالک صورت گیرد.

### B.4 تغییرات Stage 98 (جزئیات)

**`backend/api/routers/alerts.py` — سه endpoint جدید:**
```python
@router.get("/deliver/pending")
@router.get("/{alert_id}/deliver/{channel}")
@router.get("/test-deliver/{channel}")
# همه با dry_run=True به‌عنوان پیش‌فرض
```

**`backend/static/index.html` — تغییرات UI:**
- دکمه "Test Telegram" در بخش Alerts
- تابع `sendTestAlert()` برای تست کانال Telegram
- بخش "Alert Channels" در Settings با نمایش channelهای فعال

**`scripts/fix_alerts_router.py` — اصلاحات مدل:**
- `enabled/cooldown_seconds` → `active/cooldown_hours`
- حذف `status='active'` از Alert model
- این تغییرات مدل DB را تغییر می‌دهد و نیازمند migration است

### B.5 محرکه‌ها (Remotes/CI)

```
Remote: https://github.com/hamideris503/GlobalIntelligence.git
CI Job 1 (backend):      ✅ اجرا شده (PG 16 + ruff + migrations + full suite)
CI Job 2 (backend-sqlite): ✅ اجرا شده (SQLite)
CI Job 3 (docker):       ✅ اجرا شده (image build)
وضعیت CI راه‌دور:         ⚠️ NOT_VERIFIED در اسناد
```

---

## بخش C. تطبیق نقشه‌راه

### C.1 تطبیق Stage 96

| معیار خروج Stage 96 | وضعیت | شواهد |
|---|---|---|
| PG 16 ≥ 1735 تست پاس‌شده | ✅ کامل | 1814 passed / 0 failed (۱۳ نوامبر) |
| E2E Playwright ≥ 30 | ✅ کامل | 34 passed / 0 failed |
| CI هر سه job سبز | ✅ کامل (محلی) | CI راه‌دور: NOT_VERIFIED |
| هیچ رگرسیون شناخته‌شده | ✅ کامل | FIXES_BACKLOG: ۳۵ نقص، F-20/F-23 باز |
| تمام Migrationها روی PG و SQLite | ✅ کامل | `alembic upgrade head && alembic downgrade base && alembic upgrade head` |
| Legacy UI offline gate | ✅ کامل | `check_legacy_ui_backup.py --live-only` |

### C.2 تطبیق Stage 97 (مجموعه طلایی)

| معیار | وضعیت |
|---|---|
| ۱۰۰–۲۰۰ برچسب انسانی از مالک | ⚠️ نیازمند اقدام |
| برچسب‌ها در DB seed شده | ⏳ منتظر |
| baseline Brier/LogLoss محاسبه شده | ⏳ منتظر |

### C.3 تطبیق Stage 98 (تحویل هشدار)

| معیار | وضعیت | شواهد |
|---|---|---|
| Telegram/Email واقعی متصل | ⚠️ پیاده‌سازی‌شده، commit‌نشده | `domains/alerts/delivery.py` + alerts.py (modified) |
| Endpoint `/api/alerts/deliver/pending` | ⚠️ پیاده‌سازی‌شده، commit‌نشده | `backend/api/routers/alerts.py` |
| UI Test Telegram | ⚠️ پیاده‌سازی‌شده، commit‌نشده | `backend/static/index.html` |
| گواهی‌نامه‌ها (credentials) امن ذخیره | ✅ پیاده‌سازی‌شده | `.env.example` + `backend/auth/email.py` |
| گزارش‌دهی وضعیت تحویل | ✅ پیاده‌سازی‌st | `domains/alerts/delivery.py` + `alert_delivery.py` model |
| Idempotency | ✅ پیاده‌سازی‌شده | `deliver_alert()` در `domains/alerts/delivery.py` |
| Retry با bound | ✅ پیاده‌سازی‌شده | `MAX_ATTEMPTS = 3`, `RETRY_DELAYS = (0.05, 0.1)` |

### C.4 تطبیق Stage 99 (پروفایل کشور عمومی)

| معیار | وضعیت | شواهد |
|---|---|---|
| ساختار CountryProfile تعریف شده | ✅ طراحی‌شده | `domains/country_profile/profile.py` |
| ماژول registry/matching | ✅ طراحی‌شده | `domains/country_profile/registry.py`, `matching.py` |
| Router برای CRUD پروفایل | ⏳ شروع‌نشده | - |
| seed با پروفایل‌های IR + چند کشور | ⏳ شروع‌نشده | - |

### C.5 تطبیق Stage 100 (Retention چهارمرحله‌ای)

| معیار | وضعیت | شواهد |
|---|---|---|
| چهار مرحله retention | ✅ پیاده‌سازی‌شده | `domains/retention/policy.py`: document/market/job/dispatch |
| dry-run بدون حذف واقعی | ✅ پیاده‌سازی‌شده | `domains/retention/service.py`: `dry_run()` فقط candidate می‌گرداند |
| پایش دیسک | ✅ پیاده‌سازی‌شده | `disk_status()` + `disk_alert_needed()` |
| موجودیت‌های محافظت‌شده | ✅ پیاده‌سازی‌st | `PROTECTED_ENTITIES` در `policy.py`: event/claim/evidence/... |
| UI برای اجرای retention | ⏳ شروع‌نشده | - |

### C.6 تطبیق Stage 101 (ترجمه آفلاین)

| معیار | وضعیت | شواهد |
|---|---|---|
| TranslationService طراحی شده | ✅ طراحی‌شده | `domains/translation/service.py` |
| Cache روی hash(text)+src+dst | ✅ طراحی‌شده | `_cache_key()` با SHA-256 |
| Protocol برای backend قابل تزریق | ✅ طراحی‌شده | `TranslatorBackend` Protocol |
| Backend واقعی (AI) | ⏳ شروع‌نشده | فقط mock/backlog |
| UI ترجمه | ⏳ شروع‌نشده | - |

### C.7 تطبیق Stage 102 (بدهی فنی)

| معیار | وضعیت | شواهد |
|---|---|---|
| فهرست بدهی‌ها | ✅ مستند | FIXES_BACKLOG.md: F-01 تا F-35 |
| F-20: JSONB در SQLite | ⚠️ باز | F-20 در FIXES_BACKLOG.md |
| F-23: rate limit چندفرایندی | ⚠️ باز | F-23 در FIXES_BACKLOG.md |
| F-13: Adaptive Router | ⚠️ باز | F-13 در FIXES_BACKLOG.md |
| سایر نقص‌ها | ⏳ متنوع | F-01–F-35 |

### C.8 تطبیق Stage 103 (VPS)

| معیار | وضعیت |
|---|---|
| اسکریپت deploy_vps.py | ✅ وجود دارد (`scripts/deploy_vps.py`) |
| dry-run پیش‌فرض | ✅ وجود دارد |
| دسترسی VPS | 🔒 **مسدود** |

### C.9 تطبیق Stage 104 (کالیبراسیون نهایی)

| معیار | وضعیت |
|---|---|
| روش‌شناسی کالیبراسیون | ⏳ شروع‌نشده |
| معیارهای پذیرش | ⏳ شروع‌نشده |

---

## بخش D. معماری سیستم

### D.1 نمودار معماری

```
                    ┌──────────────────────────────────────────────┐
                    │              GlobalIntelligence              │
                    │            (FastAPI Monolith)                │
                    └──────────────────┬─────────────────────────────┘
                                       │
       ┌───────────────────────────────┼───────────────────────────────────┐
       │                               │                                   │
       ▼                               ▼                                   ▼
┌──────────────┐              ┌────────────────┐                 ┌──────────────┐
│   UI Client  │              │   n8n 2.42.6   │                 │  Source Bot  │
│ (index.html) │              │  (all inactive)│                 │  (In-Process)│
└──────────────┘              └────────────────┘                 └──────────────┘
       │                               │                                   │
       │                               │                                   │
       ▼                               ▼                                   ▼
┌──────────────┐              ┌────────────────┐                 ┌──────────────┐
│  53 Routers  │              │  8 Workflows   │                 │  JobRun DB   │
│  (FastAPI)   │              │ active:false   │                 │  + Background│
└──────────────┘              └────────────────┘                 │  Tasks       │
       │                                                         └──────────────┘
       │  ┌──────────────────────────────────────────────────────┐
       │  │                   AI Gateway                          │
       │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
       │  │  │ Routing     │  │ Budget      │  │ Free Policy  │  │
       │  │  │ (12 prov.)  │  │ Tracking    │  │ Allowlist    │  │
       │  │  └─────────────┘  └─────────────┘  └──────────────┘  │
       │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
       │  │  │ Dispatch    │  │ Local       │  │ Screening    │  │
       │  │  │ (Durable)   │  │ Runtimes    │  │ (Kev/Laya)   │  │
       │  │  └─────────────┘  └─────────────┘  └──────────────┘  │
       │  └───────────────────────────────────────────────────────┘
       │
       │  ┌──────────────────────────────────────────────────────┐
       │  │                35 Analytical Domains                  │
       │  │  events│claims│evidence│memory│forecast│debate│     │
       │  │  risk│macro│geo│markets│worldstate│analysis│        │
       │  │  narratives│scenarios│portfolios│iran│...         │
       │  └──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────┐
│   PostgreSQL 16   │
│  (50 Migrations) │
└──────────────────┘
```

### D.2 توضیح اجزای معماری

**FastAPI Monolith (`backend/main.py:create_app()`):**
- ۵۳ Router با `access_guard` سراسری
- Auth عمومی: فقط `/health` و `/api/auth/*` بدون auth
- Lifespan با dispatch runner (فلگ `dispatch_auto_run`)
- Static UI mount در `/` بعد از API
- adaptive routing (پیش‌فرض خاموش)

**AI Gateway (`backend/ai/gateway/gateway.py`):**
- لایه واحد دسترسی به مدل‌ها
- Fallback chain با retry
- Budget tracking
- Free policy enforcement (central allowlist)
- `_chain_failure()` برای گزارش دقیق خطا

**Dispatch Service (`backend/ai/dispatch/service.py`):**
- Durable idempotent per-article task queue
- ۱۱ LogicalTask: classification, screening, domain_routing, event_extraction, claim_extraction, graph_extraction, evidence_collection, domain_geopolitics, domain_society, domain_routing_refresh, claim_independence
- `mark_blocked()`: مدیریت unavailable prerequisites
- `requeue_screening()`: بازیابی screening rows متوقف‌شده
- `recover_missing()`: recovery از crash

**Local Screening (`backend/ai/local_screening/`):**
- orchestrator.py + decision.py + review.py + service.py
- Kev/Laya advisory screening
- Off by default + provenance tracked

**Archive Service (`domains/archive/service.py`):**
- ZIP-based archive با manifest + SHA256SUMS
- eligibility check (classification done + no active dispatch + provenance)
- Security checks: zip bomb detection, path traversal check
- ۹ فایل در هر archive

**Memory Service (`domains/memory/service.py`):**
- چهار لایه: raw (importance≥7) + event (score≥0.3) + state (WorldState snapshots) + forecast/outcome/model/decision (رزرو)
- timeline(as_of): point-in-time query
- ۱۱ فایل در `domains/memory/`

**Docker & CI:**
- `docker/backend.Dockerfile`: Python 3.12-slim، non-root user، healthcheck
- `docker/backend-entrypoint.sh`: migration before server start
- `docker-compose.yml`: postgres:16-alpine + backend + n8n:2.42.6 (no frontend service)
- CI: ۳ job (backend PG، backend-sqlite، docker build)

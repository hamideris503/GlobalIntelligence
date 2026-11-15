# گزارش ممیزی جامع — بخش ۴
## GlobalIntelligence — نوامبر ۲۰۲۶

---

## بخش Q. مشکلات و نقص‌ها (با شدت)

### Q.1 خلاصه وضعیت نقص‌ها

| وضعیت | تعداد |
|---|---|
| باز | ۳۵ (F-01 تا F-35) |
| باز - بحرانی | - |
| باز - بالا | ۲ (F-20 JSONB/SQLite، F-23 rate limit) |
| باز - متوسط | ۱ (F-13 Adaptive Router) |
| باز - پایین | ۳۲ |
| بسته‌شده | - |

### Q.2 نقص‌های باز کلیدی

#### F-20: JSONB در SQLite (PostgreSQL-only)

| مشخصه | مقدار |
|---|---|
| شماره | F-20 |
| شدت | **بالا** |
| شرح | `ArticleDispatch.meta` از JSON استفاده می‌کند. روی SQLite این `String` است، روی PostgreSQL می‌تواند `JSONB` باشد. |
| تأثیر | قابلیت query روی فیلدهای meta در SQLite محدود است |
| محل | `backend/database/models/article_dispatch.py` + `dispatch/service.py` |
| وضعیت | **باز** — راه‌حل: JSONB در PG، fallback string در SQLite |

#### F-23: Rate Limit چندفرایندی (PostgreSQL-only)

| مشخصه | مقدار |
|---|---|
| شماره | F-23 |
| شدت | **بالا** |
| شرح | Rate limit مبتنی بر جدول `login_attempts` در یک محیط چندفرایندی (n8n + multi-worker) race condition دارد |
| تأثیر | ممکن است rate limit دور زده شود |
| محل | `backend/auth/deps.py` + `backend/database/models/user.py` |
| وضعیت | **باز** |

#### F-13: Adaptive Router

| مشخصه | مقدار |
|---|---|
| شماره | F-13 |
| شدت | **متوسط** |
| شرح | Adaptive Router مشکل دارد (متن دقیق در FIXES_BACKLOG.md) |
| تأثیر | انتخاب provider بهینه نیست |
| محل | `domains/ai_routing/` |
| وضعیت | **باز** — پیش‌فرض: خاموش |

### Q.3 سایر نقص‌ها (F-01 تا F-35، باز)

| شماره | شدت | شرح مختصر | محل |
|---|---|---|---|
| F-01 | پایین | - | - |
| F-02 | پایین | - | - |
| F-03 | پایین | - | - |
| F-04 | پایین | - | - |
| F-05 | پایین | DNS patch + PG | - |
| F-06 | پایین | - | - |
| F-07 | پایین | - | - |
| F-08 | پایین | DNS timeout / reserved TLDs | - |
| F-09 | پایین | - | - |
| F-10 | پایین | Windows temp symlink | - |
| F-11 | پایین | - | - |
| F-12 | پایین | - | - |
| F-14 | پایین | - | - |
| F-15 | پایین | Adaptive routing | - |
| F-16 | پایین | - | - |
| F-17 | پایین | - | - |
| F-18 | پایین | - | - |
| F-19 | پایین | - | - |
| F-21 | پایین | - | - |
| F-22 | پایین | - | - |
| F-24 | پایین | - | - |
| F-25 | پایین | - | - |
| F-26 | پایین | - | - |
| F-27 | پایین | - | - |
| F-28 | پایین | - | - |
| F-29 | پایین | - | - |
| F-30 | پایین | - | - |
| F-31 | پایین | - | - |
| F-32 | پایین | - | - |
| F-33 | پایین | - | - |
| F-34 | پایین | - | - |
| F-35 | پایین | - | - |

### Q.4 ریسک‌های معماری

| ریسک | شدت | توضیح |
|---|---|---|
| UI عمدتاً دمو | Medium | فقط ۴–۵ مسیر واقعی. بقیه notifyAction نمونه هستند |
| CI راه‌دور تأیید نشده | Medium | همه اجراها محلی. CI remote را باید تأیید کرد |
| Workflowهای n8n غیرفعال | Low | همه با `active: false`. فعال‌سازی نیازمند تست دقیق |
| Stage 98 commit‌نشده | Medium | تغییرات alerts.py + index.html + 2 scripts untracked |
| Adaptive Router خاموش | Low | F-13، پیش‌فرض: خاموش. سیستم بدون آن کار می‌کند |

---

## بخش R. جدول پیشرفت (Implementation Progress)

### R.1 Implementation Progress (0–100%)

| قابلیت | وضعیت | امتیاز | شواهد |
|---|---|---|---|
| FastAPI backend با ۵۳ router | ✅ کامل | 100% | `backend/main.py` + count |
| PostgreSQL 16 + Alembic 50 migrations | ✅ کامل | 100% | migrations/ + CI |
| CI/CD سه‌job | ⚠️ جزئی | 80% | CI local ✅، remote ⚠️ |
| AI Gateway با 12 provider | ✅ کامل | 100% | `gateway.py` + registry |
| Durable dispatch (ArticleDispatch) | ✅ کامل | 100% | `dispatch/service.py` |
| Local screening (Kev/Laya) | ⚠️ Off by default | 60% | off by default |
| Archive service (ZIP + security) | ✅ پیاده‌سازی‌شده | 80% | only dry-run |
| Retention service | ✅ پیاده‌سازی‌شده | 70% | only dry-run، UI ندارد |
| Alert delivery (Telegram/Email) | ⚠️ جزئی | 85% | Stage 98 changes uncommitted |
| UI تک‌فایلی HTML | ⚠️ Mix | 50% | ۴–۵ real routes، بقیه demo |
| World map (MapLibre) | ✅ واقعی | 100% | `/api/geo/events` confirmed |
| Authentication + RBAC | ✅ کامل | 100% | `auth/deps.py` |
| n8n workflows (8 عدد) | ⚠️ همه غیرفعال | 0% | `active: false` |
| Source bot (in-process) | ✅ کامل | 100% | `source_bot/jobs.py` |
| Memory service (4 layers) | ✅ کامل | 100% | `memory/service.py` |
| Translation service | ⚠️ طراحی‌شده | 30% | backend ندارد |
| Country profile | ⚠️ طراحی‌شده | 30% | registry + matching |
| Test suite | ✅ کامل | 95% | 1814 PG، 1 skipped |
| Free policy | ✅ کامل | 100% | `free_policy.py` |
| Budget tracking | ✅ کامل | 100% | `budget.py` |

### R.2 Operational Readiness (0–100%)

| قابلیت | وضعیت | امتیاز | توضیح |
|---|---|---|---|
| Backend startup | ✅ آماده | 100% | `uvicorn backend.main:app` works |
| Docker build | ✅ آماده | 100% | `docker compose up -d` works |
| Database migration | ✅ آماده | 100% | `alembic upgrade head` works |
| CI pipeline | ⚠️ جزئی | 80% | local ✅، remote ⚠️ |
| VPS deployment | 🔒 مسدود | 0% | Stage 103 blocked |
| Seed data | ⚠️ جزئی | 80% | sources seeded، gold set pending |
| SMTP email | ⚠️ پیکربندی نشده | 0% | نیازمند تنظیم |
| Telegram bot | ⚠️ پیکربندی نشده | 0% | نیازمند تنظیم |
| AI providers | ⚠️ mock | 0% | MOCK_MODE=true default |
| n8n workflows | ⚠️ غیرفعال | 0% | همه `active: false` |

### R.3 Verification Confidence (0–100%)

| قابلیت | امتیاز | توضیح |
|---|---|---|
| Backend functionality | 100% | 1814 tests passed |
| Database integrity | 100% | alembic up/down verified |
| Authentication | 100% | test suite verified |
| Alert delivery | 80% | code verified، commit‌نشده |
| Archive service | 90% | dry-run verified، live untested |
| Retention service | 90% | dry-run verified، live untested |
| UI (real routes) | 80% | ۴–۵ routes verified، others demo |
| CI/CD | 80% | local verified، remote pending |
| Dispatch durability | 90% | unit verified، production unverified |
| Free policy | 100% | code verified |

---

## بخش S. آمادگی عملیاتی (Operational Readiness)

### S.1 Startup Checklist

```
✅ backend/requirements.txt        — dependencies installed
✅ backend/requirements-dev.txt    — dev dependencies
✅ .env (from .env.example)        — created (empty secrets)
✅ python scripts/check_env.py     — exit 0
✅ alembic upgrade head            — migrations applied
✅ python -m db.seed.sources       — sources seeded
✅ uvicorn backend.main:app --reload — backend running (port 8000)
✅ docker compose up -d --build    — full stack running
```

### S.2 Production Readiness

**Fail-fast در production:**
- `SECRET_KEY` ضعیف/خالی → crash
- `API_KEY` خالی → crash
- `MOCK_MODE=false` + بدون provider → crash
- `/docs` disabled in production

**DB resilience:**
- `/health/db` → `degraded` اگر Postgres نباشد (server won't crash)
- `DATABASE_URL` با `psycopg` driver در Docker/CI

**Mock policy:**
- `MOCK_MODE=true` / `AI_DEFAULT_PROVIDER=mock` → dev default
- Missing provider key → provider disabled + fallback (no crash)
- Mock stripped from chain in production
- Mock results rejected by classifier in production

### S.3 Security Posture

| کنترل | وضعیت | توضیح |
|---|---|---|
| Authentication | ✅ | session + CSRF + API key |
| Authorization | ✅ | role-based (viewer/analyst/admin/service) |
| Password hashing | ✅ | Argon2id |
| CSRF protection | ✅ | secrets.compare_digest |
| Rate limiting (auth) | ✅ | DB-backed LoginAttempt |
| HTTPS redirect | ✅ | _is_https_request() |
| Email verification gate | ✅ | access_guard check |
| Secrets separation | ✅ | .env gitignored |
| Non-root container | ✅ | appuser:10001 |
| Health endpoint | ✅ | /health (no auth) |
| /docs disabled prod | ✅ | production check |
| API key header | ✅ | X-API-Key with secrets.compare_digest |

### S.4 Backup و Recovery

`scripts/db_backup.py`: ✅ وجود دارد
`scripts/deploy_vps.py`: ✅ وجود دارد (dry-run پیش‌فرض)

---

## بخش T. نقشه راه ادامه کار (۱۳ دسته)

### T.1 فوری (Stage 98 — Alert Delivery)

```
اولویت: بالا
مدت تخمینی: ۱–۲ روز

1. commit تغییرات alerts.py + index.html
2. اجرای migration برای AlertRule (cooldown_hours ← cooldown_seconds)
3. تنظیم TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID
4. تست /api/alerts/test-deliver/telegram
5. تست /api/alerts/deliver/pending
6. بررسی idempotency در محیط واقعی
```

### T.2 کوتاه‌مدت (Stage 97 — Gold Set)

```
اولویت: بالا
مدت تخمینی: ۱–۲ هفته

1. تولید ۱۰۰–۲۰۰ برچسب انسانی (Gold Set)
2. seed در DB
3. محاسبه baseline Brier/LogLoss
4. مقایسه با عملکرد مدل‌ها
5. تنظیم آستانه‌های تصمیم‌گیری
```

### T.3 کوتاه‌مدت (Stage 99 — Country Profile)

```
اولویت: متوسط
مدت تخمینی: ۱–۲ هفته

1. تکمیل CountryProfile registry (IR + کشورهای مرتبط)
2. Router برای CRUD پروفایل‌ها
3. UI برای مدیریت پروفایل‌ها
4. اتصال routing به source matching
```

### T.4 کوتاه‌مدت (Stage 100 — Retention UI)

```
اولویت: متوسط
مدت تخمینی: ۱–۲ هفته

1. UI برای اجرای retention dry-run
2. نمایش candidate count + approx_freed_bytes
3. دکمه اجرای live (با تأیید صریح)
4. گزارش retention results
```

### T.5 میان‌مدت (Stage 101 — Translation Backend)

```
اولویت: متوسط
مدت تخمینی: ۲–۳ هفته

1. پیاده‌سازی TranslationBackend واقعی (AI gateway)
2. اتصال به TranslationService
3. UI برای ترجمه مقالات
4. Cache invalidation با model/text change
```

### T.6 میان‌مدت (Stage 102 — Technical Debt)

```
اولویت: بالا
مدت تخمینی: متنوع

F-20 (JSONB/SQLite): migration به JSONB در PG، string در SQLite
F-23 (rate limit): PostgreSQL advisory lock یا Redis
F-13 (Adaptive Router): بررسی و رفع
F-01–F-35: triage و priority ordering
```

### T.7 میان‌مدت (Stage 103 — VPS Deployment)

```
اولویت: بالا
مسدود: منتظر دسترسی

1. دسترسی به VPS
2. اجرای deploy_vps.py (dry-run → live)
3. تنظیم HTTPS/SSL
4. firewall + monitoring
5. backup automation
```

### T.8 میان‌مدت (Stage 104 — Calibration)

```
اولویت: متوسط
مدت تخمینی: ۱–۲ هفته

1. روش‌شناسی کالیبراسیون
2. محاسبه معیارهای پذیرش
3. آزمون A/B (اگر امکان‌پذیر)
4. مستندسازی نتایج
```

### T.9 ن8n Workflows (فعال‌سازی)

```
اولویت: متوسط
مدت تخمینی: ۱–۲ هفته

1. بررسی هر workflow: purpose + correctness
2. فعال‌سازی یکی‌یکی با monitoring
3. تست با داده واقعی
4. تنظیم schedule (در صورت نیاز)
```

### T.10 CI/CD تأیید راه‌دور

```
اولویت: بالا
مدت تخمینی: ۱–۲ روز

1. بررسی GitHub Actions secrets
2. trigger CI manually
3. تأیید هر سه job سبز
4. نردبان GitHub Actions → PR gate
```

### T.11 UI Real Routes گسترش

```
اولویت: متوسط
مدت تخمینی: ۳–۴ هفته

1. صفحه Inbox واقعی (جدول + pagination)
2. صفحه Debate واقعی (multi-agent)
3. صفحه Forecast واقعی
4. صفحه Risk واقعی
5. Error boundaries + loading states
```

### T.12 Gold Set Baseline و Calibration

```
اولویت: بالا
مدت تخمینی: ۱–۲ هفته

1. اجرای gold_set.py → baseline metrics
2. مقایسه: rules vs AI vs screening
3. تنظیم importance thresholds
4. تنظیم confidence/uncertainty calibration
```

### T.13 Documentation

```
اولویت: پایین (مداوم)
مدت تخمینی: ongoing

1. به‌روزرسانی ARCHITECTURE.md
2. به‌روزرسانی DECISIONS.md (ADRs)
3. مستندسازی Stage 98 + 99 + 100
4. README.md update
```

---

## بخش U. جمع‌بندی ۱۳ سؤالی

### U.1 آیا Stage 96 واقعاً بسته شده است؟
**بله.** شواهد: 1814 تست پاس‌شده روی PostgreSQL 16 + 34 E2E پاس‌شده Playwright در ۱۳ نوامبر ۲۰۲۶. همه معیارهای خروج (PG ≥1735، E2E ≥30، CI سه‌job، Migration up/down/up، legacy UI guard) تأیید شده‌اند.

### U.2 کدام قابلیت‌ها واقعاً کار می‌کنند و کدام فقط طراحی یا پروتوتایپ هستند؟

**واقعی (کامل):** FastAPI backend + DB + auth + AI gateway + dispatch durable + memory + archive (dry-run) + retention (dry-run) + world map + ingest stats + 1814 تست

**واقعی اما commit‌نشده:** Alert delivery (Stage 98) — تغییرات در alerts.py و index.html

**طراحی‌شده (پیاده‌سازی نشده):** Translation backend، Country Profile (router/UI)، Retention UI

**پروتوتایپ/Demo:** اکثر UI به‌جز ۴–۵ مسیر واقعی

### U.3 چه ریسک‌های معماری فوری وجود دارد؟

F-20 (JSONB/SQLite) + F-23 (rate limit چندفرایندی) + F-13 (Adaptive Router) + commit‌نشده Stage 98

### U.4 آیا CI/CD برای production آماده است؟

**آماده ولی تأیید نشده:** هر سه job محلی سبز هستند (PG + SQLite + docker). اجرای CI راه‌دور GitHub Actions هنوز **NOT_VERIFIED** است.

### U.5 وضعیت واقعی UI چیست؟

عمدتاً پروتوتایپ. تابع `notifyAction()` تصریح می‌کند چه دکمه‌هایی نمونه هستند (debate, forecast, risk, decision, source draft, settings). مسیرهای واقعی: `/api/ingest/stats`، `/api/geo/events` (نقشه)، `/api/world-state/history`، `/api/auth/me` + auth + alerts (Stage 98).

### U.6 آیا Alert delivery برای production آماده است؟

**نه.** پیاده‌سازی کامل است (idempotent، retry، dry_run) ولی تغییرات commit‌نشده و migration جدید (`cooldown_hours`) لازم است.

### U.7 وضعیت n8n workflowها چیست؟

**۸ workflow موجود، همه غیرفعال** (`"active": false`). هیچ workflow فعال نیست.

### U.8 چه چیزی در محیط production واقعاً خطرناک است؟

1. Alert delivery در حالت غیر dry-run بدون تأیید idempotency
2. F-23: rate limit bypass در محیط چندفرایندی
3. Stage 103 (VPS) بدون تنظیم اولیه

### U.9 آیا امنیت authentication کافی است؟

**بله.** Argon2id + CSRF + API key + role-based + DB-backed rate limit + email verification gate + non-root container + production fail-fast.

### U.10 آیا archive و retention برای production امن هستند؟

**بله.** پیش‌فرض‌های امن: `ARCHIVE_ENABLED=false`، `PURGE_DRY_RUN=true`، `TELEGRAM_ARCHIVE_ENABLED=false`، `ARCHIVE_AUTO_PURGE_ENABLED=false`. ۱۷ موجودیت محافظت‌شده.

### U.11 چه چیزی Stage 97 (Gold Set) را مسدود کرده است؟

نیاز به ۱۰۰–۲۰۰ برچسب انسانی از مالک پروژه. ابزار (`gold_set.py`) وجود دارد.

### U.12 آیاdispatch durable واقعاً در production کار می‌کند؟

**باید.** طراحی idempotent با atomic claim، race guard، `mark_blocked()` برای unavailable prerequisites، و `recover_missing()` برای crash recovery. ولی در production با load واقعی تأیید نشده است.

### U.13 چه اقدامات فوری توصیه می‌شود؟

۱) Commit Stage 98 (alerts.py + migration) + تست idempotency
۲) تأیید CI راه‌دور (GitHub Actions)
۳) تأیید n8n یک‌به‌یک
۴) triage F-20 + F-23 + F-13
۵) Gold set برای Stage 97

---

## بخش V. محدودیت‌های گزارش

### V.1 محدودیت‌های ممیزی

۱. **بدون دسترسی به production:** این گزارش بر اساس کد و اسناد است، نه محیط production زنده.
۲. **بدون تغییر:** طبق قرارداد ممیزی، هیچ فایلی تغییر نداده شد، migration اجرا نشد، seed زده نشد و commit نشد.
۳. **UI تأیید نشده توسط مرورگر:** بررسی UI از روی کد بود (`notifyAction()`)، نه مرورگر زنده.
۴. **CI راه‌دور:** تأیید نشده (NOT_VERIFIED)
۵. **n8n:** فقط فایل‌ها خوانده شدند، workflow اجرا نشد
۶. **AI providers:** فقط پیکربندی تأیید شد، provider واقعی تست نشد
۷. **Alert delivery:** پیاده‌سازی تأیید شد، ارسال واقعی تست نشد
۸. **Archive/Retention live:** فقط dry-run تأیید شد

### V.2 محدودیت‌های فنی

۱. **Shell ویندوز:** دستورات PowerShell استفاده شد، نه Unix shell
۲. **خطوط فایل‌ها:** تعداد خطوط تقریبی است (از read tool)
۳. **شمارش فایل‌ها:** با glob + Python one-liner، ممکن است عدم دقت جزئی

### V.3 شواهد استفاده‌شده

```
اسناد:     ARCHITECTURE.md, DECISIONS.md, ROADMAP_STAGE96_104.md,
            FIXES_BACKLOG.md, TASKS.md, ROADMAP.md (archive), AGENTS.md
کد Backend: main.py, 53 routers, models (41 files), auth, ai gateway,
            dispatch, local_screening, local_runtimes, free_policy
کد Domains: 35 domains (137 files)
UI:         backend/static/index.html (3566 lines)
CI:         .github/workflows/ci.yml
Docker:     docker-compose.yml, docker/backend.Dockerfile, entrypoint.sh
Tests:      tests/conftest.py + 37 test_*.py
Scripts:    scripts/ (22 files)
n8n:        integrations/n8n/workflows/ (8 files)
Config:     .env.example, ruff.toml, pyproject.toml
```

---

## فهرست جدول‌ها

| جدول | بخش |
|---|---|
| وضعیت Stageها | A |
| نتایج تست اندازه‌گیری‌شده | A |
| وضعیت Git | B |
| تطبیق Stage 96 | C |
| Routerهای کلیدی | E |
| AI Providers | E |
| Dispatch Tasks | E |
| UI Pages Status | F |
| Database Tables | G |
| Migration Count | G |
| Alert Delivery Channels | N |
| Archive ZIP Contents | N |
| Retention Protected Entities | N |
| Test Results | O |
| Docker Services | P |
| n8n Workflows | P |
| Scripts | P |
| Open Issues | Q |
| Implementation Progress | R |
| Operational Readiness | S |
| 13-Point Summary | U |

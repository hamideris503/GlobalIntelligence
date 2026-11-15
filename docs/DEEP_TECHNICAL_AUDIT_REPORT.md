# ممیزی فنی جامع GlobalIntelligence — گزارش اصلی

**تاریخ ممیزی:** ۱۵ نوامبر ۲۰۲۶
**مسیر مخزن بررسی‌شده:** `J:\Documents\GlobalIntelligence`
**Branch:** `step6a-analysis-dashboard` · **HEAD:** `2d0e1bc768ecbedde9dc58a91ef914e1e6a5be97`
**Python:** 3.14.4 (venv پروژه) · **Node:** 24.16.0 · **Docker:** 29.8.2 / Compose v5.6.0
**نوع ممیزی:** فقط‌خواندنی روی کد پروژه. تنها نوشتن‌ها: چهار فایل گزارش در `docs/` و یک پوشهٔ موقت `/.tmp-audit-2026/` برای لاگ و DB آزمایشی.

---

## 0. روش و مرز شواهد

هر ادعای این گزارش یکی از این سه برچسب را دارد:

| برچسب | معنا |
|---|---|
| **MEASURED** | در همین نوبت با اجرای واقعی روی همین ماشین اندازه‌گیری شده (دستور + خروجی در گزارش). |
| **CODE-INSPECTED** | از خواندن کد و تست تأیید شده، ولی در این نوبت اجرا نشده. |
| **NOT_VERIFIED / BLOCKED** | شاهد کافی نیست یا به ورودی مالک/سرویس خارجی نیاز دارد. |

اعداد مستندات قبلی (WP-18، STAGE_STATUS، README) **به‌عنوان شاهد امروز پذیرفته نشدند**؛ فقط به‌عنوان ادعای تاریخی ذکر شده‌اند.

### دستورهای اندازه‌گیری اصلی

```bash
git status --porcelain=v1            # 60 ورودی (modified + untracked)
ruff check backend domains tests scripts source_bot
python scripts/check_legacy_ui_backup.py --live-only
python -m pytest tests -q            # کل suite روی SQLite
python -c "create_app(); app.openapi()"
uvicorn backend.main:app --port 18102/18103/18104/18105   # با DB آزمایشی
```

---

## A. وضعیت کلی پروژه

**پروژه تکمیل‌شده نیست.** یک مونولیت واقعی و نسبتاً بزرگ با هستهٔ سالم است، اما:

1. مجموعهٔ تست در وضعیت فعلی **سرخ** است: **9 failed / 1900 passed / 1 skipped** (MEASURED).
2. مسیر محلی مستندشده (SQLite + Alembic) **نوشتن در دیتابیس را می‌شکند** (GI-DB-001) — عملاً «افزودن منبع» در UI محلی خطای 503 می‌دهد.
3. ادعای «هیچ شکاف کدی باز نمانده» در WP-18 با شواهد امروز سازگار نیست.
4. بخش‌هایی واقعاً کار می‌کنند و با اجرای مستقیم اثبات شدند: Auth/Session/CSRF، AI Gateway زنده با Provider رایگان، Ingestion واقعی RSS، Dedup، UI تک‌فایلی متصل به API.

---

## B. Git و وضعیت Working Tree (MEASURED)

```
branch: step6a-analysis-dashboard
HEAD:   2d0e1bc docs: add completion plan for stages 96-104
origin/main: 31b4ca4  (شاخهٔ جاری روی origin/step6a-analysis-dashboard)
git status --porcelain: 60 ورودی
  - modified tracked: 25 فایل
  - untracked: 35 مورد (شامل 4 گزارش ممیزی قبلی، 19 سند WP، 10 فایل تست جدید، 1 migration، 2 اسکریپت، 3 spec جدید e2e)
```

نکات:

- **CI راه‌دور `NOT_VERIFIED`**: هیچ اجرای GitHub Actions برای این SHA قابل بازبینی نبود (بدون push و بدون دسترسی شبکه به وضعیت PR). این محدودیت ممیزی است، نه شاهد موفقیت.
- **خطر از دست رفتن کار**: 60 ورودی uncommitted شامل تغییرات مهم کد (`gateway.py`, `auth.py`, `settings.py`, `index.html`) و یک migration جدید `a9f1c2d3e4b5_promote_users_to_admin.py` است.
- گزارش‌های قبلی (`AUDIT_2026_PART1..4.md`, `WP00_TO_WP18_CONSOLIDATED_REPORT.md`) خودشان untracked هستند؛ یعنی منبع «وضعیت رسمی» در مخزن تثبیت نشده است.

---

## C. معماری واقعی (MEASURED + CODE-INSPECTED)

| مؤلفه | اندازهٔ اندازه‌گیری‌شده |
|---|---|
| فایل‌های Python در `backend/` | 21,721 خط |
| `domains/` | 20,166 خط، 34 دامنه (یکی خالی: `domains/entities/`) |
| `source_bot/` | 3,276 خط |
| Routerها | 52 فایل/تگ، 241 route object |
| OpenAPI | **220 path، 235 operation** |
| Migration | 51 revision، **1 head** = `a9f1c2d3e4b5` |
| تست | 166 فایل `.py` در `tests/`، ~1709 تابع تست، **1910 مورد collect‌شده** |
| UI | `backend/static/index.html` = 3,900 خط / 495 KB سرو‌شده، **26 صفحه**، 18 کانتینر live، 36 loader، 85 ارجاع endpoint |

معماری همان چیزی است که `ARCHITECTURE.md` می‌گوید: FastAPI app factory + دامنه‌های جدا + صف بادوام `ArticleDispatch` + UI تک‌فایلی. هیچ سرویس worker جدا یا Redis وجود ندارد (طبق طراحی).

### جریان واقعی داده (اثبات‌شدهٔ امروز)

```
RSS واقعی (BBC World) --fetch--> 5 مورد --> normalize --> dedup --> priority --> Document+Article در DB
   --> /api/inbox (3+5 ردیف واقعی)  --> dispatch pending (آنالیز وابسته به AI/provider)
```

اجرای دوم همان فید: `fetched=5, stored=0, duplicates=5` → **dedup در عمل کار می‌کند**.

---

## D. وضعیت هر ماژول (خلاصه؛ جزئیات در FEATURE_COMPLETION_MATRIX)

| ماژول | وضعیت | شاهد |
|---|---|---|
| Backend / App factory | VERIFIED | app ساخته و سرو شد؛ 235 operation |
| Auth (session/CSRF/RBAC) | VERIFIED (MEASURED) | login 200 → `/api/auth/me` 200؛ POST بدون CSRF → 403؛ POST نامعتبر → 422 |
| AI Gateway | VERIFIED (MEASURED) | فراخوان زندهٔ `openrouter/free` → 200، `is_mock=false`، 3.3s |
| Provider/Model catalog | VERIFIED (MEASURED) | `/api/settings/providers/catalog` → لیست 7 kind با free_policy_status |
| Ingestion (RSS واقعی) | VERIFIED (MEASURED) | 5 خبر واقعی ذخیره شد |
| Dedup | VERIFIED (MEASURED) | اجرای دوم: 5 duplicate، 0 stored |
| Source Management | **PARTIAL** | ساخت منبع روی SQLite مهاجرت‌شده 503 (GI-DB-001)؛ `/ingest/all` منابع بدون `collection_method=rss` را بی‌صدا رد می‌کند (GI-OPS-001) |
| Local screening (Kev/Laya) | DISABLED تا پذیرش Gold Set | `/api/local-runtimes/status` → هر دو `DISABLED`؛ مسیرهای runtime روی `H:` وجود دارند |
| Dispatch | PARTIAL | API/مدل‌ها و recovery موجود؛ در این اجرا task تولید نشد چون آنالیز به provider/زمان‌بند نیاز دارد |
| Event/Claim/Evidence/Entity | CODE-INSPECTED + تست | در DB آزمایشی صفر ماند چون آنالیز اجرا نشد |
| GraphRAG / Knowledge Graph | PARTIAL | سرویس واقعی موجود؛ ارزیابی آن با پاسخ synthetic انجام می‌شود (`run_graphrag_eval.py`) |
| Debate / Chat / Evaluation | VERIFIED (chat زنده) / CODE-INSPECTED | chat زنده اثبات شد؛ debate و evaluation تست دارند ولی اجرای واقعی چندمدلی انجام نشد |
| Archive / Telegram | CODE-INSPECTED | `telegram.py` واقعی (multipart/download/roundtrip)؛ ارسال زنده نیازمند credential |
| Alerts / Notification | PARTIAL | کانال Telegram/SMTP واقعی در `delivery.py`؛ ارسال زنده در این نوبت انجام نشد |
| Retention / Disk | CODE-INSPECTED | `RetentionService` + `disk_status` موجود؛ auto-purge پیش‌فرض خاموش |
| Backup | PARTIAL | `scripts/db_backup.py` از `docker exec pg_dump` استفاده می‌کند → روی SQLite/بدون Docker کار نمی‌کند |
| Settings / Control Plane | VERIFIED (MEASURED) | catalog و configuration plane پاسخ 200 |
| Windows Runtime 24/7 | **NOT_IMPLEMENTED** | WP-16 خودش DEFERRED است؛ هیچ Task Scheduler/service/runbook اجرایی وجود ندارد |

---

## E. دیتابیس (MEASURED)

- `DATABASE_URL` در `.env` = `sqlite:///./dev.db`؛ فایل `dev.db` موجود، 54 جدول، `alembic_version = a9f1c2d3e4b5`.
- محتوای `dev.db`: `users=1`, `sessions=1`, **همهٔ جداول داده‌ای صفر** (`sources`, `documents`, `articles`, `events`, `claims`, `evidence`, `forecasts` = 0).
- زنجیرهٔ مهاجرت: 51 revision، یک head → سالم.
- **اما DDL تولیدشده برای SQLite خراب است:** `created_at DATETIME DEFAULT (now())` و SQLite تابع `now()` ندارد.

شاهد مستقیم (MEASURED):

```
POST /api/sources -> 503
{"detail":"database unavailable","error":{"code":"DB_UNAVAILABLE"}}
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unknown function: now()
[SQL: INSERT INTO sources (...) RETURNING created_at, updated_at]
```

مقایسهٔ DDL:

```
Alembic (dev.db)      : created_at DATETIME DEFAULT (now())
Base.metadata.create_all: created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

یعنی تست‌ها (که schema را با `create_all` می‌سازند) این باگ را نمی‌بینند؛ کاربر واقعی که `alembic upgrade head` می‌زند می‌بیند. این توضیح می‌دهد چرا `dev.db` خالی است.

---

## F. وضعیت AI (MEASURED)

- `.env`: `MOCK_MODE=false`, `AI_DEFAULT_PROVIDER=openrouter`, `OPENROUTER_MODEL=openrouter/free`, `GEMINI_MODEL=gemini-3.5-flash`, `GROQ_MODEL=openai/gpt-oss-20b`. هر شش credential کلیدی (Gemini/OpenRouter/Groq/Cloudflare/SMTP/encryption) **SET** هستند (مقدار خوانده/چاپ نشد).
- Free Policy یک allowlist دقیق (provider, model) است؛ `openrouter/free` مجاز است و در نتیجه مسیر پیش‌فرض policy-compliant است.
- **فراخوان زنده:**

```
POST /api/ai/chat -> 200
{"text":"PONG","provider":"openrouter","model":"baidu/ernie-5.5-flash-preview:free",
 "usage":{"total_tokens":92},"latency_ms":3307.08,"is_mock":false}
```

- عیب واقعی: اگر در زنجیره به Provider دوم برسد که مدل پیش‌فرضش در allowlist نیست، خطای اصلی Provider با `model_not_allowed` (403) **پوشانده می‌شود** — عامل 7 تست سرخ (GI-AI-001).
- Kev/Laya: `enabled=false`، state=`DISABLED`. مسیرهایشان روی `H:\GIRuntime\...` **وجود دارند** (MEASURED) اما اجرا نشده‌اند.

---

## G. Frontend (MEASURED + CODE-INSPECTED)

- `GET /` → 200، `text/html`, 494,999 bytes.
- 26 صفحه در registry؛ مسیرها با `data-page` و History API؛ هر صفحه loader دارد (`loadDashboard`, `loadInbox`, ...).
- لایهٔ شبکه: `api()` با timeout، AbortController، کش sessionStorage، حالت «داده کهنه»، بنر آفلاین، CSRF header، `credentials:'same-origin'`.
- 149 استفاده از `innerHTML`، اما helper `esc()` برای escape وجود دارد و در مسیرهای دیده‌شده استفاده می‌شود (XSS سیستماتیک دیده نشد؛ ممیزی کامل هر 149 نقطه انجام نشد).
- باقی‌ماندهٔ نمونه/دکوراتیو: helperهای `chartPanel()`/`metrics()` با دادهٔ ثابت نمونه هنوز در فایل هستند (`metrics()` استفاده نمی‌شود = کد مرده).
- E2E: 7 spec در `tests/e2e/`، اما **هیچ job E2E در CI نیست** و `package.json` هیچ script ندارد.

---

## H. امنیت (CODE-INSPECTED + MEASURED)

شواهد مثبت (MEASURED):

- `POST /api/sources` بدون `X-CSRF-Token` → **403 FORBIDDEN**.
- بدون session/API key → 401؛ session name/role درست برمی‌گردد.
- رمزها Argon2id؛ در DB فقط `token_hash`/`csrf_hash`؛ کوکی `HttpOnly` + `SameSite=lax`.
- Security headers (`X-Frame-Options: DENY`, `CSP`, `nosniff`) در `backend/core/security.py`.
- Rate limit روی login/register/recovery با پنجرهٔ DB؛ `RateLimitMiddleware` سراسری.
- SSRF: گارد `GuardedTransport`/`host_is_private` روی فید و آداپترها؛ تست‌های امنیتی موجود.
- `/health/db` فقط status می‌دهد و جزئیات پشت auth است (خوب).

ریسک‌های باز:

- SMTP App Password طبق مستندات قبلی افشا شده و باید rotate شود (خارج از توان ممیزی؛ `BLOCKED_OWNER`).
- rate limit تک‌فرایندی است (بدون Redis) → با چند worker دور زدنی است (مستندشده).
- `.env` واقعی روی دیسک است (gitignore شده)؛ هرکسی به فایل‌سیستم دسترسی دارد کلیدها را دارد — طبیعی برای self-hosted، اما باید در runbook باشد.

---

## I. Windows و اجرای محلی (MEASURED)

| مورد | نتیجه |
|---|---|
| `python scripts/check_env.py` | **exit 0** — Git/Python/pip/Node/npm/Docker/Compose همه OK |
| سرور بدون Docker | بالا آمد (`uvicorn` روی 18102/18103/18104/18105) |
| UI از همان سرور | 200، 495 KB |
| Docker/Compose | نصب و daemon در دسترس |
| PostgreSQL محلی | `psql` روی PATH نیست؛ PG فقط داخل Docker |
| Local AI runtime | مسیرها روی `H:` موجود، ولی state=DISABLED |

**نتیجهٔ Windows:** برنامه با SQLite «بالا می‌آید و می‌خواند»، ولی با schema مهاجرت‌شده **نوشتن منبع/رکوردهای TimestampMixin شکست می‌خورد** (GI-DB-001). با PostgreSQL (Docker) این مشکل وجود ندارد. بنابراین «اجرای کامل محصول روی Windows» امروز **آماده نیست** — نه به دلیل Python/Node، بلکه به دلیل باگ migration + نبود runtime پایدار ۲۴/۷.

---

## J. تست و CI (MEASURED)

اجرای واقعی روی SQLite (همان lane پیش‌فرض):

```
9 failed, 1900 passed, 1 skipped, 746 warnings in 566.86s
Python 3.14.4 · HEAD 2d0e1bc + working tree dirty
```

| تست شکست‌خورده | علت ریشه‌ای |
|---|---|
| `test_fullstack_integration.py` × 7 (503/504/502/429) | GI-AI-001: fallback به openrouter با مدل غیرمجاز → 403 `model_not_allowed` جای خطای واقعی |
| `test_health.py::test_db_pool_sized_for_scheduled_bursts` | تست فرض می‌کند engine با `pool_size` ساخته می‌شود؛ روی SQLite فقط `{'future': True}` |
| `test_permission_matrix_doc.py::test_permission_doc_matches_code` | `POST /api/settings/providers/{id}/auto-detect-model` در `docs/ROLE_MATRIX.md` نیست |

- **Ruff:** `All checks passed!` (MEASURED) — ادعای 4 خطای Ruff در گزارش قبلی دیگر معتبر نیست.
- **Legacy UI guard:** OK (MEASURED).
- **CI:** سه job (`backend` PG + full suite، `backend-sqlite`، `docker`) — محتوای فایل درست است، ولی **اجرای راه‌دور برای این SHA تأیید نشده**.
- **تست PG در این نوبت اجرا نشد** (نیازمند PG زنده؛ محدودیت ممیزی). اعداد PG قبلی «گزارش‌شده» هستند.

---

## K. محدودیت‌های این ممیزی

1. CI راه‌دور و وضعیت PRها بررسی نشد (بدون network push/permission).
2. lane PostgreSQL 16 دوباره اجرا نشد؛ فقط SQLite.
3. Playwright E2E دوباره اجرا نشد (نیازمند Chrome و backend/کاربر تست).
4. ارسال زندهٔ Telegram/SMTP و Kev/Laya اجرا نشد (credential/زمان).
5. تست AI فقط یک فراخوان chat بود؛ debate/evaluation چندمدلی، extraction ساختاریافته و screenings واقعی اجرا نشد.
6. تحلیل امنیتی روی همهٔ 149 نقطهٔ `innerHTML` و همهٔ endpointها انجام نشد.
7. مقادیر secret خوانده/چاپ نشد؛ فقط SET/MISSING.

---

## L. نتیجهٔ نهایی این گزارش

هستهٔ مهندسی واقعی است و چند مسیر کلیدی (Auth، Gateway زنده، Ingestion واقعی، Dedup، UI) با اجرای مستقیم اثبات شد. اما سه چیز مانع «تکمیل» است:

1. **باگ P0 دیتابیس** روی مسیر SQLite/Alembic که نوشتن را می‌شکند.
2. **مجموعهٔ تست سرخ** به‌همراه رگرسیون error-mapping در Gateway.
3. **نبود runtime پایدار ۲۴/۷ و نبود شاهد CI راه‌دور** برای ادعای «آمادهٔ محصول محلی».

وضعیت نهایی پیشنهادی: **PARTIALLY COMPLETE** (دلیل کامل در انتهای `REMAINING_WORK_AND_DEBUGGING_PLAN.md`).


---

## ضمیمهٔ اجرا — ۱۴ نوامبر ۲۰۲۶ (CONTROLLED REPAIR EXECUTION)

این بخش وضعیت اقلام این گزارش را پس از اجرای اصلاحات به‌روز می‌کند. سند اصلی حفظ شده است.

| قلم | وضعیت قبلی | وضعیت پس از اجرا | شاهد |
|---|---|---|---|
| GI-DB-001 (`DEFAULT (now())`) | شکست نوشتن روی SQLite/Alembic | **FIXED** | ثبت تابع `now` روی اتصال SQLite + `tests/test_sqlite_alembic_writes.py` (۴ تست) + اجرای واقعی روی DB تازه |
| GI-DB-002 (`SELECT version()` روی SQLite) | health کاذب degraded | **FIXED** | `_server_version()` dialect-aware؛ `/health/db` = `{"status":"ok"}` |
| GI-AI-001 (پوشاندن خطای Provider) | ۷ تست سرخ | **FIXED** | `attempted` + رد نامزد غیرمجاز پیش از فراخوانی؛ تست تقویت‌شده |
| GI-OPS-001 (منبع با feed_url نادیده) | ingestion بی‌صدا خالی | **FIXED** | پیش‌فرض rss + فیلتر `or_`؛ `fetched=20, stored=20` |
| GI-TEST-002 (تست pool) | شکست روی SQLite | **FIXED** | `skipif` مخصوص لاین SQLite (بدون حذف assertion) |
| GI-DOC-001 (Role Matrix) | ناسازگار | **FIXED** | ردیف `auto-detect-model` + تست تطابق |
| GI-UI-001 (مسیر اجرای ingestion در UI) | نبود | **IMPROVED** | دکمهٔ «دریافت اکنون» + E2E واقعی |
| GI-TEST-004 (warning های Deprecation) | نویز | OPEN | 746 warning باقی است؛ مربوط به کتابخانه‌ها |
| CI راه‌دور | NOT_VERIFIED | **NOT_VERIFIED** | بدون push توسط مالک |

### شواهد کلان این اجرا

- Suite کامل SQLite: **1912 passed / 2 skipped / 0 failed** (590.18s).
- Suite کامل PostgreSQL 16.16: **1913 passed / 1 skipped / 0 failed** (1142.60s).
- Ruff: `All checks passed!`.
- Alembic روی DB تازه: `upgrade head` → ۵۴ جدول، head `a9f1c2d3e4b5`.
- چرخهٔ PG: upgrade → downgrade base → upgrade، همه EXIT=0.
- E2E واقعی UI: `1 passed` (ساخت منبع از فرم → ingest → Inbox → جزئیات).
- زنجیرهٔ AI واقعی: classification/routing/event/claim/evidence/graph با `is_mock=false`.

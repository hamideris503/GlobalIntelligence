# گزارش WP-00 و WP-01 — نقشه‌راه v2.2

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **Branch:** `step6a-analysis-dashboard` · **HEAD:** `2d0e1bc768ecbedde9dc58a91ef914e1e6a5be97`
**Repository root:** `J:\Documents\GlobalIntelligence` (همان checkout محلی؛ هیچ مسیر دیگری فرض نشد)
**مبنای این گزارش:** اجرای مستقیم روی همین Working Tree، بدون Build/Migration/Seed و بدون `pull/fetch/push`.

---

## WP-00 — ممیزی فقط‌خواندنی

### 1. Working Tree

| دسته | تعداد | فایل‌ها |
|---|---:|---|
| Modified | 6 | `.env.example`, `TASKS.md`, `backend/api/routers/alerts.py`, `backend/static/index.html`, `docs/FIXES_BACKLOG.md`, `docs/ROADMAP_STAGE96_104.md` |
| Untracked | 6 | `AUDIT_2026_PART1.md` … `AUDIT_2026_PART4.md`, `scripts/fix_alerts_router.py`, `scripts/fix_ui.py` |
| Staged | 0 | — |

Snapshot تاریخی گزارش‌های C/D («۶ Modified + ۲ Untracked») دیگر معتبر نیست؛ وضعیت واقعی **۶ + ۶** است.

### 2. آمار قابل بازتولید (خروجی مستقیم، بدون عدد دستی)

| سنجه | مقدار |
|---|---:|
| Python file در `backend/` | 173 |
| Python file در `domains/` | 172 |
| Domain directory | 36 |
| Python file در `source_bot/` | 23 |
| Python file در `scripts/` | 22 |
| Router file | 54 |
| `@router.` decorator | 234 |
| Migration file | 50 |
| Alembic head | **یک head**: `f0auth_users_accounts` |
| Test file (`tests/test_*.py`) | 154 |
| Playwright spec (`tests/e2e/`) | 3 (`routes`, `smoke`, `axe`) + `global-setup.js` |
| UI lines (`backend/static/index.html`) | 3566 |
| UI page function (الگوی `function x(){return \``) | 26 |
| UI `api('…')` callsite | 93 |
| n8n workflow JSON | 8 |
| CI job | 3 (`backend`, `backend-sqlite`, `docker`) + trigger `push` |
| Python runtime محلی | 3.14.4 |

شمارش ۲۵ صفحه/۹۴ call تاریخی با کد فعلی هم‌خوان نیست: **۲۶ page function و ۹۳ call**. عدد مرجع، همین خروجی دستور است.

### 3. Credential / Configuration (فقط SET/MISSING — هیچ مقدار خوانده یا چاپ نشد)

| متغیر | وضعیت |
|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM` | SET |
| `SMTP_PASSWORD` | SET (طبق سیاست: `COMPROMISED` تلقی می‌شود تا چرخش) |
| `SMTP_USER` | **MISSING** |
| `SMTP_TO` | **MISSING** (در `.env` غایب) |
| `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | SET |
| `AI_PAID_ENABLED`, `AI_DAILY_BUDGET_USD` | MISSING → پیش‌فرض = Paid خاموش (مطابق §3.3.2) |
| `MOCK_MODE`, `API_KEY`, `SECRET_KEY`, `APP_ENCRYPTION_KEY` | SET |

**تناقض یافته‌شده (GI-AI/SEC، مسئلهٔ نام‌گذاری نه Secret):** دو مسیر کد دو نام متفاوت برای یک credential می‌خوانند:

- `domains/alerts/delivery.py:147-148` → `SMTP_USER` + `SMTP_PASSWORD` (ایمیل Alert)
- `backend/core/config.py:146` → `smtp_username` یعنی `SMTP_USERNAME` (ایمیل Auth/Verification)

یعنی مسیر Auth در حال حاضر بدون `SMTP_USERNAME` هرگز login نمی‌کند و مسیر Alert بدون `SMTP_USER` هم. این یک کد/کانفیگ gap است، نه نیاز به درخواست Secret جدید از مالک؛ در WP-04/WP-14 باید به یک نام مرجع یکپارچه شود.

### 4. مسیر دادهٔ Gold Set (خارج از Repository، فقط‌خواندنی)

`H:\GIRuntime\labeling` **موجود است** و شامل `all-labels-review.zip`, `review-package/`, `reviewed/`, `backups/`, `pilot_stage102.py` و پوشه‌های مرحله‌ای `stage49`…`stage53` است. محتوای فایل‌ها خوانده/تغییر/import نشد؛ این کار در WP-08 انجام می‌شود.

### 5. Stage ledger (فشرده)

| WP | وضعیت فعلی | دلیل |
|---|---|---|
| WP-00 | `VERIFIED_COMPLETE` | همین گزارش، خروجی مستقیم |
| WP-01 | `VERIFIED_COMPLETE` | بخش بعدی |
| WP-02 | `PARTIALLY_VERIFIED` | اجرای PG/CI تازه انجام نشده در این نوبت؛ remote CI `NOT_VERIFIED` |
| WP-03 | `NOT_VERIFIED` | Manifest UI و ماتریس صفحه/API ساخته نشده |
| WP-04…WP-18 | `NOT_VERIFIED` / `EVIDENCE_STALE` | با ترتیب وابستگی §5.1 |

---

## WP-01 — حفاظت Working Tree، Secret Hygiene، Lint

### WP-01.1 — Snapshot

Snapshot کامل فایل‌های تغییر‌یافته و untracked (بدون `.env`، بدون هیچ Secret) در:

```
backups/roadmap_v22/wp01_snapshot_20261114/       ← فایل‌های کپی‌شده
backups/roadmap_v22/wp01_snapshot_20261114/manifest.json   ← path + bytes + SHA-256 + branch + HEAD
```

فایل‌های snapshot‌شده: `TASKS.md`, `backend/api/routers/alerts.py`, `backend/static/index.html`, `docs/FIXES_BACKLOG.md`, `docs/ROADMAP_STAGE96_104.md`, `.env.example`, `scripts/fix_alerts_router.py`, `scripts/fix_ui.py`, `AUDIT_2026_PART1..4.md`. مسیر `backups/` در `.gitignore` است، بنابراین هیچ دادهٔ محلی وارد Git نمی‌شود.

هیچ فایل Modified/Untracked حذف، reset، rename یا overwrite نشد. Scriptهای patch (`fix_ui.py`, `fix_alerts_router.py`) **اجرا نشدند** — فقط lint آن‌ها اصلاح شد.

### WP-01.2 — Secret Hygiene

- Secret scan روی ۹۰۵ فایل tracked: **۰ hit** برای `AIza…`, `sk-…`, `gsk_…`, `sk-ant-…`, `AKIA…`, `BEGIN PRIVATE KEY`, الگوی App Password.
- `.env` نه tracked است و نه در snapshot/report کپی شد؛ گزارش فقط `SET/MISSING`.
- `SMTP_PASSWORD` طبق §0.A.1 `COMPROMISED` ثبت می‌شود. چرخش App Password فقط با اقدام مالک در Google Account ممکن است:
  **`BLOCKED_OWNER_CREDENTIAL_ROTATION`** — تا آن زمان SMTP live re-test انجام نشد و نتیجهٔ قدیمی صرفاً `OWNER_REPORTED_TEST_SUCCESS` باقی می‌ماند.

### WP-01.3 — Lint / Diff hygiene

| بررسی | قبل | بعد |
|---|---|---|
| `ruff check backend domains tests scripts source_bot` | 4 خطا (`I001` در `alerts.py:204`, `UP009`×2 و `F401` در دو script) | **0 خطا** (exit 0) |
| `git diff --check` | 1 خط (trailing whitespace در `index.html:2523`) | **پاک** (exit 0) |

Diff اصلاحات کاملاً حداقلی است: یک blank line برای مرتب‌سازی import داخل تابع `test_deliver`، حذف coding declaration و `import re` بلااستفاده در دو script یک‌بارمصرف، و حذف trailing whitespace یک خط UI. هیچ منطقی تغییر نکرد.

### تست تأیید

```
python -m pytest tests -q -k "alert or auth_email or test_alerts"
→ 21 passed, 1793 deselected
```

---

## معیارهای پذیرش WP-01

| معیار | نتیجه |
|---|---|
| شناسایی و حفظ همهٔ فایل‌های local/untracked | PASS (۶+۶، snapshot با SHA-256) |
| Snapshot قابل بازیابی از تغییرات مجاز | PASS |
| عدم افشای Secret در خروجی/گزارش/Backup جدید | PASS (۰ hit، `.env` خارج از snapshot) |
| چرخش Secret افشاشده یا ثبت blocker مالک | PASS به‌صورت `BLOCKED_OWNER_CREDENTIAL_ROTATION` |
| Lint پاک روی Working Tree | PASS (ruff 0، diff-check 0) |

**فقط اقدام مالک:** باطل‌کردن App Password افشاشده در Google و قرار دادن مقدار تازه در `.env` محلی؛ سپس SMTP live re-test با مقصد آزمایشی اجرا می‌شود.

---

---

# WP-02 — تثبیت فنی، PostgreSQL، Migration و Tests

### 0. مانع محیطی که کشف شد (GI-OPS)

پورت publish‌شدهٔ سرویس PG موجود از Host کار نمی‌کند: `127.0.0.1:15432 → gi_postgres:5432` اتصال TCP را می‌پذیرد و بلافاصله RST می‌دهد (`recv b''`)، `gi_backend:8000` هم همین وضع را دارد، در حالی که `gi_n8n:5678` سالم است (HTTP 200). این یعنی port-proxy داکر برای آن کانتینرهای قدیمی stale شده — نه خرابی خود PG (از داخل شبکهٔ کانتینر کوئری سالم است).

**اقدام بدون دست‌زدن به سرویس‌های مالک:** یک کانتینر یک‌بارمصرف تازه ساخته شد:
`docker run -d --name gi_wp02_pg -p 127.0.0.1:15434:5432 postgres:16-alpine` با credential تولیدشدهٔ تصادفی (در فایل gitignored، نه در گزارش). اتصال از Host موفق بود و پس از پایان کار، کانتینر و دیتابیس موقت **حذف شدند**؛ شش کانتینر مالک دست‌نخورده باقی ماند.

### WP-02.1 — Inventory و Collection

| سنجه | مقدار |
|---|---:|
| Collected test case | **1814** |
| Static test function | **1653** |
| Test class | 0 |
| `@pytest.mark.parametrize` decorator | 36 |
| Case idهای پارامتری | 197 |
| اختلاف | 161 = **تماماً** بازشدن parametrize در ۲۱ فایل |

بزرگ‌ترین منابع بازشدن: `test_priority_thresholds_levels.py` (+31)، `test_bot_config_preflight.py` (+20)، `test_role_matrix.py` (+17)، `test_mock_schema.py` (+14)، `test_ai_error_responses.py` (+11).

بنابراین اختلاف تاریخی «۱۶۵۳ تابع / ۱۸۱۴ case» یک تناقض نیست؛ همان parametrize است. اختلاف ۳۷/۱۵۴ فایل هم با شمردن `tests/test_*.py` (۱۵۴) در برابر ۱۵۴ found + 3 spec پلی‌رایت `.spec.js` توضیح داده می‌شود.

دستور مرجع قابل بازتولید: `python -m pytest tests --collect-only -q | tail -1`

### WP-02.2 — PostgreSQL، Migration و Dispatch

| بررسی | نتیجه |
|---|---|
| `alembic heads` | یک head: `f0auth_users_accounts` |
| Migration file / revision | ۵۰ / ۵۰ (خطی، بدون branch) |
| `upgrade head` | exit 0 → **۵۴ جدول** |
| `downgrade base` | exit 0 → ۱ جدول (`alembic_version`) |
| `upgrade head` مجدد | exit 0 → **۵۴ جدول**، `alembic_version = f0auth_users_accounts` |
| اثبات اتصال واقعی تست‌ها به PG | `pg_stat_activity` یک session فعال روی `gi_test_lane_wp02` نشان داد + اتصال مستقیم psycopg |
| `SKIP LOCKED` | موجود و سالم است (`service.py:473`، `with_for_update(skip_locked=True)`) — **بازنویسی نشد** |
| `test_claim_is_atomic`, `test_claim_is_atomic_under_concurrency` | در lane پستگرس **pass**؛ claim دوم `False` و claim موازی بدون deadlock |

### WP-02.3 — تست‌های تاریخی

موارد F-02…F-11 و F-20/F-23 (deadlock، DNS/DSN، FK article، offline DNS guard، CWD، temp-dir ویندوز، atomic claim، JobRun race، ETag) همه در suite فعلی حاضرند و در lane پستگرس پاس شدند. هیچ تستی حذف/Skip/ضعیف نشد و هیچ Timeout افزایش نیافت.

### WP-02.4 — CI

`ci.yml` بازخوانی شد (فرض سه job درست است):

- `backend`: postgres:16 service، Python 3.12، ruff روی `backend domains tests scripts source_bot`، legacy-UI guard، `alembic upgrade/downgrade/upgrade`، سپس **full suite** روی PG.
- `backend-sqlite`: `pytest ../tests -q -m "not pg"`.
- `docker`: build هر دو image.

**Playwright در CI نیست** (`tests/e2e/{routes,smoke,axe}.spec.js`). طبق §WP-02.4 این یا باید اضافه شود یا استثنای مستند با تصمیم مالک داشته باشد: اینجا به‌صورت `DEFERRED_BY_OWNER` تا تصمیم صریح ثبت می‌شود و در این نوبت job جدید ساخته نشد.
- Remote CI همچنان `NOT_VERIFIED` — نیازمند push مالک است.

### نتایج اجرای واقعی (HEAD `2d0e1bc` + تغییرات WP-01، Python 3.14.4)

| Lane | نتیجه | زمان |
|---|---|---|
| PostgreSQL 16.15 | **1814 passed / 0 failed** | 849.62 s |
| SQLite | **1813 passed / 1 skipped / 0 failed** | 411.87 s |
| Legacy UI guard (`--live-only`) | exit 0 | — |
| ruff | 0 خطا | — |

لاگ‌ها: `backups/roadmap_v22/wp02_pg_suite.log`, `backups/roadmap_v22/wp02_sqlite_suite.log` (gitignored).

### پذیرش WP-02

| معیار | نتیجه |
|---|---|
| Full suite روی PG با صفر failure | PASS (1814) |
| SQLite lane مستقل | PASS (1813 + 1 skip) |
| Migration chain یک head + تست واقعی روی DB یک‌بارمصرف | PASS (up/down/up) |
| E2E در CI یا استثنای مستند | PARTIAL — استثنا ثبت شد، تصمیم مالک لازم |
| تعداد تست قابل توضیح/بازتولید | PASS (1653 تابع + 161 بازشدن parametrize = 1814) |
| Remote CI همان SHA | `NOT_VERIFIED` (نیازمند push مالک) |

---

# WP-03 — UI Inventory و Manifest (خلاصه)

گزارش کامل در `docs/UI_MIGRATION_MANIFEST.md`. خلاصهٔ نتایج:

- **۲۵ صفحهٔ واقعی** (رجیستری `pages`)؛ ۲۴ render function + `worldMonitorPage()`؛ `evidenceFlow`/`miniNetwork` کامپوننت‌اند نه صفحه.
- **۹۲ callsite `api()` + ۳ فراخوانی خام `fetch()`**، در مجموع ۸۵ endpoint یکتا؛ **هیچ‌کدام بدون route متناظر در FastAPI نیست** (تطبیق با ۲۴۰ route از `create_app().routes`).
- **۲ فایل مرجع پیدا نشد:** نقشه‌راه v1.9 و HTML مرجع Auth/WorldMonitor مالک در repo و `H:\GIRuntime` وجود ندارند ⇒ `BLOCKED_OWNER_REFERENCE_NOT_FOUND`؛ محتوای آن‌ها حدس زده نشد.
- **`GI-SEC-001` ابطال شد (اصلاح ثبت):** ادعای «نبود RBAC» غلط بود؛ `access_guard` روی ۵۱ router و `required_role(method, path)` در `backend/auth/deps.py` واقعاً اجرا می‌شوند. جزئیات در بخش WP-04.

---

# WP-04 — permission matrix و گیت Admin (نتیجه)

## 1. ماتریس واقعی (از کد)

`required_role(method, path)` روی ۲۴۰ route×method: **۱۱۳ viewer / ۴۱ analyst / ۸۶ admin**؛
`health` و `/api/auth/*` بیرون از `access_guard`. خواندن = viewer مگر
`/api/settings|archive|audit|local-runtimes|ops`؛ نوشتن = admin مگر `ANALYST_WRITE_PATHS`؛
پیش‌فرضِ ناشناخته = admin (default-deny). `X-API-Key` = نقش service؛ کاربر تأییدنشده بیرون از `/api/auth/*` مسدود.

## 2. Drift که پیدا و رفع شد

`docs/ROLE_MATRIX.md` از **۱۳ route** عقب بود و همه اضافه شدند:
`/api/dashboard/overview`, `/api/analyses` (+trace، +request), `/api/country-profiles` (+code),
`/api/decisions/{id}/review(s)`, `/api/forecasts/outlook`, `/api/retention/{disk,dry-run}`,
`/api/risk/matrix`, و `POST /api/alerts/test-deliver/{channel}` (از patch محلی مالک).

## 3. تست‌های قفل‌کننده

- `tests/test_permission_matrix_doc.py` — سند و کد باید دقیقاً برابر باشند؛ هر endpoint جدید بدون ردیف، تست را می‌شکند. + «هیچ route نویسنده‌ای با viewer» + خواندن‌های عملیاتی admin-only.
- `tests/test_admin_gate_allow_deny.py` — ۹ مسیر حساس: viewer→403، analyst→403 (`required=admin`)، admin→بدون 403؛ + سازگاری `X-API-Key` + مسدودبودن ایمیل تأییدنشده.

هیچ endpoint حساسی بازی نبود؛ گیت از قبل وجود داشت و کار واقعی، اثبات و قفل‌کردن آن بود.

# WP-04.3 / WP-04.4 — Session/Verification و Auth UI (نتیجه)

## 1. وضعیت واقعی (کشف، نه ساخت)

- **Backend:** ثبت‌نام، ورود، خروج، `me`، verify/resend، forgot-username/password، reset، change-password؛ توکن‌های `verify_email` (۲۴h) و `reset_password` (۲۰m) یک‌بارمصرف و hash‌شده؛ نرخ‌محدودی DB-backed؛ پاسخ‌های یکسان ضدِ enumeration.
- **UI:** هر هفت فرم به endpoint واقعی وصل‌اند؛ لینک `?token=` روی `GET /verify-email` و `GET /reset-password` به‌عنوان SPA shell سرو می‌شود (۴۰۴ نمی‌دهد).
- **حالت صادقانه:** `EMAIL_DELIVERY_NOT_CONFIGURED` / `EMAIL_DELIVERY_FAILED` هم در Backend و هم در UI؛ هیچ تأیید ساختگی.

## 2. دو باگ واقعی که رفع شد

| # | باگ | اثر | اصلاح |
|---|---|---|---|
| 1 | `_set_session_cookies` همیشه ۳۰ روز می‌گذاشت | کوکی Admin پس از ۳۰ روز می‌مرد در حالی که نشست سرور بی‌انقضاست (نقض سیاست ۳۶۵ روز) | پارامتر `days`؛ ورود Admin = ۳۶۵ روز |
| 2 | Auth فقط `SMTP_USERNAME`، Alert فقط `SMTP_USER` | با `.env` فعلی ایمیل Auth بی‌صدا بدون login می‌رفت | `AliasChoices("SMTP_USERNAME","SMTP_USER")` |

تأیید روی `.env` واقعی (masked): `smtp_username_resolved=SET` (قبلاً MISSING)، `email_delivery_configured=True`.

## 3. تست‌های جدید

`tests/test_auth_ui_contract.py` (قرارداد فرم↔endpoint، حالت not-configured، نبود shortcut، deep-link)،
`tests/test_email_config_alias.py` (alias و اولویت، با `_env_file=None` تا `.env` واقعی افشا نشود)،
و `test_login_cookie_lifetime_matches_session_policy` که پیش از اصلاح شکست می‌خورد.

## 4. آنچه هنوز ممکن نیست

آزمون واقعی SMTP: `BLOCKED_OWNER_CREDENTIAL_ROTATION` — App Password افشاشده باید در Google باطل شود؛ تا آن زمان فقط sink/mock تست شده و هیچ پیام واقعی ارسال نشده است.

## زیرمرحلهٔ بعدی (فقط یکی)

**WP-05.1** — stateهای استاندارد صفحه (loading/empty/error) و ناوبری URL/deep-link برای ۲۵ صفحه (شکاف‌های `GI-UI-001` و `GI-UI-002` که در WP-03 ثبت شد).

---

# WP-05.1 — ناوبری URL و stateهای صفحه (نتیجه)

## 1. کاری که واقعاً انجام شد

**`GI-UI-001` (deep-link) بسته شد.** در `backend/static/index.html`:

- `giPageFromHash()` — فقط شناسه‌های موجود در رجیستری `pages` را می‌پذیرد (هر چیز دیگر → `overview`).
- `giSyncUrl(id)` — در هر `renderPage` یک ورودی تاریخچه با `#/<page>` می‌سازد.
- شنوندهٔ `popstate` — back/forward همان صفحه را دوباره render می‌کند، با `giUrlSyncPaused` برای جلوگیری از حلقه.
- بارگذاری اولیه و مسیرهای پس از ورود دیگر همیشه `overview` را باز نمی‌کنند؛
  `renderPage(giPageFromHash()||'overview')` استفاده می‌شود (۴ callsite).

## 2. تصحیح ادعای قبلی دربارهٔ stateها (`GI-UI-002`)

شمارش ۶/۱/۲ مربوط به helperهای مشترک بود و نتیجه‌گیری «۲۵ صفحه بدون loading/empty/error» **نادرست** بود.
اندازه‌گیری واقعی: **۳۴ تابع `async function load…`** وجود دارد؛ **۳۳** مورد try/catch + پیام خالی/خطای فارسی
دارند و `loadInboxDetail` با `Promise.allSettled` + `giErrorHtml` خطا را مدیریت می‌کند. پس stateها وجود دارند؛
شکاف باقی‌مانده «استفادهٔ ناهمگون از helper مشترک» است و در manifest با همین دقت ثبت شد.

## 3. تست

`tests/test_ui_routing_contract.py` (۶ تست): اعتبارسنجی hash با رجیستری، همگام‌سازی URL + pushState + popstate،
احترام به deep-link در boot، بازگشت hash ناشناخته به overview، پوشش renderer برای هر ۲۵ صفحه،
و **سلامت نحوی هر سه بلوک `<script>` با `node --check`** (در نبود node تست skip می‌شود، نه pass).

checks: `pytest` روی ۶ تست routing → **۶ passed**؛ `ruff` ۰ خطا؛ `git diff --check` پاک.

## 4. آنچه بررسی نشد

رفتار واقعی در مرورگر (کلیک ناوبری، back/forward، refresh روی `#/settings`) اجرا نشد؛
تأیید فقط ایستا + نحوی است. این مورد در WP-18 (Local Product Acceptance) با Playwright پوشش داده می‌شود.

---

# WP-05.2 — دکمه‌های مرده و smoke مرورگری (نتیجه)

## 1. دکمه‌های بدون handler (پیدا و رفع شد)

با یک اسکن ساده، **۵ `data-action` بدون هیچ handler** پیدا شد؛ دکمه‌های کلیک‌پذیر که هیچ کاری نمی‌کردند:

| action | صفحه | اقدام |
|---|---|---|
| `debate` | مناظره | اتصال به `POST /api/debate/run` با ورودی هدف، `dry_run:true` (مدل زنده صدا زده نمی‌شود) + گیت نقش analyst |
| `analysis` | تحلیل AI | اتصال به `POST /api/analyses/request` (task=evidence_collection، limit=20) روی صف dispatch موجود |
| `void` | مناظره | اتصال به `POST /api/settings/debate-runs/{id}/void` با `reason`؛ رکورد حذف نمی‌شود، فقط `void` |
| `ack` | مناظره | API ندارد ⇒ دکمه حذف و با چیپ صریح `بررسی انسانی · NOT_CONNECTED` جایگزین شد |
| `filter` | شواهد | فیلتر سمت سرور ندارد ⇒ دکمه `disabled` با برچسب «اتصال ندارد» شد |

اضافه: ورودی `#debateTarget` برای هدف مناظره، کش `window.__debateRuns` برای هدف‌گیری ابطال، و `giNeedRole()` برای پیام فارسی کمبود نقش (UI فقط راهنما؛ گیت واقعی در Backend است).

## 2. smoke مرورگری واقعی (Playwright + Chromium)

`tests/e2e/deeplink.spec.js` (جدید، ۶ تست): deep-link مستقیم روی `#/macro`، تغییر URL با کلیک ناوبری، back/forward، refresh روی `#/sources`، fallback برای hash ناشناخته، و وجود دکمهٔ متصل + چیپ NOT_CONNECTED.

اجرا روی بک‌اند موقت SQLite (`127.0.0.1:18100`، کاربر `e2e` با نقش admin):

| spec | نتیجه |
|---|---|
| `deeplink.spec.js` | **6 passed** |
| `smoke.spec.js` | **4 passed** |
| `routes.spec.js` (همهٔ ۲۵ صفحه، بدون console error) | **25 passed** |
| مجموع | **35 passed / 0 failed** (۱.۹ دقیقه) |

تست استاتیک مکمل: `test_no_dead_data_actions` هر `data-action` بدون handler را رد می‌کند.

## 3. نکتهٔ روش

نسخهٔ اول اسپک با لوکیتور `[data-page="x"]` شکست خورد چون هم لینک ناوبری و هم نتیجهٔ palette این صفت را دارند (strict mode). اصلاح: `.nav-item[data-page="x"]`. این شکست، باگ محصول نبود.

## 4. باقی‌مانده WP-05 (برای نوبت بعد)

صفحه‌های `world` (فید رویداد واقعی)، `entity-graph` (جزئیات گره/همسایه‌ها)، `markets` (دریافت دادهٔ بازار از UI) و `evidence` (فیلتر محلی) همچنان فقط خواندنی‌اند؛ endpointها موجودند اما دکمه/جریان ندارند.

---

# WP-05.3 — کارکرد واقعی چهار صفحهٔ باقی‌مانده

## 1. چه چیزی واقعاً ساخته شد

| صفحه | قبل | بعد (WP-05.3) |
|---|---|---|
| `markets` | فقط «تازه‌سازی» (GET) | ورودی نماد + دکمهٔ **دریافت داده** → `POST /api/markets/fetch` (`fetcher=auto`) با بازخوانی جدول و نمایش خطای واقعی |
| `evidence` | دکمهٔ «فیلتر شواهد» غیرفعال | `select#evidenceFilter` واقعی: همه / تأییدشده / در انتظار / ردشده-متناقض / دارای شاهد — فیلتر روی دادهٔ GET `/api/claims` |
| `entity-graph` | کامل بود (تأیید شد) | بدون تغییر: کلیک گره جزئیات + روابط، کلیک یال وزن/اطمینان؛ حالا با داده پوشش تست دارد |
| `world` | کامل بود (تأیید شد) | بدون تغییر: سه دکمهٔ بازدریافت فید به `refreshAll` وصل‌اند؛ حالا پوشش تست دارد |

## 2. یک باگ واقعی که تست گرفت

نسخهٔ اول `giClaimStatusBucket` با **زیررشته** تطبیق می‌داد، پس `unverified` هم «verified» شمرده می‌شد و فیلتر «تأییدشده» دو ادعا نشان داد به‌جای یک. اصلاح: تطبیق **توکنی** (`split(/[^a-z]+/)`) — حالا `unverified` → سبد «در انتظار». تست Playwright قبل از اصلاح شکست و بعد از آن سبز شد.

## 3. پوشش مرورگری

`tests/e2e/pages.spec.js` (جدید، ۵ تست):

1. فیلتر شواهد: ۳ ادعا → `verified`=۱، `with_evidence`=۲، `rejected`=۱، `all`=۳ (شمارش واقعی DOM).
2. بازارها: جدول ۲ ردیف از دادهٔ seed؛ کلیک «دریافت داده» با `symbol=BRENT` به `/api/markets/fetch` می‌رود (پاسخ با `page.route` جایگزین شد تا وابستگی به سرویس بیرونی نباشد) و toast موفق می‌دهد.
3. گراف موجودیت: کلیک گره → پنل جزئیات شامل `Iran`، `IAEA` و رابطهٔ `cooperates_with`.
4. جهان: کلیک «↻ دریافت داده» بدون خطای کنسول.
5. deep-link هر چهار صفحه + همگامی nav.

اجرای کامل Playwright: **۴۰ passed / 0 failed** (pages ۵ + deeplink ۶ + smoke ۴ + routes ۲۵)، ۲.۱ دقیقه، بک‌اند SQLite موقت `127.0.0.1:18100`.

## 4. تست‌های استاتیک اضافه‌شده

`tests/test_ui_routing_contract.py`: `test_evidence_filter_is_local_and_wired`، `test_claim_status_bucket_is_token_exact`، `test_markets_fetch_is_wired_to_backend` (کل فایل ۱۱ تست سبز).

## 5. وضعیت WP-05

صفحه‌های ۲۵گانه رجیستری: همه رندر می‌شوند، هیچ دکمهٔ مرده‌ای نمانده، و جریان‌های نوشتن در `debate`/`analysis`/`markets` به API واقعی وصل‌اند. موارد باقی‌مانده در سطح **API نیستند**: «ثبت بررسی انسانی مناظره» (`NOT_CONNECTED`) و مسیر «استخراج گراف/Claims از رویداد» که به Job واقعی نیاز دارد.

---

# بستهٔ بازبینی ادعاها (بدون شمارهٔ نقشه‌راه) — ۱۴ نوامبر ۲۰۲۶

**چرا شمارهٔ نقشه‌راه ندارد:** فایل `GlobalIntelligence_Roadmap_v2.2.md` در این checkout
موجود نیست (فقط گزارش‌های خودمان به آن ارجاع می‌دهند). به‌جای اختراع دامنهٔ «WP-06»، بستهٔ
زیر از بک‌لاگ **موجود و اندازه‌گیری‌شده** انتخاب شد.

## انگیزهٔ اندازه‌گیری‌شده

هنگام بررسی دو قلم بک‌لاگ، دو نوع خطا پیدا شد:

1. **کهنگی:** `F-11` («`claim` بدون `SKIP LOCKED`») از قبل حل شده بود — `claimable()` در
   `backend/ai/dispatch/service.py:473` از `.with_for_update(skip_locked=True)` استفاده می‌کند.
   اگر کورکورانه «اصلاح» می‌شد، کد سالم بازنویسی می‌شد.
2. **ادعای غلط:** `GI-SEC-002` («`/api/alerts/test-deliver` گیت Admin ندارد») غلط است؛
   گیت سراسری `access_guard` آن را admin می‌کند و `required_role` هم همین را برمی‌گرداند.

## کار انجام‌شده

- بازآزمایی اقلام **P0/P1** (۱۳ قلم) با شاهد کد/دستور؛ جدول کامل در
  `docs/FIXES_BACKLOG.md` → «بازبینی ادعاها».
- `F-11` و `GI-SEC-002` با شاهد اصلاح شدند.
- تست نگهبان جدید `tests/test_doc_claims.py` (۴ تست):
  `claimable` برای دیالکت PG باید `FOR UPDATE SKIP LOCKED` تولید کند ·
  `test-deliver` باید admin باشد (با کنترل مثبت analyst/viewer) ·
  DSN لاین PG و ریشهٔ temp اختصاصی باید باقی بمانند ·
  هیچ `assert 'sqlite' in` در تست‌ها نماند.

## شاهد اجرا

- `pytest tests/test_doc_claims.py -q` → **۴ passed**
- `pytest tests/test_dispatch.py tests/test_permission_matrix_doc.py tests/test_admin_gate_allow_deny.py -q`
  → **82 passed / 1 skipped**
- `ruff check backend domains tests scripts source_bot` → **۰ خطا**

## آنچه بازآزمایی نشد

`P2` (۱۴ قلم) و `P3` (۸ قلم) بک‌لاگ؛ اجرای راه‌دور CI (`F-04`) هم همچنان
`NOT_VERIFIED` است و به push مالک نیاز دارد.

---

# WP-00 (نوبت WP-06) — ممیزی فقط‌خواندنی، ۱۴ نوامبر ۲۰۲۶

## 1. Repository

| سنجه | مقدار |
|---|---|
| root | `J:/Documents/GlobalIntelligence` |
| branch | `step6a-analysis-dashboard` (upstream `origin/...`, `+0 -0`) |
| HEAD | `2d0e1bc768ecbedde9dc58a91ef914e1e6a5be97` |
| staged | ندارد |
| modified (tracked) | ۱۱ فایل |
| untracked | ۱۶ فایل |
| نقشه‌راه v2.2 | `docs/GlobalIntelligence_Roadmap_v2.2.md` (۱۲۱۰۰۰ بایت، untracked) — پیدا شد و خوانده شد |

فایل‌های modified در شروع این نوبت: `.env.example`, `TASKS.md`,
`backend/api/routers/alerts.py`, `backend/api/routers/auth.py`, `backend/core/config.py`,
`backend/static/index.html`, `docs/FIXES_BACKLOG.md`, `docs/ROADMAP_STAGE96_104.md`,
`docs/ROLE_MATRIX.md`, `docs/UI_MIGRATION_MANIFEST.md`, `tests/test_auth_roadmap_gates.py`.

untracked: چهار `AUDIT_2026_PART*.md`، `docs/GlobalIntelligence_Roadmap_v2.2.md`،
`docs/ROADMAP_V22_WP00_WP01_REPORT.md`، `scripts/fix_alerts_router.py`، `scripts/fix_ui.py`،
دو spec قبلی `tests/e2e/{deeplink,pages}.spec.js` و شش تست جدید WP-04/WP-05/WP-بازبینی.

## 2. Runtime و سرویس‌ها (فقط‌خواندنی، بدون توقف هیچ سرویس مالک)

| سرویس | وضعیت |
|---|---|
| `gi_backend` | Up 3h (healthy) · `127.0.0.1:8000` |
| `gi_frontend` | Up 3h · `127.0.0.1:5173` |
| `gi_postgres` | Up 3h (healthy) · `127.0.0.1:15432` |
| `gi_staging_postgres` | Up 3h (healthy) · `127.0.0.1:15433` |
| `gi_n8n` | Up 3h · `127.0.0.1:5678` (n8n 2.42.6) |
| `gi_staging_backend` | Up 3h (healthy) · `127.0.0.1:8001` |

سرویس موقت خودِ agent (از نوبت WP-05، SQLite در `backups/roadmap_v22/e2e_wp05.db`)
روی `127.0.0.1:18100` برای smoke مرورگری بالا بود و در همین نوبت با کد جدید بازراه‌اندازی شد.
هیچ کانتینر/Volume/دیتابیس مالک متوقف یا تغییر داده نشد.

## 3. لاین PostgreSQL — باز ارزیابی بعد از WP-02

برای این نوبت یک کانتینر **موقت** `postgres:16-alpine` روی `127.0.0.1:15435` ساخته شد
(PG 16.15)، `alembic upgrade head` روی آن اجرا شد (**۵۴ جدول**، head `f0auth_users_accounts`)،
تست‌ها اجرا و در پایان کانتینر حذف شد. رمز موقت فقط در همان اجرا استفاده شد.

| مجموعه | نتیجه روی PG |
|---|---|
| `test_config_control_plane.py` + `test_config_revision_pin.py` + `test_source_preview_api.py` | **20 passed** (۴۶٫۲۵s) |
| `test_settings.py` + `test_doc_claims.py` + `test_permission_matrix_doc.py` + `test_auth_ui_contract.py` | **77 passed** (۸۸٫۷۸s) |

**نکتهٔ مهم برای لاین PG:** بدون `alembic upgrade head` همهٔ تست‌ها با
`UndefinedTable: relation "article_dispatches" does not exist` خطا می‌دهند؛ یعنی
لاین PG به migration وابسته است و `create_all` فقط در لاین SQLite انجام می‌شود
(همان قید مستند F-12). suite کامل PG در این نوبت اجرا نشد.

---

# WP-06 — Settings و Configuration Control Plane (نتیجه)

## 1. یافتهٔ اصلی: یک Control Plane کامل از قبل وجود داشت

هیچ Store موازی ساخته نشد. زنجیرهٔ موجود (F03.0) کامل بود:

| حلقه | پیاده‌سازی موجود |
|---|---|
| Definition | `backend/configuration/descriptors.py` — `FieldSpec` (type/required/choices/max_length/secret), `Descriptor`, `validate()` بدون I/O، `redact()` |
| Storage | `backend/database/models/configuration.py` — `ConfigurationInstance` + `ConfigurationRevision` (تاریخچهٔ افزودنی) |
| API | `backend/api/routers/configuration.py` — definitions, instances, revisions, validate, test, activate, rollback |
| Validation | `descriptors.validate` + `source_bot.security.validate_url` + `pick_adapter` رجیستری |
| Test | `backend/configuration/preview.py` — fetch/parse **بدون** ingest |
| Activation | `service.activate_revision` با `expected_revision` (optimistic lock) |
| Runtime consumer | `backend/configuration/runtime.py` → `source_bot.runner.run_source` (revision در `BotMetrics.config_revision` ثبت می‌شود) |
| Audit | `domains.audit.service.log_action` (قبلاً فقط activate/rollback) |
| Rollback | `service.rollback` — revision جدید، نه بازنویسی تاریخچه |

## 2. شکاف‌های واقعی که در این نوبت بسته شدند

1. **صفر رابط کاربری.** `grep -c "api/configuration" backend/static/index.html` = **0** بود؛
   پذیرش WP-06 («از UI») عملاً غیرممکن بود. حالا بخش «Configuration Control Plane» داخل
   صفحهٔ تنظیمات، کل چرخه را به همان API وصل می‌کند.
2. **گروه‌های بدون adapter نمایش داده نمی‌شدند.** بند ۱۲ WP-06 صریح است: برای integration
   فاقد adapter باید `NEEDS_ADAPTER` نمایش داده شود. اضافه شد:
   `Descriptor.adapter_state` (`ready` | `needs_adapter`), `creatable`,
   `NEEDS_ADAPTER_KINDS` برای `email`, `telegram`, `scheduling`, `ui_preferences`,
   `access_security` با یادداشت دلیل. تلاش برای ذخیرهٔ پیکربندی این kindها با خطای
   صریح `NeedsAdapter` (HTTP **409**) رد می‌شود و هیچ instance جعلی ساخته نمی‌شود.
3. **نشت مقدار secret در پاسخ GET.** `redact()` فقط فیلدهای `secret=True` را ماسک می‌کرد؛
   `endpoint_config.api_key_env` که validation آن را به‌عنوان «کلید واقعی به‌جای نام متغیر»
   رد می‌کند، از مسیر GET بازخوانی و افشا می‌شد. حالا اگر مقدار شبیه کلید باشد ماسک می‌شود.
   این باگ توسط تست جدید گرفته شد، نه با بازرسی چشمی.
4. **Audit ناقص.** فقط `activate`/`rollback` حسابرسی می‌شدند. حالا
   `configuration_create`, `configuration_revision`, `configuration_validate` (ok/failed),
   `configuration_test` (ok/failed/unsupported) هم ثبت می‌شوند؛ خطای audit گذار را نمی‌شکند.
5. **باگ رندر در صفحهٔ تنظیمات.** بخش «Alert Channels» بعد از `c.innerHTML=html` به رشته
   اضافه می‌شد و **هرگز رندر نمی‌شد**. ترتیب اصلاح شد.
6. **پیکربندی‌های بی‌مصرف‌کننده.** گروه‌هایی که مصرف‌کنندهٔ واقعی دارند صریحاً به همان
   مسیر موجود ارجاع داده شدند (AI Providers → `/api/settings/providers`،
   General/Processing → `/api/settings/app`، Archive/Retention → `/api/retention`)
   تا Store دومی ساخته نشود.

## 3. چرخهٔ Setting در UI (همان قرارداد بند ۲)

`Definition → Draft → Validate → Test (بدون ingest) → Activate → Runtime pin → Audit → Rollback`

- ورودی: kind (فقط `ready`)، slug یکتا، payload JSON.
- **Save Draft** هیچ اثری روی runtime ندارد (تست: `test_draft_does_not_change_runtime`).
- **Test** همان `preview_fetch` است: هیچ Document/Article نمی‌سازد
  (تست: `test_test_step_does_not_ingest`).
- **Activate** فقط از وضعیت `tested` و با `expected_revision` جاری.
- **Rollback** یک revision جدید می‌سازد (r3) و r1/r2 را `archived` می‌کند.
- Secretها در این مسیر write-only می‌مانند: descriptor فقط **نام** متغیر env را می‌پذیرد.

## 4. فایل‌های تغییر‌یافته در WP-06

| فایل | تغییر |
|---|---|
| `backend/configuration/errors.py` | `NeedsAdapter` (409) |
| `backend/configuration/descriptors.py` | `adapter_state`/`creatable`، `NEEDS_ADAPTER_KINDS`، `needs_adapter_definitions()`، ماسک `api_key_env` در `redact()` |
| `backend/configuration/service.py` | `_audit()` و ثبت audit برای create/revision/validate/test |
| `backend/static/index.html` | بخش Configuration Control Plane در صفحهٔ تنظیمات + ۷ action جدید (`cfgCreate`, `cfgOpen`, `cfgRevision`, `cfgValidate`, `cfgTest`, `cfgActivate`, `cfgRollback`) + اصلاح ترتیب رندر Alert Channels |
| `tests/test_config_control_plane.py` | **جدید** — ۱۰ تست |
| `tests/e2e/configuration.spec.js` | **جدید** — ۳ تست Playwright |

هیچ migration جدید لازم نشد: مدل‌های `ConfigurationInstance`/`ConfigurationRevision`
از قبل در migrationها هستند و تغییر این نوبت فقط descriptor/service/UI است.

## 5. تست‌ها و نتایج واقعی

| اجرا | نتیجه |
|---|---|
| `pytest tests/test_config_control_plane.py -q` (SQLite) | **10 passed** (۲٫۶s) |
| همان + `test_config_revision_pin.py` + `test_source_preview_api.py` | **20 passed** |
| همان سه فایل روی **PG 16.15** (بعد از `alembic upgrade head`) | **20 passed** (۴۶٫۲۵s) |
| `test_settings.py` + `test_doc_claims.py` + `test_permission_matrix_doc.py` + `test_auth_ui_contract.py` روی PG | **77 passed** (۸۸٫۷۸s) |
| `npx playwright test tests/e2e/configuration.spec.js` | **3 passed** |
| `… configuration.spec.js routes.spec.js` | **28 passed** (۲٫۲m) |
| `ruff check backend domains tests scripts source_bot` | ۰ خطا |
| `node --check` روی هر سه بلوک `<script>` | سالم |
| اسکن `data-action` بدون handler | خالی |

پوشش تست Playwright: رندر بخش پیکربندی + chip `NEEDS_ADAPTER`، جریان
Draft → Validate از UI، عدم نمایش دکمهٔ Activate پیش از Test، و نمایش نمونهٔ ساخته‌شده
با شمارهٔ نسخه.

## 6. محدودیت‌ها و مسدودها

- **Test/Activate از UI در مرورگر تا انتها اجرا نشد.** `preview_fetch` فقط adapter `rss`
  را پشتیبانی می‌کند و به شبکهٔ واقعی نیاز دارد؛ در محیط تست، اینترنت/فید پایدار نیست و
  ساختن یک endpoint محلی هم توسط سیاست SSRF (`connection_check`) رد می‌شود. چرخهٔ
  Validate → Test → Activate → Runtime pin → Rollback با شواهد واقعی در تست‌های API
  (SQLite + PG) پوشش داده شد؛ UI تا Validate و نمایش صحیح گذارهای مجاز تست شد.
- **suite کامل PG** در این نوبت اجرا نشد (زمان‌بر)؛ فقط برش هدفمند ۹۷ تست. عدد کامل
  تاریخی WP-02 (۱۸۱۴ passed) به این HEAD تعمیم داده نمی‌شود.
- **CI راه‌دور** همچنان `NOT_VERIFIED` (نیازمند push مالک).
- **SMTP:** Alias اصلاح‌شده دست‌نخورده ماند؛ هیچ ارسال واقعی انجام نشد
  (`BLOCKED_OWNER_CREDENTIAL_ROTATION` برای چرخش App Password).
- **Paid/Free-first:** `AI_PAID_ENABLED` روشن نشد، هیچ Provider پولی فعال و هیچ هزینه‌ای
  ایجاد نشد؛ Mock/Free-first دست‌نخورده است.
- گروه‌های `email`/`telegram`/`scheduling`/`ui_preferences`/`access_security` عمداً
  `NEEDS_ADAPTER` ماندند؛ ادعای پیکربندی قابل‌ذخیره برایشان ساخته نشد.

---

# WP-00 (نوبت WP-07) — ممیزی فقط‌خواندنی، ۱۴ نوامبر ۲۰۲۶

| سنجه | مقدار |
|---|---|
| root / branch / HEAD | `J:/Documents/GlobalIntelligence` · `step6a-analysis-dashboard` · `2d0e1bc` (+0 −0) |
| staged / modified / untracked | ۰ / **۱۴** / **۱۹** |
| نقشه‌راه | `docs/GlobalIntelligence_Roadmap_v2.2.md` خوانده شد (§۱۳ = WP-07) |
| سرویس‌های مالک | ۶ کانتینر Up و دست‌نخورده (backend 8000، frontend 5173، postgres 15432، staging 15433/8001، n8n 5678) |
| سرویس موقت agent | uvicorn روی `127.0.0.1:18100` (SQLite در `backups/roadmap_v22/e2e_wp05.db`) برای smoke مرورگری |

`.env` فقط به‌صورت حضور بررسی شد (هیچ مقداری خوانده/چاپ نشد):
`GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID` = SET · `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` = MISSING ·
`AI_PAID_ENABLED` = MISSING (یعنی Off) · `MOCK_MODE=false` · `AI_DEFAULT_PROVIDER=groq`.

---

# WP-07 — AI Provider/Model Catalog و Gateway واقعی (نتیجه: BLOCKED)

## 1. دارایی‌های موجود که حفظ شدند (بند ۱)

هیچ‌کدام بازنویسی نشد: `AIGateway` (retry/fallback/`_record_run`)، `registry` با ۱۰ adapter،
`free_policy` (fail-closed allowlist)، `budget` (reserve/settle)، `credentials_store`
(DB اولویت بر `.env` + نسخه‌گذاری کش)، provider adapters، `GET/POST /api/settings/providers`
و `POST /providers/{id}/test`.

## 2. ماتریس و شمارش (بند ۲ و ۳)

ماتریس کامل ۱۱ ستونی در `docs/WP07_PROVIDER_CATALOG_MATRIX.md` ثبت شد. خلاصهٔ شمارش:

| دسته | تعداد |
|---|---:|
| adapter module | ۱۰ |
| Provider ابری (بدون local/mock) | ۷ |
| Local Screening Runtime (kev/laya) | ۲ |
| Mock | ۱ |
| ردیف model catalog | ۷ (۱ active، ۶ disabled) |

## 3. یافتهٔ تعیین‌کننده: هیچ Provider قابل‌استفاده‌ای وجود ندارد

| Provider | اتصال | سیاست | نتیجهٔ واقعی Gateway |
|---|---|---|---|
| **groq** (تنها جفت active سیاست) | ❌ HTTP 403 `Access denied` | ✅ `openai/gpt-oss-20b` | `AIErrorKind.auth` (retryable=False) |
| gemini | ✅ 200، ۵۰ مدل، `gemini-3.5-flash` موجود | ❌ terms منطقه/داده | `model_not_allowed` قبل از HTTP |
| openrouter | ✅ 200، ۴۳۶ مدل | ❌ blanket `:free` | `model_not_allowed` |
| cloudflare | ⏸ تست‌نشده | ❌ eligibility تأییدنشده | `model_not_allowed` |
| openai / anthropic / openai_compatible | missing/⏸ | ❌ | `model_not_allowed` |

پس **معیار پذیرش WP-07 (Provider واقعی + Task واقعی + Usage ثبت‌شده) قابل تحقق نبود**
و به‌درستی با mock یا Provider پولی پوشانده نشد. هیچ درخواست inference موفقی هزینه‌ای
ایجاد نکرد (Groq با 403 و بقیه پیش از HTTP رد شدند).

## 4. اقدام‌های مالک (بدون درخواست Secret در گفتگو)

1. **Groq:** رفع دسترسی شبکه/Region به `api.groq.com` یا چرخش کلید در کنسول — تنها
   Provider مجاز سیاست است، پس کل AI واقعی متوقف است.
2. **Gemini:** تصمیم سیاستی دربارهٔ شرایط EEA/CH/UK و unpaid data-use (کلید و مدل سالم‌اند).
3. **OpenRouter:** refresh کاتالوگ و تصمیم روی یک جفت مشخص (نه blanket `:free`).
4. **Cloudflare:** تأیید eligibility مدل رایگان در Workers Free.

## 5. شکاف شناسایی‌شده و اعمال‌نشده (WP-07.1)

بند ۸ («Provider جدید Draft؛ فعال‌سازی بدون تست ممنوع») برقرار نیست:
`POST /providers` با `enabled=True` می‌سازد و `PUT {enabled:true}` شاهدی از تست نمی‌خواهد.

اعمال «Draft-first + گیت تست» در همین نوبت **عمداً برگشت داده شد**، چون به تناقض طراحی
می‌خورد: `test_provider` برای Provider غیرفعال 422 می‌دهد و
`resolve_provider_credential` فقط ردیف‌های `enabled=True` را resolve می‌کند؛ یعنی Draft
هرگز قابل تست نمی‌شد. اعمال درست آن یک زیرمرحلهٔ مستقل است
(مسیر تست برای Draft + ثبت شاهد در همان گذار). تغییر اعمال‌شده با `git checkout` به
وضعیت قبل برگشت و `tests/test_fullstack_integration.py` + `tests/test_settings.py`
دوباره **75 passed** شد تا هیچ اثر نیمه‌کاره باقی نماند.

## 6. تغییرات این نوبت

| فایل | نوع |
|---|---|
| `tests/test_provider_catalog_matrix.py` | **جدید** — ۶ تست نگهبان آفلاین |
| `docs/WP07_PROVIDER_CATALOG_MATRIX.md` | **جدید** — ماتریس اندازه‌گیری‌شده + شواهد |
| `docs/ROADMAP_V22_WP00_WP01_REPORT.md` | همین بخش |

هیچ کد محصولی تغییر نکرد؛ هیچ Secret چاپ/ذخیره نشد؛ `AI_PAID_ENABLED` روشن نشد؛
هیچ ارسال واقعی انجام نشد.

## 7. تست‌ها و نتایج

| اجرا | نتیجه |
|---|---|
| `pytest tests/test_provider_catalog_matrix.py -q` | **6 passed** |
| `pytest tests/test_fullstack_integration.py tests/test_settings.py -q` (بعد از برگشت تغییر) | **75 passed** |
| `pytest tests/test_ai_chat.py tests/test_providers_http.py -q` (در همان اجرای قبل از برگشت) | بخشی از **102 passed** |
| `ruff check backend domains tests scripts source_bot` | ۰ خطا |

## 8. محدودیت‌ها

- `usage_recorded` برای هیچ Providerی قابل اثبات نبود، چون هیچ فراخوانی موفقی انجام نشد؛
  عدد usage ساختگی ثبت نشد.
- Cloudflare به‌دلیل نیاز به درخواست account-scoped و سیاست disabled تست نشد (`NOT_TESTED`).
- لاین PG و suite کامل در این نوبت اجرا نشد (هیچ کد محصولی تغییر نکرد).

---

# WP-07.1 — Provider Draft-first و گیت تست اتصال (رفع شکاف ثبت‌شده)

## 1. مشکل و ریشهٔ آن

بند ۸ WP-07 می‌خواست «Provider جدید ابتدا Draft؛ فعال‌سازی بدون تست و تأیید سیاست ممنوع».
کد قبلی: `POST /providers` با `enabled=True` می‌ساخت، مدل پیش‌فرض را مستقیم `enabled=True`
می‌گذاشت، `PUT {enabled:true}` هیچ شاهدی نمی‌خواست، و `test` روی Provider غیرفعال **422** بود.

deadlock قبلی از همین‌جا می‌آمد: `test` فقط برای ردیف فعال کار می‌کرد و
`resolve_provider_credential` هم فقط ردیف‌های `enabled=True` را resolve می‌کرد؛
پس Draft هرگز نه تست‌شدنی بود نه فعال‌شدنی.

## 2. تغییرات (بدون Store جدید، بدون مسیر دوم)

| فایل | تغییر |
|---|---|
| `backend/ai/credentials_store.py` | `resolve_provider_credential(..., include_disabled=False)`؛ مسیریابی عادی دقیقاً مثل قبل فقط ردیف‌های فعال را می‌بیند |
| `backend/ai/providers/registry.py` | `build_provider_with_store(..., include_disabled=False)` — فقط pass-through همین گزینه |
| `backend/ai/gateway/gateway.py` | `generate(..., include_disabled_provider=False)`؛ کلید کش Provider با پسوند `|draft` جدا می‌شود تا کش Draft و فعال قاطی نشود |
| `backend/api/routers/settings.py` | ساخت همیشه Draft؛ مدل پیش‌فرض Draft؛ `PUT {enabled:true}` بدون `last_test_status=="ok"` → **422**؛ تست اتصال برای Draft مجاز و در صورت موفقیت **همان درخواست** Provider را فعال می‌کند؛ چرخش کلید شاهد تست را باطل و Provider را به Draft برمی‌گرداند؛ audit ساخت با `draft: true` |
| `backend/static/index.html` | دکمهٔ «تست» فقط به `key_set` وابسته است (نه `enabled`) و متن راهنما به گذار جدید اصلاح شد |

نکات طراحی:

- **سیاست دور زده نمی‌شود**: `include_disabled_provider` فقط resolve اعتبارنامه را
  باز می‌کند؛ `check_provider` و `check_model` (Free-Only) در همان حلقه و پیش از هر
  HTTP مثل قبل اجرا می‌شوند (تست `test_policy_is_enforced_on_draft_test_path`).
- گذار «Draft → فعال» یک گذار با شاهد است: `last_test_status="ok"` و `enabled=True`
  در همان درخواست تست موفق نوشته می‌شوند؛ هیچ endpoint «فعال‌سازی بدون شاهد» اضافه نشد.
- کلید عوض شود → شاهد قبلی بی‌اعتبار است؛ پس `last_test_status=None` و `enabled=False`.

## 3. تست‌ها

| فایل | محتوا |
|---|---|
| `tests/test_provider_lifecycle.py` (جدید، ۶ تست) | Draft بودن ساخت (حتی با `enabled:true` در ورودی)، Draft بودن مدل پیش‌فرض، 422 برای فعال‌سازی بدون تست، promotion با تست موفق (دقیقاً ۱ تلاش HTTP)، اجرای سیاست روی مسیر Draft (۰ درخواست HTTP)، بازگشت به Draft پس از چرخش کلید |
| `tests/test_settings.py` | helper `_mark_tested` برای تست‌هایی که موضوعشان مدل/مصرف‌کننده است (نه گذار فعال‌سازی) |
| `tests/test_fullstack_integration.py` | helper `_promote_provider` برای تست‌های Budget/Quota؛ ادعاهای اصلی دست‌نخورده |

هیچ تست حذف/ضعیف/Skip نشد؛ در دو فایل بالا فقط **پیش‌نیاز جدید دامنه** (Provider فعال)
به‌صورت صریح آماده می‌شود و مسیر واقعی promotion در فایل اختصاصی از طریق endpoint
تست اتصال (با `httpx.MockTransport`) سنجیده می‌شود.

## 4. نتایج

| اجرا | نتیجه |
|---|---|
| `pytest tests/test_provider_lifecycle.py -q` (SQLite) | **6 passed** |
| `pytest` روی ۸ فایل مرتبط (lifecycle، catalog matrix، settings، fullstack، ai_chat، admin_gate، config_control_plane، doc_claims) — SQLite | **142 passed** |
| `ruff check backend domains tests scripts source_bot` | ۰ خطا |
| `git diff --check` | پاک |
| **همان ۸ فایل روی PostgreSQL 16.15** (کانتینر موقت `gi_pg_wp071`:15436، `alembic upgrade head` → ۵۴ جدول) | **142 passed / 0 failed** (108 + 34، بدون skip) |
| **کل suite روی PostgreSQL 16.15** (`gi_pg_full`:15437، بخش ۴.۲) | **1909 passed / 0 failed / 0 skipped** در ۲۴:۲۴ |
| **چرخهٔ مهاجرت** `upgrade → downgrade base → upgrade` (بخش ۴.۳) | ۳ گام، همه `EXIT=0` · ۵۴ → ۱ → ۵۴ جدول · ۱۶ passed smoke |
| `tests/test_permission_matrix_doc.py` روی همان PG | ۱۰ passed |

## 4.5. بازبینی بصری UI (WP-07.1) — ۱۴ نوامبر ۲۰۲۶

سرویس موقت `127.0.0.1:18100` با SQLite `backups/roadmap_v22/e2e_wp05.db` و `MOCK_MODE=true`،
کاربر `e2e`/`E2eTestPassword123` (نقش admin). صفحهٔ Providers باز شد؛ Draft row «UI-Draft-Final»
(groq) با دکمهٔ «تست» فعال و checkbox «فعال» غیرفعال (Draft) نمایش داده شد.

<|constrain|> شاهد | فایل/نتیجه |
|---|---|
| Draft row + test button فعال | `docs/screenshots/wp071-providers-draft.png` |
| فرم افزودن Provider با select «فعال» غیرفعال | `docs/screenshots/wp071-create-form-draft-final.png` |
| کلیک «تست» با `window.confirm` stub → true | toast «تست ناموفق: mock response (check MOCK_MODE)»؛ `last_test_status` غیرفعال؛ timestamp ۱۶:۲۲؛ Draft باقی ماند (checkbox checked=false) |
| شاهد مسیر شکست | `docs/screenshots/wp071-draft-test-failed.png` |
| شاهد UI fix (فرم) | `docs/screenshots/wp071-create-form-draft-final.png` |

**مسیر موفق (Promotion) در مرورگر نمایش داده نشد**، چون Provider قابل‌دسترس/مجازی
در محیط نیست (groq 403، gemini/openrouter/cloudflare policy-disabled، openai_compatible
policy-disabled و base_url محدود به openai_compatible). شاهد خودکار مسیر موفق:
`tests/test_provider_lifecycle.py::test_successful_connectivity_test_promotes_draft` (۶ passed)،
که با `httpx.MockTransport` دقیقاً ۱ درخواست HTTP می‌فرستد و Provider را فعال می‌کند.

**UI fix (فرم «فعال»):** فیلد «فعال» در فرم ایجاد Provider با برچسب
«فعال (Draft؛ فقط با تست موفق فعال می‌شود)» و `disabled` نمایش داده می‌شود؛ در فرم ویرایش
«فعال» بدون غیرفعال‌سازی. این تغییر در مرورگر با reload تأیید شد (اسکرین‌شات فرم).

**محدودیت:** native `confirm()` در مرورگر برای کلیک «تست» hang می‌کرد؛ با `window.confirm = () => true`
stub شد. هیچ dialog واقعی (لغو) در این نوبت بررسی نشد.

## 5. آنچه تغییر نکرد و عمداً انجام نشد

- هیچ درخواست شبکه‌ای/هزینه‌ای در تست‌ها نیست؛ `httpx.MockTransport` جای transport را می‌گیرد.
- سیاست Free، allowlist، Budget و شمارش Provider دست‌نخورده‌اند.
- وضعیت AI واقعی همچنان `BLOCKED` است (Groq 403 / سیاست Gemini)؛ WP-07.1 فقط
  چرخهٔ عمر Provider را درست می‌کند و موانع بیرونی را حل نمی‌کند.
- UI تغییر یافته در مرورگر **بازبینی چشمی شد** (پایین: بخش «بازبینی بصری UI»)؛ Playwright در این نوبت اجرا نشد (تغییر UI فقط شرط فعال‌بودن دکمه و یک متن/غیرفعال‌سازی فیلد «فعال» است).

### 4.1. جزئیات لاین PostgreSQL (۱۴ نوامبر ۲۰۲۶)

| مورد | مقدار |
|---|---|
| تصویر | `postgres:16`, **PostgreSQL 16.15** (Debian) |
| پورت/کانتینر | `127.0.0.1:15436` · `gi_pg_wp071` (موقت؛ در پایان حذف شد) |
| مهاجرت | `alembic upgrade head` موفق → **۵۴ جدول** در `public` |
| اجرای اول (۷ فایل) | `test_provider_lifecycle, test_provider_catalog_matrix, test_settings, test_fullstack_integration, test_ai_chat, test_config_control_plane, test_doc_claims` → **108 passed** در ۹۱.۱۳s |
| اجرای دوم | `test_admin_gate_allow_deny, test_permission_matrix_doc` → **44 passed** در ۱۲.۹۱s (۳۴ + ۱۰) |
| جمع همان ۸ فایل SQLite | ۱۰۸ + ۳۴ = **۱۴۲** ← دقیقاً برابر شمار SQLite؛ هیچ skip و هیچ تفاوت پلتفرمی |
| کانتینر مالک | دست‌نخورده (`gi_backend`, `gi_frontend`, `gi_postgres`, `gi_staging_*`, `gi_n8n`) |

### 4.2. suite کامل روی PostgreSQL (۱۴ نوامبر ۲۰۲۶)

| مورد | مقدار |
|---|---|
| کانتینر | `gi_pg_full` (موقت) روی `127.0.0.1:15437`، تصویر `postgres:16` → **PostgreSQL 16.15** |
| مهاجرت | `DATABASE_URL=... python -m alembic upgrade head` → موفق، **۵۴ جدول** در `public` |
| فرمان | `DATABASE_URL=postgresql+psycopg://... python -m pytest tests -q -p no:cacheprovider` |
| بازه | `START 15:28:31` → `END 15:53:19` (UTC) |
| نتیجه | **1909 passed / 0 failed / 0 error / 0 skipped** در **1464.25s (24:24)**، `EXIT=0` |
| مقایسه با اندازه‌گیری قبلی PG | 18.09.2026: 1814 passed، 923.96s (HEAD `ebe1292`) → **+۹۵ تست** (بستهٔ WP-06/WP-07/WP-07.1 و تست‌های ادعاها) |
| پس از اجرا | کانتینر `docker rm -f` شد؛ کانتینرهای مالک دست‌نخورده؛ هیچ Volume/داده‌ای حذف نشد |

این اجرا کل suite را پوشش می‌دهد (نه فقط فایل‌های WP-07)، پس ادعای «PG lane سبز» دیگر به
اندازه‌گیری قبلی متکی نیست. چرخهٔ کامل مهاجرت در بخش ۴.۳ آمد؛ Playwright همچنان در این
نوبت اجرا نشده است (`NOT_VERIFIED`).

### 4.3. چرخهٔ کامل مهاجرت روی PostgreSQL — `upgrade → downgrade base → upgrade`

| مورد | مقدار |
|---|---|
| کانتینر | `gi_pg_mig` (موقت) روی `127.0.0.1:15438`، `postgres:16` → **PostgreSQL 16.15** (DB `gi_mig`) |
| گام ۱ — `alembic upgrade head` | `EXIT=0` · `current` = `f0auth_users_accounts (head)` · **۵۴ جدول** در `public` |
| گام ۲ — `alembic downgrade base` | `EXIT=0` · بدون error/traceback در لاگ · `current` خالی · فقط **`alembic_version`** باقی ماند (۵۴ → ۱ جدول) |
| گام ۳ — `alembic upgrade head` | `EXIT=0` · بدون error/traceback · `current` = `f0auth_users_accounts (head)` · **۵۴ جدول** و **۱۸۷ index** |
| یکتایی head | `alembic heads` → تنها یک head: `f0auth_users_accounts` (بدون branch چندسری) |
| smoke پس از upgrade دوم | `pytest tests/test_provider_lifecycle.py tests/test_config_control_plane.py` → **16 passed** در ۸.۸۶s (یعنی schema دوباره‌ساخته‌شده واقعاً کار می‌کند، نه فقط شمار جدول) |
| پس از اجرا | کانتینر `docker rm -f` شد؛ کانتینرهای مالک دست‌نخورده؛ هیچ Volume/دادهٔ مالک لمس نشد |

نتیجه: این مورد از «اجرا نشده» در AGENTS.md به **تأییدشده** ارتقا یافت — downgrade بدون
خطا تا base می‌رود و upgrade دوم همان schema و همان head را بازمی‌گرداند.


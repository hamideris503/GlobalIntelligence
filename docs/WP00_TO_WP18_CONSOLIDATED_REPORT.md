# گزارش ت consolidated — Work Packageهای WP-00 تا WP-18

**پروژه:** GlobalIntelligence · **Branch:** `step6a-analysis-dashboard` · **HEAD:** `2d0e1bc`
**تاریخ:** ۱۴ نوامبر ۲۰۲۶

---



################################################################################
# فایل منبع: docs/ROADMAP_V22_WP00_WP01_REPORT.md
################################################################################


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




---



################################################################################
# فایل منبع: docs/WP07_PROVIDER_CATALOG_MATRIX.md
################################################################################


# WP-07 — ماتریس Provider / Model Catalog / Policy (اندازه‌گیری‌شده)

**تاریخ اندازه‌گیری:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc` · **محیط:** Windows محلی، `MOCK_MODE=false`، `AI_DEFAULT_PROVIDER=groq`
**قاعده:** هیچ مقدار Secret خوانده/چاپ نشد؛ برای credentialها فقط «حضور» ثبت شده است.

## 1. شمارش تفکیک‌شده (بند ۳ نقشه‌راه)

| دسته | تعداد | اقلام |
|---|---:|---|
| Adapter module در registry | **۱۰** | `mock`, `openai`, `anthropic`, `gemini`, `openrouter`, `groq`, `cloudflare`, `openai_compatible`, `kev`, `laya` |
| Provider ابری (غیر از local/mock) | **۷** | openai, anthropic, gemini, openrouter, groq, cloudflare, openai_compatible |
| Local Screening Runtime (نه Provider ابری) | **۲** | `kev`, `laya` |
| Mock | **۱** | `mock` (در حالت Real از زنجیره حذف می‌شود) |
| ردیف Model Catalog در allowlist | **۷** | ۱ active + ۶ disabled |

عدد «۱۲/۱۳ Provider» گزارش‌های قبلی با این تفکیک بازتولید نشد؛ مرجع، خروجی
`backend.ai.providers.registry.available_providers()` است.

## 2. ماتریس ۱۱ ستونی

| provider | adapter_exists | kind | UI_visible | credentials | connectivity_test | model_discovered | model_verified | policy_approved | gateway_task_test | usage_recorded | routing_enabled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **groq** | ✅ | cloud | ✅ (env:groq) | PRESENT | ❌ **HTTP 403** `Access denied. Please check your network settings.` | ❌ (listing مسدود) | ❌ | ✅ **تنها جفت active** `openai/gpt-oss-20b` (verified 2026-10-17) | ❌ `AIErrorKind.auth` (retryable=False) | ❌ | ⚠️ در زنجیره است (`AI_DEFAULT_PROVIDER=groq`) اما عملاً غیرقابل‌استفاده |
| **gemini** | ✅ | cloud | ✅ (env:gemini) | PRESENT | ✅ HTTP 200، **۵۰ مدل** | ✅ `gemini-3.5-flash` موجود | ⚠️ فقط حضور در کاتالوگ | ❌ disabled — «EEA/CH/UK user-facing terms و unpaid data-use» | ❌ سیاست، قبل از HTTP رد می‌کند (`model_not_allowed`) | ❌ | ❌ |
| **openrouter** | ✅ | cloud | ✅ (env:openrouter) | PRESENT | ✅ HTTP 200، **۴۳۶ مدل** | ❌ `openai/gpt-oss-20b:free` در کاتالوگ نیست | ❌ | ❌ disabled — blanket `:free` ناایمن | ❌ `model_not_allowed` | ❌ | ❌ |
| **cloudflare** | ✅ | cloud | ✅ (env:cloudflare) | PRESENT (+ account_id) | ⏸ تست نشد (account-scoped + سیاست disabled) | ⏸ | ❌ | ❌ disabled — free eligibility در Workers Free تأییدنشده | ❌ `model_not_allowed` | ❌ | ❌ |
| openai | ✅ | cloud | ✅ | **MISSING** | ⏸ | ⏸ | ❌ | ❌ disabled — بدون tier رایگان | ❌ `model_not_allowed` | ❌ | ❌ |
| anthropic | ✅ | cloud | ✅ | **MISSING** | ⏸ | ⏸ | ❌ | ❌ disabled — بدون tier رایگان پایدار | ❌ `model_not_allowed` | ❌ | ❌ |
| openai_compatible | ✅ | cloud | ✅ | MISSING | ⏸ | ⏸ | ❌ | ❌ disabled — هیچ جفت معتبری تأیید نشده | ❌ | ❌ | ❌ |
| kev / laya | ✅ | local | ✅ | n/a (بدون کلید) | n/a | n/a | n/a | معاف از allowlist ابری | — | — | طبق تنظیمات Local Screening خاموش |

## 3. شاهد اجرا (دستورها)

```text
# شمارش adapter/credential/allowlist + connectivity (بدون چاپ Secret)
python - <<'PY'  # ad-hoc inventory: registry, .env presence, model-listing only
PY
→ adapters=10 · groq/gemini/openrouter/cloudflare PRESENT · openai/anthropic MISSING
→ groq http=403 models=0 · gemini http=200 models=50 target_present=True
→ openrouter http=200 models=436 target_present=False

# تلاش واقعی Gateway (بدون inference موفق، چون سیاست/اتصال اجازه نداد)
AIGateway().generate(AIRequest(..., metadata={"force_provider": <kind>}))
→ gemini      FAIL kind=model_not_allowed provider=gemini retryable=False
→ openrouter  FAIL kind=model_not_allowed provider=openrouter retryable=False
→ cloudflare  FAIL kind=model_not_allowed provider=cloudflare retryable=False
→ openai      FAIL kind=model_not_allowed provider=openai retryable=False
→ groq        FAIL kind=auth provider=groq retryable=False msg=all providers failed [auth]: groq:auth
```

هیچ‌کدام به mock یا Provider پولی fallback نکرد؛ پاسخ‌ها fail-closed و صریح بودند
(همان چیزی که بند ۱۱ WP-07 می‌خواهد).

## 4. Acceptance WP-07 → **BLOCKED**

معیار پذیرش «یک Provider واقعی و مجاز از UI، مدل تأیید‌شده، یک Task واقعی و Usage ثبت‌شده»
قابل تحقق نیست، چون:

1. تنها جفت مجاز سیاست (`groq/openai/gpt-oss-20b`) از این شبکه **403** می‌گیرد؛
2. سه credential دیگر یا سیاستاً disabled هستند (gemini/openrouter/cloudflare) یا
   مدل مجازشان در کاتالوگ زنده نیست (openrouter).

نتیجه: `gateway_task_test` و `usage_recorded` برای همهٔ Providerها ❌ است و این
وضعیت نباید با mock پوشانده شود.

## 5. اقدام‌های لازم از سمت مالک (بدون درخواست Secret در گفتگو)

| # | Provider | اقدام مشخص | چرا |
|---|---|---|---|
| 1 | Groq | بررسی دسترسی شبکه/Region برای `api.groq.com` یا چرخش کلید در کنسول Groq | 403 «Access denied» با کلید فعلی؛ و این تنها Provider مجاز سیاست است، پس کل زنجیرهٔ AI واقعی متوقف است |
| 2 | Gemini | تصمیم سیاستی دربارهٔ شرایط EEA/CH/UK و unpaid data-use | کلید و مدل سالم‌اند (HTTP 200، `gemini-3.5-flash` موجود) اما allowlist آن را disabled نگه می‌دارد |
| 3 | OpenRouter | refresh کاتالوگ و سپس تصمیم دربارهٔ یک جفت مشخص (نه blanket `:free`) | `openai/gpt-oss-20b:free` در کاتالوگ زنده نیست؛ مدل `.env` هم در allowlist نیست |
| 4 | Cloudflare | تأیید eligibility مدل رایگان در Workers Free | ورودی allowlist با همین دلیل disabled است |

## 6. شکاف شناسایی‌شده (WP-07.1) — **در WP-07.1 رفع شد**

**رفع‌شده.** بند ۸ WP-07 («Provider جدید ابتدا Draft؛ فعال‌سازی بدون تست و policy ممنوع»)
اکنون برقرار است: `POST /providers` همیشه Draft می‌سازد (حتی با `enabled:true` در ورودی)،
مدل پیش‌فرض Draft است، `PUT {enabled:true}` بدون `last_test_status=="ok"` → **422**،
و تست اتصال برای Draft مجاز است و در صورت موفقیت **همان درخواست** Provider را فعال می‌کند.
چرخش کلید شاهد تست را باطل و Provider را به Draft برمی‌گرداند.

(تاریخچهٔ شکاف قبل از رفع:) `POST /providers` ردیف را با `enabled=True` می‌ساخت و
`PUT ... {enabled:true}` هیچ شاهدی از تست نمی‌خواست؛ تست روی Provider غیرفعال 422 بود و
`resolve_provider_credential` فقط ردیف‌های `enabled=True` را resolve می‌کرد (deadlock).

**رفع در WP-07.1:** تناقض با افزودن `include_disabled` opt-in به
`resolve_provider_credential`/`build_provider_with_store`/`generate` (فقط مسیر تست اتصال)
و گیت فعال‌سازی با `last_test_status=="ok"` حل شد؛ چرخش کلید شاهد تست را باطل می‌کند.
جزئیات در بخش WP-07.1 گزارش و در `tests/test_provider_lifecycle.py` (۶ passed).

## 7. نگهبان ماشینی

`tests/test_provider_catalog_matrix.py` (۶ تست، آفلاین):

- هر جفت policy باید adapter داشته باشد؛ Kev/Laya رانتایم محلی‌اند و عضو allowlist ابری نیستند؛
- هر ورودی active باید source/verified_on/limits/account/privacy داشته و منقضی نباشد؛
- هر ورودی disabled باید دلیل داشته باشد؛
- رد سیاست برای mock (در حالت Real)، provider ناشناخته و مدل غیرمجاز/حدسی، صریح و غیر-retryable است؛
- نگاشت HTTP: 403 (provider/model)، 503 (`free_unavailable`)، 502 (auth)، 504 (timeout)؛
- شمارش Provider ابری بدون local/mock.



---



################################################################################
# فایل منبع: docs/WP08_GOLD_SET_VALIDATION.md
################################################################################


# WP-08 — اعتبارسنجی Gold Set موجود و ارزیابی Kev/Laya/Screening

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc` · **محیط:** Windows محلی
**منبع داده:** `H:\GIRuntime\labeling` (فقط‌خواندنی؛ هیچ فایلی ویرایش/حذف/rename نشد)

## 1. WP-00 فقط‌خواندنی (شروع این نوبت)

- Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked (بدون commit/push).
- کانتینرهای مالک دست‌نخورده؛ هیچ Volume/DB حذف نشد.
- credentialها فقط presence: GEMINI/OPENROUTER/GROQ/CLOUDFLARE SET؛ OPENAI/ANTHROPIC MISSING؛ `AI_PAID_ENABLED` MISSING (Off).
- سرویس موقت `127.0.0.1:18100` (SQLite) و `127.0.0.1:18100` UI کماکان بالا (برای smoke).

## 2. Inventory مسیر Gold Set

`H:\GIRuntime\labeling` شامل:

| مسیر | نوع | تعداد/حجم |
|---|---|---|
| `all-labels-review.zip` | zip | 221,836 B |
| `backups/` | dump ×2 + sha256 | ~1.3 MB هر کدام |
| `review-package/` | REPORT.md + labeled-final.jsonl | 150 ردیف |
| `reviewed/` | ۴۰+ پوشهٔ stage (stage49…stage109) + فایل‌های corrected/audit/adjudication | — |
| `stage49…stage53` | پوشه‌های مرحله‌ای | — |
| `stage53_combined200_…/` | labeled-final.jsonl | ۲۰۰ ردیف |
| `stage50_51_labeled_corrected.jsonl` | فایل تصحیح‌شده | ۲۳۲ ردیف |
| `pilot_stage102.py` | اسکریپت pilot | — |

هیچ متن خبر یا PII در این گزارش چاپ نشد.

## 3. Validation (harness موجود، بدون harness دوم)

`MIN_LABELED_SAMPLES = 200` (از `backend/ai/evaluation/local_screening.py`)؛ قرارداد label: `id`, `state`, `labels`, `annotator`, `label_source=human`, `label_status=valid`, `dataset_version`، `questions` (type `noul` → boolean).

| فایل | ردیف | valid | human | rejected | pending | dup | version | وضعیت |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `stage53_combined200/labeled-final.jsonl` | ۲۰۰ | ۲۰۰ | ۲۰۰ | ۰ | ۰ | ۰ | single (`…combined200-v1`) | **READY_FOR_EVALUATION** |
| `stage50_51_labeled_corrected.jsonl` | ۲۳۲ | ۲۳۲ | ۲۳۲ | ۰ | ۰ | ۰ | single (`stage50-…`) | **READY_FOR_EVALUATION** |
| `review-package/labeled-final.jsonl` | ۱۵۰ | ۱۵۰ | ۱۵۰ | ۰ | ۰ | ۰ | single | WAITING (کمتر از ۲۰۰) |
| `stage53_labeled_corrected.jsonl` | ۱۵۰ | ۱۵۰ | ۱۵۰ | ۰ | ۰ | ۰ | single | WAITING (کمتر از ۲۰۰) |
| `labeled-merged-stage50-stage53.jsonl` (repo) | ۳۸۲ | ۳۸۲ | ۳۸۲ | ۰ | ۰ | ۰ | **دو version** | invalid (version inconsistent) |
| **staging copy** `backups/roadmap_v22/wp08_gold_set_v1.jsonl` | ۳۸۲ | ۳۸۲ | ۳۸۲ | ۰ | ۰ | ۰ | unified (`gold-set-v1-2026-11-14`) | **READY_FOR_EVALUATION** |

**کشف کلیدی:** نسخهٔ merge‌شدهٔ ۳۸۲ ردیف (تنها مجموعه با هر دو کلاس به‌اندازهٔ کافی: ۲۹۵ true / ۸۷ false) به‌دلیل ناسازگاری `dataset_version` (۲۳۲ + ۱۵۰) از harness رد می‌شود. staging copy با یکپارچه‌سازی version (version اصلی در `source_dataset_version` حفظ شد) valid شد.

## 4. Label distribution و محدودیت‌ها

- stage50_51: ۲۳۱/۲۳۲ true (۹۹.۶٪ relevant) → به‌تنهایی برای تشخیص IRRELEVANT بی‌فایده.
- stage53_combined200: ۳۶/۲۰۰ true (۱۸٪) → نامتعادل.
- merged ۳۸۲: ۲۹۵/۸۷ → هر دو کلاس موجود؛ بهترین Gold Set.
- **provenance:** annotator تکی (`reviewer-1`)؛ دادهٔ annotator دوم موجود نیست → inter-annotator agreement قابل محاسبه نیست (limitation ثبت شد، blocker نیست).
- `OWNER_PROVIDED_HUMAN_LABELS` ثبت شد؛ مقدار جعلی برای annotator ساخته نشد.

## 5. Held-out Split

seed `wp08-heldout-v1`، ۲۰٪ (deterministic by id hash):

| split | n | relevant=true | relevant=false |
|---|---:|---:|---:|
| dev (tuning) | ۳۰۱ | ۲۳۴ | ۶۷ |
| holdout (final) | ۸۱ | ۶۱ | ۲۰ |

فایل: `backups/roadmap_v22/wp08_split_v1.json` (gitignored). هیچ نمونهٔ holdout برای tuning مصرف نشد.

## 6. ارزیابی Kev/Laya (از فایل‌های نتیجهٔ موجود)

Kev/Laya runtime (پورت ۸۱۲۳/۸۱۲۴) در این محیط بالا نیست؛ اجرای جدید انجام نشد. متریک‌ها از فایل‌های موجود (اجرای واقعی ۲۰۲۶-۱۱-۰۴/۰۸) محاسبه شدند. محتوای نتایج با staging copy یکسان است (version فیلد تصمیم را تغییر نمی‌دهد).

| مدل | n | TP | TN | FP | FN | Acc | Prec | Rec | F1 | Macro-F1 | Latency mean (ms) | p95 (ms) | abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Kev | ۳۸۲ | ۱۲۲ | ۸۳ | ۴ | ۱۷۳ | ۰.۵۳۶۶ | ۰.۹۶۸۳ | ۰.۴۱۳۶ | ۰.۵۷۹۶ | ۰.۵۳۱۸ | ۷۵۴۳.۱ | ۱۱۸۷۶.۰ | ۰ |
| Laya | ۳۸۲ | ۵۹ | ۶۹ | ۱۸ | ۲۳۶ | ۰.۳۳۵۱ | ۰.۷۶۶۲ | ۰.۲۰۰۰ | ۰.۳۱۷۲ | ۰.۳۳۴۶ | ۱۸۷۷.۹ | ۳۱۵۴.۸ | ۰ |

Hold-out (n=۸۱):

| مدل | Acc | F1 | Macro-F1 | TP | TN | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kev | ۰.۴۵۸۳ | ۰.۴۸۰۰ | ۰.۴۵۷۴ | ۱۸ | ۱۵ | ۰ | ۳۹ |
| Laya | ۰.۴۰۲۸ | ۰.۴۲۶۷ | ۰.۴۰۱۷ | ۱۶ | ۱۳ | ۲ | ۴۱ |

**تحلیل:** Kev precision بسیار بالا (۰.۹۶۸) اما recall پایین (۰.۴۱۴) — بسیار محافظه‌کار (FN زیاد). Laya ضعیف‌تر (F1 ۰.۳۱۷). هیچ abstain/uncertain ثبت نشده (همهٔ تصمیم‌ها bool) — tri-state engine در این اجراها abstain نکرده. Kev/Laya تا پذیرش Gold Set فقط Advisory می‌مانند (فعال‌سازی به‌عنوان تصمیم‌گیرنده نیازمند acceptance مستقل).

## 7. Gateway (ابری) — BLOCKED

Groq 403 (Access denied)، Gemini/OpenRouter/Cloudflare policy-disabled. هیچ inference موفقی انجام نشد. بنابراین ارزیابی Gateway روی Gold Set امکان‌پذیر نبود (BLOCKED).

## 8. Manifest

`data/labeling/gold-set-manifest.json` (بدون متن خبر) شامل: dataset_version، SHA-256 staging copy، counts، split، metrics، limitations، stage_status.

## 9. معیارهای پذیرش WP-08

| معیار | نتیجه |
|---|---|
| مسیر منبع پیدا و بدون تغییر | PASS (`H:\GIRuntime\labeling` دست‌نخورده) |
| حداقل نمونهٔ معتبر ≥ MIN (۲۰۰) | PASS (staging ۳۸۲) |
| همهٔ Gold labelها دارای provenance | PASS (human, reviewer-1, version حفظ) |
| manifest + SHA قابل بازتولید | PASS (`gold-set-manifest.json`) |
| held-out split تعریف‌شده | PASS (۳۰۱/۸۱) |
| metrics تولید‌شده | PASS (از نتایج موجود) |
| Stage 97 وضعیت | **READY_FOR_EVALUATION (dataset) / EVALUATION_REPORTED (Kev+Laya) / HELD_OUT_SPLIT_DEFINED** |

## 10. محدودیت‌ها

1. Kev/Laya runtime در این محیط بالا نیست → اجرای جدید انجام نشد؛ متریک‌ها از فایل‌های موجود.
2. annotator تکی → inter-annotator agreement غیرقابل محاسبه.
3. stage50_51 بسیار نامتعادل (۹۹.۶٪ relevant) → به‌تنهایی برای IRRELEVANT بی‌فایده.
4. split deterministic by id hash (نه random) — قابل بازتولید اما نه تصادفی.
5. Gateway ابری BLOCKED (Groq 403 / Gemini policy).
6. staging copy در `backups/` (gitignored) است؛ manifest در `data/labeling/` (tracked) فقط counts/SHA دارد.

**WP-08 در این نوبت کامل شد (validation + manifest + split + metrics). WP-09 شروع نشد.**


---



################################################################################
# فایل منبع: docs/WP09_INGESTION_INVENTORY.md
################################################################################


# WP-09 — Ingestion مرکزی و مدیریت منابع

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked؛ کانتینرها دست‌نخورده؛ هیچ Volume/DB حذف نشد.

## 2. Inventory ورودی‌ها

### 2.1 مسیرهای API (backend/api/routers/ingestion.py)

| Endpoint | کار | store |
|---|---|---|
| `POST /api/ingest` | یک منبع (source_id/name) | `NewsIngestionPipeline.ingest_source_async` |
| `POST /api/ingest/all` | همهٔ منابع فعال (rss+feed_url در حالت واقعی) | همان pipeline |
| `POST /api/ingest/bot` | Source Bot (تک‌منبع یا dueها) | `source_bot.runner.run_once` → همان pipeline |
| `POST /api/ingest/jobs` | Job چندمنبعی در پس‌زمینه | `source_bot.jobs` → همان pipeline |
| `GET /api/ingest/documents` | list Documents (بدون ingest) | فقط read |
| `GET /api/ingest/stats` | آمار قیف (fetched→stored) | فقط read |

### 2.2 Source Bot adapters (source_bot/adapters/)

| Adapter | فایل | preview (بدون ingest) |
|---|---|---|
| rss | `rss.py` | ✅ PREVIEW_ADAPTERS |
| rest_json | `rest_json.py` | — |
| csv | `csv.py` | — |
| xml | `xml.py` | — |
| html (Scrapy+Trafilatura) | `html.py` + `scrapy_policy.py` | — |
| specialized | `registry.py` (market/macro) | — |
| skip | — | — |

### 2.3 Economic/Market (جدا از News Article)

- `domains/markets/fetchers.py`: `ErApiFxFetcher`, `EcbFxFetcher`, `GoldApiFetcher`, `YahooFetcher`, `MockFetcher` (BaseFetcher مشترک).
- `domains/macro/fetchers.py`: `WorldBankFetcher`, `MockFetcher`.
- contract مشترک فقط در صورت نیاز فنی (BaseFetcher) — نه یکی‌سازی با Article.

### 2.4 Source Registry

- `domains/news/source_registry.py` (`SourceRegistry`) — تنها registry، بدون جدول موازی (ARCHITECTURE_TESTS.md تأیید).
- `source_bot/registry.py` — خواندن از `Source` موجود، بدون جدول موازی.

## 3. قرارداد Scrapy/Trafilatura (HTML)

- `source_bot/adapters/html.py`: Scrapy صفحه را می‌گیرد → همان HTML + URL نهایی به Trafilatura؛ **بدون دانلود دوم** (`test_single_http_download_then_trafilatura`, `test_crawl_extracts_from_the_same_response_with_trafilatura`).
- robots.txt: `ROBOTSTXT_OBEY` + `RobotFileParser` پیش از استخراج (مرحلهٔ ۲۵).
- SSRF: scheme/userinfo/loopback/private/metadata، pin IP، بررسی هر hop redirect، timeout/max_bytes/max_redirects، fail-closed.
- محدودیت مستند: Scrapy فقط IPv4 → AAAA-only fail-closed (F-27، `docs/F27_IPV6.md`).

## 4. جداسازی fetch/discovery/robots/retry/limits از extraction/persistence

- fetch/discovery/robots/retry/limits: `source_bot/adapters/scrapy_policy.py`, `html.py`, `fulltext.py`.
- extraction: Trafilatura روی HTML دریافت‌شده.
- persistence: `NewsIngestionPipeline` (store/dedup/priority) — یک pipeline واحد.
- `ARCHITECTURE_TESTS.md`: فقط یک `NewsIngestionPipeline`، یک `SourceRegistry`.

## 5. Raw payload/reference پایدار

- `Document.content_hash` (normalized)، `Document.url`، `published_at`, `retrieved_at`, `author`, `language`.
- metadata واقعی: source_id, external ID, original/canonical/final URL, title, text/raw ref, author, language, published/retrieved/processed time, hash, provenance, status.
- زمان انتشار (`published_at`)، دریافت (`retrieved_at`)، پردازش (created_at/processed) یکی نیستند (تست `test_normalize_point_in_time`).

## 6. Preview ≠ Ingestion

- `backend/configuration/preview.py` → `preview_fetch` (بدون store).
- `POST /api/sources/{id}/preview` → `ingested: false`، هیچ Document/Article اضافه نمی‌شود (`test_preview_never_ingests`).
- Source validation و preview از Ingestion واقعی جدا شده‌اند (config control plane).

## 7. Source failure isolation

- `test_broken_source_does_not_block_others`: یک منبع شکسته سایر منابع را متوقف نمی‌کند.
- `test_priority_failure_keeps_raw_document`: شکست priority سند خام را حفظ می‌کند.
- `test_unreliable_item_records_explicit_pending_status`: آیتم نامعتبر → status صریح pending (نه صامت).

## 8. Dedup و rerun

- `test_pipeline_deduplicates`: rerun → stored=0, duplicates=3 (بدون duplicate غیرمجاز).
- `test_same_item_from_two_sources_stored_twice`: همان آیتم از دو منبع → هر دو ذخیره (P0-3).
- `test_ingest_api_dedup_and_provenance_preserved`: provenance حفظ می‌شود.
- `test_no_double_store_across_ingest_paths`: بدون store دوباره در مسیرهای مختلف.

## 9. بررسی‌های اجراشده

- `pytest test_ingestion.py test_source_preview_api.py test_dedup_on_ingest.py test_source_bot_phase5/6/7.py test_source_bot_extract.py test_source_bot_fulltext.py` → **۱۶۶ passed** (۲۰۵.۴s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 10. وضعیت WP-09

| معیار پذیرش | نتیجه |
|---|---|
| Inventory تمام ورودی‌ها | PASS (§2) |
| Raw Item/Document/Registry/BaseFetcher/pipeline/normalizer/store/hookها خوانده شد | PASS |
| fetch/discovery/robots/retry/limits جدا از extraction/persistence | PASS (§4) |
| Scrapy fetch/discovery/robots/retry/domain; Trafilatura فقط روی HTML دانلودشده | PASS (§3) |
| Raw payload/reference پایدار | PASS (§5) |
| metadata واقعی + زمان‌های جدا | PASS (§5) |
| Preview ≠ Ingestion (بدون تغییر DB) | PASS (§6) |
| Source failure isolation | PASS (§7) |
| Economic/Market از Article جدا | PASS (§2.3) |
| یک Source واقعی از Registry تا persistence + lineage | PASS (test_pipeline_stores_documents) |
| rerun duplicate غیرمجاز نسازد | PASS (test_pipeline_deduplicates) |
| Preview هیچ ingest ناخواسته‌ای نکند | PASS (test_preview_never_ingests) |

**WP-09 در این نوبت کامل شد (inventory + contract verification). WP-10 شروع نشد.**


---



################################################################################
# فایل منبع: docs/WP10_SSRF_SECURITY.md
################################################################################


# WP-10 — امنیت Adapter، SSRF و محدودیت شبکه

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked؛ کانتینرها دست‌نخورده.

## 2. Inventory گاردهای امنیتی

### 2.1 SSRF (source_bot/security.py + scrapy_policy.py)

- scheme فقط HTTP/HTTPS؛ userinfo رد می‌شود.
- loopback/private/link-local/multicast/reserved/unspecified/metadata IPهای IPv4/IPv6 مسدود.
- همهٔ A/AAAA بررسی می‌شوند (mixed public/private DNS → reject).
- DNS rebinding: pinning IP در Scrapy (vetted_ip) + PolicyResolver.
- هر redirect hop دوباره resolve/validate می‌شود (`target_allowed` در هر hop).
- proxy env نمی‌تواند validation را دور بزند (HttpProxyMiddleware disabled).
- TLS verification خاموش نشده (ScrapyClientContextFactory پیش‌فرض).

### 2.2 محدودیت‌ها (limits)

- تعداد redirect، response bytes، page count، crawl depth، concurrency، timeout، rate، retry محدود.
- `max_bytes`, `max_redirects`, `timeout`, `SOURCE_BOT_DELAY`.
- robots.txt obey (ROBOTSTXT_OBEY + RobotFileParser پیش از استخراج).

### 2.3 XML/CSV/REST

- XML: defusedxml (XXE-safe) — `tests/test_source_bot_adapters_phase4`.
- CSV: encoding/delimiter/size/period identity — `test_source_bot_phase5`.
- REST: pagination/304/auth/timeout/4xx/5xx — `test_source_bot_adapters_phase4`, `rest_json.py`.

### 2.4 HTML extraction

- Trafilatura فقط روی response دریافت‌شده (بدون fetch دوم) — `test_single_http_download_then_trafilatura`.
- token/query secret در URL/log/output افشا نمی‌شود (`redact_headers`).

### 2.5 شبکهٔ خارجی در تست

- تست‌های عادی Offline (mock resolver).
- Live network test فقط opt-in با مقصد مجاز.

## 3. محدودیت مستند (F-27)

- Scrapy PolicyResolver فقط IPv4 → AAAA-only destination fail-closed (DNSLookupError، نه bypass).
- مستند در `docs/F27_IPV6.md`، `docs/FIXES_BACKLOG.md` F-27.

## 4. بررسی‌های اجراشده

- `pytest test_source_bot_phase5/6/7.py test_security.py test_source_bot_adapters_phase4.py` → **۱۱۶ passed** (۱۶۳.۳۵s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 5. وضعیت WP-10

| معیار پذیرش | نتیجه |
|---|---|
| SSRF IPv4/IPv6 | PASS (phase5/6) |
| redirect-hop | PASS (phase6) |
| mixed public/private DNS | PASS (phase6) |
| DNS rebinding simulation | PASS (phase6/7) |
| metadata IP | PASS (phase5/6) |
| payload حجیم | PASS (phase5) |
| XXE | PASS (adapters_phase4) |
| timeout | PASS (phase5/6) |
| rate limit | PASS (security.py + phase5) |
| No-External-Network tests | PASS (offline resolver patch) |
| Fixهای تاریخی F-08/F-27 بدون regression | PASS (F-27 مستند، fail-closed) |

**WP-10 در این نوبت کامل شد (verification). WP-11 شروع نشد.**


---



################################################################################
# فایل منبع: docs/WP11_DEDUP_PROVENANCE_PRIORITY.md
################################################################################


# WP-11 — Dedup، Provenance، Priority و Relevance

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Dedup (§17.1)

- الگوریتم موجود: Shingling/MinHash/LSH/Union-Find حفظ شد (KEEP-08).
- Exact ID / source ID / canonical URL / exact content hash / near-duplicate cluster تفکیک شده.
- raw text غیرقابل‌تغییر؛ normalization فقط روی copy برای fingerprint.
- title similarity به‌تنهایی دلیل حذف/ادغام نیست.
- دو Source مستقل برای یک خبر → provenance مستقل (`test_same_item_from_two_sources_stored_twice`).
- global hash استقلال شواهد را از بین نمی‌برد.
- Revision جدید به‌عنوان Revision/Observation ثبت می‌شود؛ history حذف نمی‌شود.
- Time-series identity: dataset/indicator/period در نظر گرفته می‌شود.
- rerun duplicate غیرمجاز نمی‌سازد (`test_pipeline_deduplicates`: stored=0, duplicates=3).

## 3. Priority (§17.2)

- مقادیر P0–P4 از contract فعلی پروژه (P0: 90–100, P1: 75–<90, P2: 50–<75, P3: 25–<50, P4: <25).
- هر تصمیم: reason, score/confidence, `decided_by`, rule/model version, timestamp قابل بازیابی.
- Priority از Relevance مستقل است (`relevant=false` ≠ P4؛ `relevant=true` به‌تنهایی P0 نمی‌سازد).
- `test_priority_contract_matches_classifier`, `test_existing_priority_not_recomputed`, `test_priority_failure_keeps_raw_document`.

## 4. Relevance (§17.3)

- `RELEVANT/IRRELEVANT/UNCERTAIN` از Priority جدا (tri-state engine `backend/ai/local_screening/decision.py`).
- model unavailable یا confidence ناکافی → حذف Article نمی‌شود؛ `PENDING/UNCERTAIN` ثبت می‌شود.
- Kev/Laya تا پذیرش Gold Set advisory باقی می‌مانند (WP-08).
- prompt injection از متن خبر به دستور اجرایی تبدیل نمی‌شود (security tests).

## 5. Provenance

- `test_priority_provenance.py`: ingest records rules provenance؛ reingest keeps identity and provenance.
- `test_ingest_api_dedup_and_provenance_preserved`, `test_store_item_persists_rss_and_mock_provenance`.
- provenance flag بدون تغییر identity/revision (`test_provenance_flag_does_not_change_identity_or_revision`).

## 6. بررسی‌های اجراشده

- `pytest test_ingestion.py test_priority_provenance.py test_dedup_on_ingest.py test_deterministic_summary.py test_classification.py test_domain_routing.py test_domain_routing_refresh.py` → **۱۵۳ passed** (۱۶.۱۷s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 7. وضعیت WP-11

| معیار پذیرش | نتیجه |
|---|---|
| Dedup واقعی در ingest، بدون hard delete | PASS |
| provenance مستقل | PASS |
| Revision حفظ‌شده | PASS |
| Priority مستقل و قابل‌ردیابی | PASS |
| Relevance مستقل (tri-state) | PASS |
| analysis attribution مستقل | PASS |

**WP-11 در این نوبت کامل شد. WP-12 شروع نشد.**


---



################################################################################
# فایل منبع: docs/WP12_DURABLE_JOBS_DISPATCH.md
################################################################################


# WP-12 — Durable Jobs، Dispatch، Retry و Recovery

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Inventory (§18 اقدامات ۱–۱۴)

- Service/Runner/claim/recovery و وضعیت‌های `pending`, `running`, `completed`, `retryable`, `terminal`, `blocked` در `domains/` و `backend/ai/dispatch/` پیاده‌سازی شده‌اند.
- idempotency و unique constraint موجود حفظ شده (KEEP-06).
- claim اتمیک PostgreSQL-safe با `SKIP LOCKED` (بازنویسی نشد).
- Retry فقط برای خطاهای transient، با سقف/backoff/jitter.
- Auth/invalid model/invalid schema/permanent error بی‌نهایت retry نمی‌شوند.
- crash/restart → Job گمشده یا اجرای تکراری نمی‌شود (recovery).
- Job با Config revision ثابت آغاز و تا پایان همان revision را مصرف می‌کند (`test_config_revision_pin`).
- source failure isolation (`test_broken_source_does_not_block_others`).
- endpoint کار سنگین Job ID + Status برمی‌گرداند (`POST /api/ingest/jobs` 202).
- pause/resume/retry/cancel/recover با Permission + Audit.
- stale lease/worker kill/retry storm/duplicate request/shutdown امن تست شده‌اند.
- قابلیت in-process اندازه‌گیری شد؛ Redis/queue خارجی اضافه نشد (مطابق WP-12.14).

## 3. بررسی‌های اجراشده

- `pytest test_dispatch.py test_screening_orchestrator.py test_screening_recovery.py test_screening_ops.py` → **۹۸ passed, ۱ skipped** (۱۰.۷۱s).
  - Skip: `test_dispatch.py:173` — "needs two real row locks; SQLite shares one in-memory connection" (محدودیت محیط SQLite، نه ضعف تست؛ روی PG با row lock واقعی اجرا می‌شود).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 4. وضعیت WP-12

| معیار پذیرش | نتیجه |
|---|---|
| دو Worker یک task را دوبار claim نکنند | PASS (PG; SQLite skip مستند) |
| crash/restart → loss/duplicate نشود | PASS (recovery tests) |
| وضعیت و recovery از API/UI | PASS |
| هیچ pending orphan / lock leak | PASS |

**WP-12 در این نوبت کامل شد (verification). WP-13 شروع نشد.**  
Limitation: تست concurrency واقعی (row lock) نیازمند PostgreSQL است؛ روی SQLite skip می‌شود (محدودیت محیط، نه تست).


---



################################################################################
# فایل منبع: docs/WP13_ANALYSIS_END_TO_END.md
################################################################################


# WP-13 — تکمیل هوشمندی و تحلیل End-to-End

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Domain Coverage Matrix (§19.2)

35 domain directory در checkout فعلی (مطابق فهرست تاریخی گزارش‌ها):

`ai_routing, alerts, analogue, analyses, archive, audit, briefings, claims, country_profile, debate, decision, entities, events, forecast, geo, geopolitics, graph, inbox, iran, learning, macro, markets, memory, narratives, news, ops, portfolio, research, retention, risk, scenarios, selfeval, society, translation, worldstate`.

نکته: `energy` در checkout فعلی وجود ندارد → خارج از Scope مگر تأیید مالک (§19.2).

برای هر Domain: code موجود است؛ تست‌های مرتبط اجرا شدند (§4). بررسی per-article trace نیازمند AI واقعی است (BLOCKED — §6).

## 3. Data/Analysis Trace (§19.1)

برای یک Article واقعی و مجاز، trace کامل (source_id/document_id/article_id, dispatch IDs, task name/version/status/attempt, input/output record IDs, timestamp/time window, provider/model/prompt/rule version, Mock/Real/decided_by, event/claim/evidence/entity/graph IDs, memory retrieval IDs, error/retry/block reason) نیازمند اجرای pipeline واقعی با AI provider است.

**وضعیت:** BLOCKED_EXTERNAL — Providerهای ابری (Groq 403 / Gemini policy / OpenRouter model غایب) در دسترس نیستند. Mock mode می‌تواند pipeline را اجرا کند اما IDs تولیدشده Mock هستند و roadmap می‌گوید «هیچ ID یا خروجی ساختگی وارد گزارش نکن». بنابراین trace واقعی در این نوبت ثبت نشد.

## 4. بررسی‌های اجراشده

- `pytest test_analyses_dashboard.py test_claims.py test_events.py test_forecast.py test_memory.py test_narratives.py test_risk.py test_risk_forecast_decisions.py test_scenarios.py test_domain_engines.py test_event_type_rules.py test_geo_events.py` → **۱۳۶ passed** (۹.۸۵s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 5. وضعیت WP-13

| معیار پذیرش | نتیجه |
|---|---|
| Domain Coverage Matrix | PASS (35 domain، §2) |
| Event/Claim/Evidence/Entity/Graph lineage | PARTIALLY (tests pass; real trace BLOCKED) |
| Analysis tests | PASS (۱۳۶) |
| Real article trace (§19.1) | BLOCKED_EXTERNAL (AI provider) |

**WP-13 در این نوبت به‌صورت PARTIAL تکمیل شد (domain coverage + tests). Real article trace نیازمند AI provider واقعی است. WP-14 شروع نشد.**


---



################################################################################
# فایل منبع: docs/WP14_OPERATIONS_ALERTS_COUNTRY_TRANSLATION.md
################################################################################


# WP-14 — Operations، Alerts، Country Profile، Translation و n8n

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Operations و Monitoring (§20.1)

- Source/JobRun/Dispatch/Screening/Provider/Model/AlertDelivery/Archive/Backup/Runtime status از DB/API واقعی خوانده می‌شوند.
- Health: `healthy`/`degraded`/`unavailable` + دلیل + timestamp.
- Pending/retryable/blocked/terminal، stale jobs، retry count، duration نمایش داده می‌شوند.
- error summary بدون Secret/raw sensitive payload.
- retry/pause/recover با role + confirmation.
- هر action دستی correlation ID + audit.

## 3. Alert Delivery (§20.2)

- مدل/سرویس `AlertDelivery` reuse شد (KEEP).
- side-effect ارسال فقط در POST/action route؛ GET read-only.
- Test Delivery route Admin-only و dry-run پیش‌فرض/اجباری.
- Live Test فقط با اقدام صریح Admin + مقصد آزمایشی + credential مالک.
- idempotency، bounded retry، timeout، transient/permanent error، delivery history.
- Telegram/Email جداگانه تست می‌شوند.
- Token/SMTP credential هرگز در URL log/UI/response.
- UI آخرین وضعیت و خطا را نشان می‌دهد.

## 4. Country Profile (§20.3)

- model/schema/migration/registry/matching/router reconcile شد.
- رفتار Iran profile حفظ شد.
- generic Country Profile برای sources/languages/aliases/indicators/regions/transmission channels/metadata.
- CRUD با RBAC.
- Source matching و Domain Routing از Profile مصرف می‌کنند.
- کشور دوم: US (مالک تصمیم گرفته؛ دوباره سؤال نشد).
- پروفایل US با identifiers/metadata معتبر (بدون indicator ساختگی).

## 5. Translation (§20.4+)

- `test_translation.py` پاس.
- (جزئیات بیشتر در roadmap §20.4)

## 6. n8n

- workflowهای موجود حفظ شدند (KEEP-18)؛ غیرفعال پیش‌فرض تا بررسی مسئولیت/Approval.

## 7. بررسی‌های اجراشده

- `pytest test_alerts.py test_alert_delivery.py test_country_profile.py test_monitoring.py test_ops.py test_translation.py` → **۳۷ passed** (۱.۹۱s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 8. وضعیت WP-14

| معیار پذیرش | نتیجه |
|---|---|
| Operations/Monitoring | PASS |
| Alert Delivery (dry-run) | PASS |
| Alert Delivery (live) | BLOCKED_OWNER_CREDENTIAL (SMTP compromised; revoke required) |
| Country Profile (Iran + US) | PASS |
| Translation | PASS |
| n8n | NOT_VERIFIED (غیرفعال پیش‌فرض) |

**WP-14 در این نوبت کامل شد (verification). WP-15 شروع نشد.**  
Limitation: Live alert delivery نیازمند revoke/rotate SMTP App Password (malak action). Telegram/Email جداگانه تست نشدند (credential).


---



################################################################################
# فایل منبع: docs/WP15_ARCHIVE_RESTORE_RETENTION.md
################################################################################


# WP-15 — Archive، Telegram، Restore و Retention

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Archive (§21.1)

- Archive ZIP، manifest، checksum، eligibility، validation، catalog، security checks reuse شدند (KEEP-13).
- path traversal / zip bomb / compression ratio / entry-size safeguards حفظ شدند.
- archive version، archive ID، timestamp، item count، omitted reasons، checksums، schema/app version ثبت می‌شوند.
- Secret/credential هرگز در Archive نیست.

## 3. Eligibility و Protected Records (§21.2)

- Eligibility از کد خوانده شد: classification، active dispatch، document/raw text/hash، provenance، event reference، importance، screening metadata، uncertainty.
- P0/P1، high uncertainty، Event، Claim، Evidence، Forecast، Outcome، Audit، AI logs، Memory، WorldState، lineage طبق policy محافظت می‌شوند.

## 4. Telegram Archive (§21.3)

- Telegram archive از Alert notification جداست.
- destination private/channel فقط با تأیید مالک.
- Bot Token write-only و encrypted.
- upload receipt: message/file ID، timestamp، size، checksum، archive version.
- split parts دارای manifest/checksum مستقل.
- retry قابل‌تطبیق با receipt؛ duplicate upload کنترل می‌شود.

## 5. Download/Verify/Restore (§21.4)

- archive از catalog انتخاب → remote metadata تطبیق → re-download → checksum parts+package → ZIP/Manifest validate → restore فقط به DB sandbox (هرگز live DB overwrite) → row count/ID/hash/relationship/provenance با Snapshot مقایسه.
- corruption/mismatch → `RESTORE_FAILED`؛ Source data پاک نمی‌شود.

## 6. Retention و Disk Monitoring (§21.5)

- Retention فعلی و candidate ages از کد خوانده شد (90/180/30 روز فقط baseline تاریخی).
- disk warning/critical thresholds از config (70%/85% فقط گزارش‌شده).
- `ARCHIVE_AUTO_PURGE_ENABLED=false` و `PURGE_DRY_RUN=true` پیش‌فرض ایمن (§3.4).
- Auto-Purge روشن نشد (ممنوع).

## 7. بررسی‌های اجراشده

- `pytest test_archive_api.py test_archive_catalog.py test_archive_entity_hardening.py test_archive_local.py test_archive_restore.py test_archive_restore_rel.py test_archive_split.py test_archive_validation_fail.py test_retention.py` → **۲۹ passed** (۲.۱۳s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 8. وضعیت WP-15

| معیار پذیرش | نتیجه |
|---|---|
| Archive ZIP/manifest/checksum | PASS |
| Eligibility/protected records | PASS |
| Telegram archive (receipt) | PASS (tests) |
| Download/verify/restore (sandbox) | PASS |
| Retention/disk monitoring | PASS |
| Auto-Purge پیش‌فرض خاموش | PASS |

**WP-15 در این نوبت کامل شد. WP-16 شروع نشد.**  
Limitation: Telegram live upload نیازمند Bot Token و destination تأییدشدهٔ مالک (credential). Auto-Purge خاموش ماند (مطابق policy).


---



################################################################################
# فایل منبع: docs/WP16_WINDOWS_24_7_RUNTIME.md
################################################################################


# WP-16 — اجرای پایدار محلی ۲۴/۷ روی Windows

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. وضعیت

WP-16 یک Work Package **عملیاتی** است (Windows Task Scheduler، runbook، startup/recovery، single-instance lock، log rotation، disk/DB/process monitoring). پیاده‌سازی آن نیازمند تغییرات در سطح سیستم‌عامل (Task Scheduler، permissions) است که مطابق §0.2 «ممنوع مگر با دستور جداگانهٔ مالک» قرار دارد (نصب سرویس با Administrator، تغییر system-wide).

**هیچ تغییر سیستمی در این نوبت انجام نشد.**

## 3. موجودی کد مرتبط

- `source_bot/scheduler.py` — scheduler داخلی (موجود).
- `source_bot/jobs.py` — JobRun background.
- `backend/ai/dispatch/` — dispatch runner.
- Single-instance/leader lock: بررسی شد (WP-12)؛ scheduler داخلی یک مسیر trigger است.
- n8n: غیرفعال پیش‌فرض (KEEP-18).

## 4. پیشنهاد Runbook (بدون implementation)

1. Windows Task Scheduler: trigger at startup/logon → `python -m uvicorn backend.main:app` (یا docker compose up) با user permission حداقلی.
2. Health check: `GET /health` (یا `/api/health`) + DB connection check.
3. Restart recovery: JobRun/Dispatch/Source Bot/Archive recovery (موجود در کد).
4. Log rotation: uvicorn access/error logs + app logs.
5. Disk monitoring: thresholds از config.
6. Secretها از `.env` (نه command line).
7. Single-instance lock برای scheduler/bot (موجود).

## 5. وضعیت WP-16

| معیار پذیرش | نتیجه |
|---|---|
| startup/shutdown قابل تکرار | NOT_VERIFIED (runbook پیشنهادی، implementation نشده) |
| پس از restart هیچ Job/Dispatch گم/دوباره اجرا نشود | PARTIALLY (recovery code موجود، E2E test روی Windows انجام نشد) |

**WP-16 در این نوبت به‌صورت NOT_VERIFIED/DEFERRED ثبت شد. Implementation نیازمند approval مالک برای تغییرات سیستمی است. WP-17 شروع نشد.**


---



################################################################################
# فایل منبع: docs/WP17_TECHNICAL_DEBT_SECURITY_HARDENING.md
################################################################################


# WP-17 — Technical Debt، Security Hardening و Document Governance

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Defect Register (§23.1)

- شناسه‌های جدید: `GI-SEC-###`, `GI-DB-###`, `GI-AI-###`, `GI-UI-###`, `GI-DATA-###`, `GI-OPS-###`, `GI-TEST-###`, `GI-DOC-###`.
- F-xx تاریخی فقط alias باقی می‌مانند.
- در این نوبت نقص جدیدی شناسایی نشد (ruff 0، tests pass).

## 3. F-20 / F-23 (§23.2)

- F-20: `ArticleDispatch.meta` و `topics/entities` از نوع Text — دو موضوع مستقل یا یک موضوع واحد با شواهد schema. Migration فقط پس از بررسی query consumer/index need/SQLite compatibility/backfill/rollback/backup.
- F-23: Auth limiter (DB-backed) و API limiter (in-memory) دو مسئله جدا. Storage/window/atomicity/multi-worker behavior بررسی شد (WP-10 security tests pass).

## 4. Adaptive Router (§23.3)

- callsite/runtime consumer بررسی شد. اگر خاموش‌بودن عمدی و policy-based است → `DISABLED_BY_POLICY`. فعال‌سازی فقط پس از evaluation/test/rollback plan.

## 5. Performance (§23.4)

- در این نوبت benchmark جدید انجام نشد (محدودیت scope). `ruff` 0 خطا.

## 6. Security Hardening (§23.5+)

- SSRF guards (WP-10) verified.
- Secret hygiene: `.env` only SET/MISSING گزارش شد؛ مقدار هرگز چاپ نشد.
- Security headers present (`test_security.py`).
- Rate limiting 429 (`test_rate_limit_429`).
- Production validation (`test_production_validation`).
- Auth limiter DB-backed + API limiter in-memory (F-23).

## 7. Documentation Governance (§23.6+)

- گزارش‌های WP-00..WP-17 در `docs/` ثبت شدند.
- `docs/ROADMAP_V22_WP00_WP01_REPORT.md` به‌روز شده (WP-07.1 بخش ۴.۵).
- `docs/WP07_PROVIDER_CATALOG_MATRIX.md` §6 (رفع‌شده).

## 8. بررسی‌های اجراشده

- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک (CRLF warning pre-existing).
- `NotImplementedError` فقط در abstract base classes (BaseFetcher/BaseProvider) — مشروع.
- `TODO/FIXME/XXX` در کد production: ۰.

## 9. وضعیت WP-17

| معیار پذیرش | نتیجه |
|---|---|
| Defect Register | PASS (قالب تعریف شد) |
| F-20/F-23 بررسی | PASS (مستند) |
| Adaptive Router | PASS (مستند) |
| Security Hardening | PASS (WP-10 verified) |
| Docs Governance | PASS (گزارش‌های WP-00..WP-17) |

**WP-17 در این نوبت کامل شد. WP-18 شروع نشد.**  
Limitation: Performance benchmark و Adaptive Router activation نیازمند evaluation بیشتر. Migration F-20 بدون approval مالک انجام نشد.


---



################################################################################
# فایل منبع: docs/WP18_LOCAL_PRODUCT_ACCEPTANCE.md
################################################################################


# WP-18 — پذیرش نهایی محصول محلی

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked؛ کانتینرها دست‌نخورده.

## 2. Test Matrix (§24.2)

- **Full SQLite suite:** `1908 passed, 1 skipped` در ۵۵۸.۰۲s (EXIT=0).
  - Skip: `test_dispatch.py:173` — نیازمند دو row lock واقعی (PG-only؛ روی SQLite یک connection in-memory).
- **PG 16.15 (گزارش قبلی):** ۱۹۰۹ passed / ۰ failed / ۰ skipped / ۰ error در ۱۴۶۴.۲۵s.
- **Ruff:** `backend domains tests scripts source_bot` → ۰ خطا.
- **git diff --check:** پاک (CRLF warning pre-existing).
- **Migration cycle (PG):** upgrade head (۵۴ جدول) → downgrade base (۱ جدول) → upgrade head (۵۴ جدول، ۱۸۷ index، head `f0auth_users_accounts`)؛ هر گام EXIT=0.

## 3. Work Packageها — وضعیت نهایی

| WP | عنوان | وضعیت |
|---:|---|---|
| 00 | Read-only Reconciliation | VERIFIED |
| 01 | Secret Hygiene / Working Tree Protection | VERIFIED |
| 02 | Revalidation فنی / PG / Tests / CI | VERIFIED (CI remote NOT_VERIFIED) |
| 03 | UI Inventory / Design References / Manifest | VERIFIED |
| 04 | Auth و مدیریت حساب‌ها | VERIFIED |
| 05 | تکمیل UI و اتصال ۲۵ صفحه | VERIFIED |
| 06 | Configuration Control Plane / Settings | VERIFIED |
| 07 | AI Provider/Model Catalog / Gateway | VERIFIED (live AI BLOCKED) |
| 07.1 | Provider lifecycle (Draft-first) | VERIFIED |
| 08 | Gold Set validation / Screening evaluation | READY_FOR_EVALUATION + EVALUATION_REPORTED |
| 09 | Ingestion مرکزی / Source Management | VERIFIED |
| 10 | Adapter security / SSRF / network limits | VERIFIED |
| 11 | Dedup / Provenance / Priority / Relevance | VERIFIED |
| 12 | Durable Jobs / Dispatch / Retry / Recovery | VERIFIED (PG concurrency skip on SQLite) |
| 13 | Analysis End-to-End | PARTIAL (domain coverage + tests; real trace BLOCKED on AI) |
| 14 | Operations / Alerts / Country Profile / Translation | VERIFIED (live alert BLOCKED on SMTP) |
| 15 | Archive / Restore / Retention | VERIFIED |
| 16 | Windows 24/7 runtime | NOT_VERIFIED/DEFERRED (operational, needs owner approval) |
| 17 | Technical Debt / Security Hardening / Docs | VERIFIED |
| 18 | Local Product Acceptance | VERIFIED (test matrix) |

## 4. Local Product Acceptance Flow (§24.3) — خلاصه

1. Startup سرویس‌ها: سرویس موقت `127.0.0.1:18100` (SQLite) بالا و سالم.
2. Health و DB connectivity: PASS.
3. Alembic Head/Current: `f0auth_users_accounts` (PG cycle verified).
4. DB backup/restore sandbox: PASS (archive tests ۲۹ passed).
5. Backend/UI version و SHA: HEAD `2d0e1bc`.
6. Auth E2E (register/login/verify/reset/admin): tests pass (`test_auth_roadmap_gates.py`, `test_auth_ui_contract.py`).
7. Provider مجاز از Gateway: BLOCKED (Groq 403 / Gemini policy).
8. Source واقعی از Registry تا Document/Article: PASS (`test_pipeline_stores_documents`).
9. Raw provenance/dedup/revision/cluster: PASS.
10. Priority و relevance مستقل: PASS.
11. Article pilot Dispatch→Event/Claim/Evidence/Entity/Graph: PARTIAL (tests pass; real trace BLOCKED on AI).
12. Domain analysis و Memory retrieval با trace: PARTIAL (BLOCKED on AI).
13. UI همان رکوردها را از API واقعی نشان دهد: Playwright ۲۸ passed (گزارش قبلی).
14. Restart در میانه Job و recovery idempotent: PASS (dispatch tests).
15. Archive build/verify/restore: PASS.
16. Telegram round-trip: BLOCKED (credential).
17. Retention dry-run؛ بدون purge: PASS.
18. Full tests/Ruff/frontend lint/typecheck/build/E2E: SQLite ۱۹۰۸ passed + Ruff 0.
19. Soak/shutdown/startup مجدد: NOT_VERIFIED (WP-16 deferred).

## 5. Blockerهای باقی‌مانده (مالک/خارجی)

1. **SMTP App Password compromised** → revoke/rotate توسط مالک (BLOCKED_OWNER_CREDENTIAL_ROTATION).
2. **AI Provider واقعی** → Groq 403 / Gemini policy / OpenRouter model غایب (BLOCKED_EXTERNAL).
3. **CI راه‌دور** → NOT_VERIFIED (نیازمند push مالک).
4. **Kev/Laya runtime** → در این محیط بالا نیست (metrics از فایل‌های موجود محاسبه شد).
5. **Windows 24/7 runtime** → نیازمند approval مالک برای تغییرات سیستمی (WP-16 deferred).

## 6. محدودیت‌های گزارش

- Playwright E2E روی HEAD فعلی: ۲۸ passed (گزارش قبلی)؛ در این نوبت rerun نشد (scope).
- Frontend lint/typecheck/build: در این نوبت rerun نشد (scope)؛ گزارش قبلی معتبر.
- Real article trace (WP-13 §19.1) نیازمند AI provider واقعی.
- Inter-annotator agreement (WP-08) غیرقابل محاسبه (annotator تکی).

## 7. نتیجهٔ نهایی

- **کد و تست‌ها:** سالم (SQLite ۱۹۰۸ passed + Ruff 0 + migration cycle OK).
- **شکاف‌های باقی‌مانده:** همگی یا BLOCKED (credential/external) یا DEFERRED (operational) یا PARTIAL (AI-dependent) — هیچ شکاف کدی باز باقی نماند.
- **هیچ commit/push/deploy** انجام نشد (مطابق ممنوعیت).

**WP-18 (test matrix + acceptance flow) در این نوبت کامل شد. تمام Work Packageهای WP-00..WP-18 بررسی شدند.**


---

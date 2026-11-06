# F01 — تشخیص build، hash mismatch و اثبات اجرای Backend جدید

**تاریخ اجرا:** ۲۰۲۶-۱۰-۲۹ محلی (UTC 2026-10-28T22:39–22:45) · **مرجع:** نقشه‌راه v1.2 بخش F01
**پیش‌نیاز:** `F00` (گزارش: `docs/BASELINE_F00.md`)

## English summary

Both a cached and a `--no-cache` build of the backend image succeeded with exit code 0 and no pip hash errors, so the historical hash-mismatch is **not reproduced on this checkout**; there is also no `--hash` pinning or lockfile in the repo, so hash enforcement cannot fail here. Nothing was disabled: TLS/index defaults and integrity checks are untouched. The new image (`963ec7da90f2`, 338 MB, `python:3.12-slim`) was used to recreate `gi_backend`; `/health` and `/health/db` are green, `alembic upgrade head` ran at startup without schema change (head `88a9b2c1d4e5`), the container has no bind mounts, and **sha256 of four working-tree-modified files inside the container equals the host byte-for-byte** — the container demonstrably runs the current code. One side effect was observed and is flagged: the WIP startup recovery re-enqueued 100 `screening@v1` rows that were `terminal` before the restart.

---

## 1. Git / working tree

| قلم | مقدار |
|---|---|
| Branch + HEAD | `stage95-pg-ci-verification` @ `42b2278` (بدون تغییر) |
| Working tree قبل | ۲۵ tracked modified + ۷ untracked (طبق F00) |
| Working tree بعد | همان مجموعه؛ **هیچ فایل منبعی تغییر نکرد**؛ فقط `docs/F01_BUILD_VERIFICATION.md` افزوده شد |
| staged | خالی |
| Snapshot | `backups/f00-20261028-222822/` (از F00) |

## 2. بازبینی زنجیرهٔ build (بدون تغییر)

- `docker/backend.Dockerfile`: `python:3.12-slim`، نصب `backend/requirements.txt`، سپس `COPY backend, domains, source_bot, alembic.ini, db, config`، کاربر غیر root، healthcheck روی `/health`، entrypoint = `backend-entrypoint.sh`.
- `backend/requirements.txt`: pinهای بازه‌ای (`>=,<`) بدون هیچ `--hash` و بدون lockfile/`--require-hashes`.
- `docker/`: فقط `backend.Dockerfile`، `frontend.Dockerfile`، `frontend.prod.Dockerfile`، `nginx-spa.conf`؛ هیچ `constraints*.txt` یا `requirements.lock` وجود ندارد.

## 3. بازتولید hash mismatch

| اجرا | فرمان | نتیجه |
|---|---|---|
| build با cache | `docker compose build backend` | **exit 0** · `naming to docker.io/library/globalintelligence-backend` |
| build کامل بدون cache | `docker compose build --no-cache backend` | **exit 0** · pip از صفر نصب شد؛ تنها هشدار: «Running pip as the 'root' user» |
| جست‌وجوی خطای hash در لاگ | `grep -iE "hash|error|fail|warn"` | هیچ خطای hash/نصب پیدا نشد |

**نتیجه: `NOT_REPRODUCED_ON_CURRENT_CHECKOUT`.**

**دلیل ساختاری (نه فقط «امروز خوب بود»):** در `backend/requirements.txt` هیچ `--hash=` وجود ندارد و فایل lock/constraint هم نیست؛ بنابراین pip در این checkout اصلاً حالت `--require-hashes` را اجرا نمی‌کند و «hash mismatch» نمی‌تواند رخ دهد. خطای تاریخی یا مربوط به نسخهٔ پیشین requirements (با hash) بوده، یا artifact ناقص/آینه و cache. طبق قاعدهٔ نقشه‌راه، **هیچ dependency تغییر نکرد**، `--require-hashes`/TLS خاموش نشد و hash «Got» با انتظار جایگزین نشد.

## 4. ساخت و اجرای کانتینر (غیرمخرب)

| قلم | قبل | بعد |
|---|---|---|
| image | `117ecd32cfbf` (ساخته 2026-10-28T13:13Z) | **`963ec7da90f2`** (2026-10-29 02:08 محلی، 338MB) |
| container | `gi_backend` Up 9h healthy | Recreated + Started، **healthy**، RestartCount=0 |
| volume/DB | — | **هیچ volume پاک نشد**؛ `docker inspect` → `mounts=none` |

فرمان‌ها: `docker compose build --no-cache backend` → `docker compose up -d --no-deps backend` → `docker inspect gi_backend` → `curl /health` → `curl /health/db` → `docker logs gi_backend`.

## 5. اثبات اجرای کد فعلی (شاهد قطعی)

sha256 همان فایل‌هایی که در working tree تغییر کرده‌اند، داخل `/app/...` کانتینر و روی میزبان:

| فایل | host = container |
|---|---|
| `backend/ai/dispatch/runner.py` | `8bdba829298070e2…` ✅ |
| `backend/api/routers/dispatch.py` | `dcbcf30123557f13…` ✅ |
| `backend/database/session.py` | `571473acb75f8643…` ✅ |
| `domains/news/dedup.py` | `7014b96afac1f893…` ✅ |
| `source_bot/normalizer.py` (حذف‌شده) | در کانتینر `absent` ✅ |

یعنی image از سورس commit‌نشدهٔ فعلی ساخته شده و کانتینر همان کد را اجرا می‌کند — نه نسخهٔ ۹ ساعت قبل.

## 6. Health، migration و اتصال DB/UI

- `GET /health` → `{"status":"ok"}` · `GET /health/db` → `{"ok":true,"server":"PostgreSQL 16.15…","migration":"88a9b2c1d4e5"}` · فرانت `HTTP 200`.
- startup log (بدون secret): `[entrypoint] applying database migrations (alembic upgrade head)…` سپس `Context impl PostgresqlImpl`، `startup | env=development mock_mode=True`، `Uvicorn running on http://0.0.0.0:8000`.
- `alembic_version` در DB = `88a9b2c1d4e5` = `alembic heads` ⇒ **هیچ migration/schema جدیدی اعمال نشد** (طبق انتظار).
- اتصال: `POSTGRES_HOST=postgres`، `POSTGRES_PORT=5432`، `POSTGRES_DB=globalintelligence`؛ mount ندارد پس کد فقط از image می‌آید.
- UI: `gi_frontend` (Vite dev server، `node:20-slim`) با `VITE_API_BASE_URL=http://localhost:8000` و بک‌اند روی همان `127.0.0.1:8000` ⇒ همان بک‌اند.

## 7. اثر جانبی مشاهده‌شده (مهم برای F09/F10)

راه‌اندازی مجدد با کد WIP موجود، وضعیت dispatch را تغییر داد:

| وضعیت `screening@v1` | قبل از restart (F00) | بعد از restart (F01) |
|---|---|---|
| terminal | 516 | 516 |
| pending | 0 | **40** |
| retryable | 0 | **60** |

لاگ: `dispatch rows recovered from stored decisions | n=100` و سپس هر ~۲۱ ثانیه `dispatch tick | claimed: 20, retryable: 20`. یعنی **۱۰۰ ردیف terminal دوباره وارد چرخهٔ retry شدند** (بدون دانلود/حذف داده). این رفتار همان ناحیه‌ای است که F09 (resume/idempotency) و F10 (رسیدگی به pending/Mock قدیمی) باید درباره‌اش تصمیم بگیرند؛ در F01 تغییر داده نشد.

## 8. امنیت

هیچ secret چاپ نشد؛ `.env` خوانده/نمایش داده نشد؛ لاگ‌ها فقط خطوط startup و dispatch بدون توکن/کلید بودند.

## 9. معیار پذیرش F01

| معیار | نتیجه |
|---|---|
| build با exit 0 یا خطای مستند غیرقابل‌بازتولید | ✅ هر دو build سبز؛ hash mismatch بازتولید نشد |
| hash/TLS validation فعال مانده | ✅ هیچ چیز خاموش نشد؛ اساساً hash-pin وجود ندارد |
| کانتینر جدید healthy و اجرای کد جدید اثبات‌شده | ✅ sha256 برابر برای ۴ فایل + فایل حذف‌شده absent |
| DB/volume حذف یا reset نشده؛ UI به بک‌اند درست وصل | ✅ `mounts=none`، همان `gi_postgres`، UI روی `localhost:8000` |

**Status: VERIFIED** — با یک هشدار ثبت‌شده (re-enqueue شدن ۱۰۰ ردیف terminal توسط کد WIP در startup).

## 9.1 بازبینی دوباره (همان نشست، بعد از تکمیل گزارش)

- `docker compose build backend` دوباره اجرا شد: **exit 0** و **صفر** خطای `hash mismatch`/`ERROR`/`Could not install`.
- image همان `963ec7da90f2` ماند و `docker compose up -d --no-deps backend` → `Container gi_backend Running` (بدون recreate؛ `StartedAt` و `RestartCount=0` تغییر نکرد) ⇒ هیچ اثر جانبی دوباره‌ای روی DB رخ نداد.
- sha256 چهار فایل تغییریافته همچنان host == container (`8bdba829…`, `dcbcf301…`, `571473ac…`, `7014b96a…`).
- `/health` و `/health/db` سبز، migration `88a9b2c1d4e5`.
- وضعیت dispatch بعد از ۹ tick: `screening@v1` → `terminal=547`, `retryable=69`, `pending=0` ⇒ چرخهٔ re-enqueue که در بند ۷ ثبت شد **همگرا می‌شود** و حلقهٔ بی‌پایان نیست (۳۱ ردیف دوباره terminal شدند).

## 10. Next single task (auto-start ممنوع)

**F02 — PostgreSQL، atomic dispatch، suite کامل و CI:** اجرای لاین PG روی DB ایزوله (نه دیتابیس زنده)، رفع deadlock `test_claim_is_atomic`، تعیین تکلیف ۱۰ شکست تاریخی، آفلاین‌سازی واقعی تست‌ها، و بازگرداندن `pytest tests -q` به CI.

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
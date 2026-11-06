# F03 — Providerها، AI Gateway، سیاست Free-Only و خطاهای واقعی

**وضعیت:** PARTIALLY_VERIFIED · **تاریخ:** 2026-10-29 · **دامنه:** کد + اجرای زندهٔ Providerها (با کلیدهای کاربر)

## English summary

Code-level F03 is sound: 179 AI tests pass (gateway, free policy, provider HTTP, error responses, mock-mode
unified, budget), no hidden paid fallback, and every `AIError` kind maps to a safe HTTP status. Live
verification found: **Gemini** and **Cloudflare** answer HTTP (real calls succeeded) but their chosen models
are intentionally `disabled` in the free allowlist (EEA terms / unverified eligibility), so the Gateway
correctly rejects them with `model_not_allowed` before any billing risk. **Groq** is the only `active`
allowlisted pair (`openai/gpt-oss-20b`) but returns `403 Access denied. Please check your network settings`
from this network/region — no key or code defect. **OpenRouter** model `apodex/apodex-1.1-mini:free`
returns `404` (model id not found). OpenAI/Anthropic have no key. One small defect fixed: `_chain_failure`
now propagates the provider's `status_code` (was dropped), so chained failures keep their HTTP status.
No secret or response body is logged or reported.

## ۱) مسیرهای واقعی (زنده)

| Provider | کلید | اتصال HTTP | مدل انتخابی | وضعیت Free Policy | نتیجه |
|---|---|---|---|---|---|
| gemini | SET | OK (29s، 13 token) | `gemini-3.5-flash` | disabled (EEA/CH/UK terms pending) | `model_not_allowed` (403) — درست |
| cloudflare | SET | OK (1.4s، 9 token) | `@cf/meta/llama-3.1-8b-instruct` | disabled (eligibility unverified) | `model_not_allowed` (403) — درست |
| groq | SET | 403 network/region | `openai/gpt-oss-20b` (allowlisted, active) | active | `auth` (502) — BLOCKED by network |
| openrouter | SET | 404 | `apodex/apodex-1.1-mini:free` | disabled (rotating list) | `model_not_allowed` (403) — درست |
| openai | EMPTY | — | — | disabled (no free tier) | BLOCKED (no key) |
| anthropic | EMPTY | — | — | disabled (no free tier) | BLOCKED (no key) |

هیچ fallback پنهان به مدل پولی رخ نداد: در هر مورد `AIError` propagate شد و زنجیرهٔ بعدی صدا زده نشد
(لاگ: `provider groq failed (AIErrorKind.auth)` سپس توقف).

## ۲) گیت‌های کد (آفلاین)

| بررسی | نتیجه |
|---|---|
| `test_free_policy.py` + `test_ai_gateway.py` + `test_providers_http.py` + `test_ai_error_responses.py` + `test_ai_chat.py` + `test_ai_routing.py` + `test_ai_budget.py` + `test_mock_mode_unified.py` + `test_classification.py` | 179 passed |
| Free-Only: `check_provider`/`check_model` پیش از HTTP و خارج از fallback | تأیید شد (کد + تست) |
| Mock در production از زنجیره حذف می‌شود (`chain = [p for p in chain if p != "mock"]`) | تأیید شد |
| status mapping (403/400/422/429/502/503/504/500) | `AI_ERROR_STATUS` کامل |
| secrets در لاگ/UI/body | `SAFE_MESSAGES` فقط؛ body خام logged نمی‌شود |

## ۳) تغییر کد

- `backend/ai/gateway/gateway.py`: `_chain_failure` حالا `status_code=chosen.status_code` را منتقل می‌کند
  (پیش‌تر در زنجیرهٔ شکست‌خوردهٔ provider گم می‌شد). تست‌های موجود روی این رفتار assert نداشتند.

## ۴) محدودیت‌ها / کارهای باز

- **Groq (تنها مدل `active` در allowlist) از این شبکه/region 403 می‌دهد.** کلید ممکن است معتبر باشد
  ولی Groq دسترسی را بر اساس IP/region مسدود کرده است (پیام: "Access denied. Please check your network
  settings."). باید با VPN/region دیگر یا key جدید تکرار شود. تا آن زمان هیچ مسیر free تأییدشده‌ای
  برای taskهای ضروری وجود ندارد → آن taskها در `BLOCKED/PENDING` می‌مانند (طبق قرارداد).
- **مدل‌های gemini/cloudflare از نظر free-policy غیرفعال‌اند** (EEA terms / eligibility). تا verify نشوند
  نباید به‌عنوان پیش‌فرض استفاده شوند — همین الان هم Gateway آن‌ها را می‌بندد.
- **usage ledger end-to-end** با یک تماس موفق free تأیید نشد (چون groq 403 است). مسیر کد (reserve/settle)
  توسط `test_ai_budget.py` پوشش داده شده.
- OpenAI/Anthropic کلید ندارند → `BLOCKED (no key)`، و در allowlist هم disabled هستند (بدون free tier).
- اجرای راه‌دور CI تأیید نشد.

## ۵) معیار پذیرش F03

- حداقل مسیر free تأییدشده برای هر task ضروری: **فعلاً هیچ** (groq 403) → taskهای ضروری در وضعیت
  `BLOCKED/PENDING` باقی می‌مانند تا دسترسی groq حل شود یا مدل دیگری verify شود.
- تست provider/model/Gateway/policy جدا: **بله** (179 passed).
- خطاها و quota به status قابل‌فهم نگاشت: **بله**.
- عدم استفادهٔ پنهان از مدل پولی، secrets امن، usage ledger با شاهد: کد تأیید شد؛ ledger زنده
  pending (نیاز به تماس free موفق).


## Provider Discovery (v1.3 capability)

Added ackend/ai/provider_catalog.py and GET /api/settings/providers/catalog (discovery only; no provider creation or network calls). Frontend Settings now lists unconfigured providers with add-draft buttons and free-policy notes. Test: 	est_provider_catalog_lists_supported_kinds.

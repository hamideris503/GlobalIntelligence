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

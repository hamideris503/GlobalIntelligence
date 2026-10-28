# AI_MODELS.md

> ثبت Providerها، مدل‌ها، نقش‌ها و عملکرد آن‌ها.
> **اصل:** هیچ Provider در منطق اصلی Hard-code نمی‌شود. همه از طریق AI Gateway.

---

## معماری

```
Application
  ↓
AI Gateway
  ↓
Provider Adapter   (mock | gemini | openai | anthropic | openrouter | …)
  ↓
Model
```

## Providerها

| Provider | Env Key | Base URL Env | Status |
|---|---|---|---|
| Mock | — | — | **پیاده‌سازی‌شده (پیش‌فرض)** |
| Gemini | `GEMINI_API_KEY` | `GEMINI_BASE_URL` | پیاده‌سازی‌شده |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_BASE_URL` | پیاده‌سازی‌شده |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` | پیاده‌سازی‌شده |
| OpenRouter | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL` | پیاده‌سازی‌شده |

> اگر کلید یک Provider نبود یا خطا داد: Provider غیرفعال می‌شود، سیستم Crash نمی‌کند، به fallback می‌رود.

---

## نقش‌های منطقی (Roles)

| Role | کاربرد | نمونه مدل (قابل تنظیم) |
|---|---|---|
| Fast Extraction | classification, extraction, tagging, dedup assist | مدل سریع/ارزان |
| Deep Analysis | geopolitical, macro, multi-source synthesis, scenario | مدل قوی |
| Critic | counter-evidence, contradiction, adversarial | مدل قوی و متفاوت |
| Report | daily/weekly/executive reports | مدل با کیفیت نوشتاری |

نگاشت Role → (Provider, Model) در `backend/ai/routing/` نگهداری می‌شود، نه در کد.

---

## وظایف LLM در برابر محاسبات Deterministic

**LLM انجام می‌دهد:** خلاصه‌سازی، طبقه‌بندی، استخراج Entity/Event/Claim،
تحلیل متن، مقایسه روایت‌ها، تحلیل شواهد/سناریو، تفسیر نتایج آماری، تحلیل
ژئوپلیتیکی/کیفی، تولید گزارش.

**LLM نباید انجام دهد (محاسبات deterministic):** Brier، Log Loss، MAE، RMSE،
Correlation، Covariance، VaR، CVaR، Monte Carlo، Probability calibration،
Statistical testing، Regression، Time series forecasting، Portfolio math.

> LLM فقط نتیجه‌ی این محاسبات را **تفسیر** می‌کند.

---

## Interface یکسان Provider (مفهومی)

```python
class AIProvider(Protocol):
    async def generate(self, prompt: str, **opts) -> AIResponse: ...
    async def structured_generate(self, prompt: str, schema: type, **opts) -> AIResponse: ...
    async def classify(self, text: str, labels: list[str], **opts) -> AIResponse: ...
    async def extract(self, text: str, schema: type, **opts) -> AIResponse: ...
    async def health(self) -> ProviderHealth: ...
```

Gateway همچنین مسئول: Fallback، Retry، Timeout، Rate limit، Structured output
(JSON Schema)، Logging، Cost/Token tracking، Model/Prompt version tracking،
Error handling، Provider health، Task-specific routing.

---

## ارزیابی مدل‌ها (Phase 36+)

برای هر (Provider, Model, Prompt Version) ثبت می‌شود:

`task, model, prompt_version, accuracy, latency, failure_rate, cost_estimate,
structured_output_success, human/evaluation score`

سپس Router (Phase 37) بر اساس عملکرد واقعی، مدل مناسب هر Task را انتخاب می‌کند.

---

## Adaptive Routing (آینده)

```
Fast Extraction  → Model A
Deep Analysis    → Model B
Critic           → Model C
Fallback         → Provider D
```

انتخاب کاملاً قابل تنظیم است و در منطق اصلی Hard-code نمی‌شود.

---

## Prompt Versioning

هر Prompt دارای نسخه است و در `backend/ai/prompts/`. هر Forecast/Analysis
نسخه‌ی Prompt خود را برای Reproducibility ثبت می‌کند.

---

## سیاست Free-Only (رایانش ابری رایگان)

> هیچ درخواست واقعی AI نباید به مدل پولی برسد. اجرای مدل محلی (Ollama،
> vLLM و مشابه) ممنوع است و اضافه نمی‌شود.

**سازوکار:** `backend/ai/free_policy.py` فهرست دقیق `(provider, model)` را
نگه می‌دارد و `AIGateway.generate` پیش از build و پیش از هر HTTP، هر نامزد
زنجیره را بررسی می‌کند. نامجاز → توقف فوری با `provider_not_allowed` یا
`model_not_allowed`؛ بدون fallback به بعدی. ورودی API، تنظیم پنل، رکورد
دیتابیس و `set_routes` همگی از همین گیت مرکزی می‌گذرند و نمی‌توانند آن را
دور بزنند. `mock` فقط در mock mode مجاز است.

**فهرست فعال/غیرفعال (آخرین بررسی: 2026-10-17):**

| Provider / Model | وضعیت | علت |
|---|---|---|
| Groq `openai/gpt-oss-20b` | ✅ فعال | سهمیه رایگان مستند (30 RPM / 1000 RPD / 8K TPM)؛ بدون آموزش روی داده |
| Cloudflare `@cf/meta/llama-3.1-8b-instruct` | ⛔ غیرفعال | مجازبودن مدل روی طرح Free تأیید نشده |
| Gemini `gemini-3.5-flash` | ⛔ غیرفعال | شروط EEA/CH/UK و کاربرد داده رایگان نیازمند شفاف‌سازی |
| OpenRouter `:free` (کلی) | ⛔ غیرفعال | فهرست چرخشی، سقف ۵۰/روز، سوییچ‌های آموزشی |
| OpenAI / Anthropic / openai_compatible | ⛔ مسدود | بدون مدرک طرح رایگان |

**تعویض provider:** فقط با فعال/غیرفعال‌کردن ورودی‌های همین فهرست (پس از
بررسی و تست آفلاین سازگاری JSON)؛ مصرف‌کنندگان Gateway بدون بازنویسی
دنبال می‌کنند. مدل جایگزین باید همان قرارداد خروجی task را نگه دارد.

**اتمام سهمیه:** `quota_exhausted` (روزانه، بدون retry بی‌فایده) متمایز از
`rate_limit` موقتی (با احترام به `Retry-After` در سقف retry مجاز) است؛
وقتی هیچ provider آزادی نماند `free_unavailable` برمی‌گردد. داده حذف
نمی‌شود (مثلاً classification در `pending` می‌ماند).

**سهمیه رایگان دائمی نیست:** هر ورودی حداکثر ۹۰ روز اعتبار دارد و پس از
انقضا خودکار مسدود می‌شود. صفحات رسمی مبنا: `console.groq.com/docs/rate-limits`،
`developers.cloudflare.com/workers-ai/platform/pricing`،
`ai.google.dev/gemini-api/docs/pricing`، `openrouter.ai/docs/api_reference/limits`.

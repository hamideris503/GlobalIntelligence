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
| Mock | — | — | **پیش‌فرض (Mock-First)** |
| Gemini | `GEMINI_API_KEY` | `GEMINI_BASE_URL` | Planned |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_BASE_URL` | Planned |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` | Planned |
| OpenRouter | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL` | Planned |

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

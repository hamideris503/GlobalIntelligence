# PHASE 06 — تکمیل زنجیرهٔ تحلیل هوشمند AI

- تاریخ: 2026-11-14
- وضعیت نهایی مرحله: **VERIFIED_COMPLETE** (یک trace کامل و قابل بازتولید از مقالهٔ واقعی)

## محیط

`MOCK_MODE=false`، `AI_DEFAULT_PROVIDER=openrouter`، `OPENROUTER_MODEL=openrouter/free`، دیتابیس `e2e_live.db`
(ساخته‌شده با Alembic) شامل ۲۰ مقالهٔ واقعی BBC World.

## مسیر اجراشده (همه با ابزارهای رسمی خود پروژه)

```
Article (BBC real)
  → domains.news.run_classify            (AI Gateway)
  → domains.news.run_backfill_routing --apply
  → POST /api/dispatch/run               (event_extraction, claim_extraction, graph_extraction, evidence_collection, claim_independence)
  → GET /api/dispatch/jobs
```

## Trace واقعی (مقاله bd11b19a…, «How telecoms upgrade work sparked US flight chaos»)

| مرحله | نتیجه | Provenance |
|---|---|---|
| classification | `done` | `provider=openrouter`, `model=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `is_mock=false`, `prompt_version=v3`, `classified_at` ثبت شد |
| domain_routing | `completed` | `screening_route=AI_GATEWAY`, `screening_reason_codes=[LOCAL_DISABLED, AI_FALLBACK]`, domain=`technology` |
| event_extraction | `completed` | ۱ event: `event_type=cyber`, action=«How telecoms upgrade work sparked US flight chaos» |
| claim_extraction | `completed` | ۵ claim با confidence (0.9–0.95) و `verification_status=single_source` |
| evidence_collection | `completed` | ۵ evidence (هر claim یک evidence متصل) |
| graph_extraction | `completed` | ۳ entity (`country:us`, `government:us officials`, `industry:telecoms`) + ۱ relationship |

نمونهٔ claimها: «US officials said flight disruptions were caused by overloaded telecom equipment»،
«flight disruptions were not caused by a cyber-attack».

## شاهد فراخوانی واقعی Provider

لاگ سرور، ۸ فراخوانی `ai.generate` با `mock=False` و مدل‌های واقعی:
`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `recursive/flint-v1.0:free`, `baidu/ernie-5.5-flash-preview:free`
با latency واقعی ۲.۲–۸.۷ ثانیه.

## نکات قرارداد

- هیچ دادهٔ ساختگی برای پر کردن صفرها تولید نشد؛ مقادیر صفر (مثل `actors` خالی) همان خروجی مدل است.
- `INSUFFICIENT_EVIDENCE` در این نمونه لازم نشد چون شواهد کافی از متن مقاله استخراج شد.
- خطاها در `article_dispatches.last_error` خالی هستند (بدون خطای پنهان‌شده).

## محدودیت‌ها

- `/api/analyses` روی Recommendation/Debate/Forecast تجمیع می‌کند و در این دیتابیس خالی بود؛ trace این مرحله از
  `article_dispatches.meta` و جدول‌های event/claim/evidence/entity استخراج شده است، نه از endpoint تحلیل.
- Screening محلی (Kev/Laya) در این اجرا `LOCAL_DISABLED` بود و مسیر AI_FALLBACK استفاده شد (طبق سیاست فعلی).

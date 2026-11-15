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
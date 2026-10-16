# REPAIR_REPORT.md — Confirmed Defects Fixed

> همه‌ی تعمیرات کوچک، هدفمند، تست‌دار و بدون migration مخرب‌اند.
> هیچ فایل کاربر/`.env`/داده حذف یا بازنویسی نشد. هیچ commit انجام نشد (طبق دستور).

## تعمیرات High

### H1 — Evidence: شکست AI دیگر done جعلی نمی‌سازد
- فایل: `domains/claims/evidence.py` (`collect_for_claim`: re-raise + بدون flag)
- رفتار قبل: exception → log → ۰ ردیف + `evidence_extracted=True` → هرگز retry، شمارش processed.
- رفتار بعد: exception بالا می‌رود → `run()` آن را failed می‌شمارد → اجرای بعد retry.
- تست: `test_evidence_failure_not_marked_done` (failed=1، flag=False، ردیف ۰).

### H2 — Evidence: انتساب per-article با article_index
- فایل‌ها: `evidence_prompts.py` (schema + prompt v2 با مقالات شماره‌دار)، `evidence.py` (`_ingest_items` per-item + fallback مستند + حذف ۲ helper مرده).
- رفتار قبل: همه به `articles[0]`.
- رفتار بعد: `article_index` معتبر → سند/منبع همان مقاله؛ نامعتبر → fallback اول + warning.
- تست: `test_evidence_attributed_by_article_index` (۲ سند متفاوت + fallback).

### H3 — Classifier: ورودی بدنه‌ی کامل سند
- فایل‌ها: `domains/news/classifier.py` (title+summary+raw_text) + prompt `v2→v3`.
- رفتار قبل: عملاً فقط title (summary در ingest تهی بود).
- تست: `test_classify_uses_document_body_when_summary_missing` (+ assert نسخه‌ی v3).
- ریسک: تغییر قرارداد ورودی؛ با نسخه‌گذاری prompt و تست golden موجود پوشش داده شد.

### H4 — Monitoring: خطای شمارش دیگر healthy نیست
- فایل‌ها: `domains/ops/service.py` (`_count → None`) + `monitoring.py` (`count_check`: None→fail).
- تست: `test_count_query_failure_is_fail_not_pass`.

## تعمیرات Medium

| # | تغییر | فایل‌ها | تست |
|---|---|---|---|
| M1 | `responseMimeType` در Gemini + `response_format` در OpenRouter | `providers/gemini.py`, `openrouter.py` | ۲ تست payload |
| M2 | guard `?fetcher=mock` با 422 در production | `routers/economic.py`, `markets.py` | ۲ تست (mock_mode=false) |
| M3 | بازه‌ی سناریو مرکزدار + assumptions | `scenarios/engine.py` | `test_scenario_interval_recentered…` |
| M4 | cooldown شامل acknowledged | `alerts/engine.py` | `test_cooldown_survives_acknowledge` |
| M5 | `VITE_API_BASE_URL` به‌صورت build-arg در prod | `frontend.prod.Dockerfile`, `docker-compose.prod.yml` | `compose config` معتبر (راستی‌آزمایی دستی) |
| M6 | همه-warn در self-eval → D | `selfeval/checks.py` | `test_overall_empty_system_is_d_not_c` |
| M7 | fail-fast: رمز DB + CORS `*`؛ حذف `/` از معافیت rate | `config.py`, `security.py` | ۲ تست امنیتی |
| M8 | root: بدون `env` + docs شرطی | `routers/health.py` | assert عدم‌نشت |
| M9 | بکاپ: `valid_target_db` + `PG_CONTAINER` + ۲۰ جدول | `scripts/db_backup.py` | ۲ تست |
| M10 | stats یکدست لاپلاس | `routers/ai_routing.py` | assert 0.6667 |
| M11 | ریسک brief فقط آخرین دوره | `briefings/daily.py` | تست ۲ دوره‌ای |
| M12 | CLI ingest هم‌فیلتر API | `domains/news/run_ingest.py` | (رفتار CLI؛ پوشش دستی) |
| M13 | warning نبود jsonschema | `classifier.py:_validate` | (مسیر import؛ بدون تست جدید) |

## تعمیرات Low

- حذف dead code: `INDEPENDENCE_CORROBORATION_THRESHOLD`، `"json"` در `__all__`، `_parse_csv_rows` (+csv/io)، `needsKey` فرانت‌اند (با `npm run build`).
- مرتب‌سازی importهای ruff --fix (۴ فایل، بدون تغییر رفتار).

## عمداً تعمیر نشد (مستند، در AUDIT_REPORT §1)

تکرار `verify_status`/UnionFind/`_safe_json`/rank/`_series_values`؛ جدول مرده‌ی `scenarios`؛
`expired`/`actual_bool` رزرو؛ تطبیق رشته‌ای نام‌ها؛ وزن‌های ثابت؛ N+1ها و loadهای O(N)؛
`_rerank` سراسری؛ `localStorage`؛ dev-root؛ staging secret مشترک.

## ریسک‌های باقی‌مانده‌ی تعمیرات

1. prompt طبقه‌بندی v3: خروجی LLM واقعی ممکن است با بدنه‌ی بلندتر کمی متفاوت شود (کیفیت، نه صحت) — با Provider واقعی باید راستی‌آزمایی شود (BLOCKED).
2. `article_index`: مدل‌های قدیمی‌تر ممکن است ایندکس ندهند → fallback اول (پوشش داده شده).
3. Evidence retry بی‌نهایت برای claim خرابِ دائمی (شمارنده‌ی attempt ندارد) — شناخته‌شده، کم‌هزینه.
4. تغییر `overall()` خودارزیابی: نمره‌ی تاریخی B قبلی با منطق جدید D می‌شد (فقط سیستم‌های تهی) — داده‌ی ذخیره‌شده بازنویسی نشد.

## فایل‌های تغییریافته (۲۴ فایل، بدون commit)

- domains: news/classifier.py, news/run_ingest.py, claims/evidence.py, claims/evidence_prompts.py, ops/service.py, ops/monitoring.py, scenarios/engine.py, alerts/engine.py, forecast/(baselines untouched), ai_routing (router untouched), briefings/daily.py, selfeval/checks.py, markets/fetchers.py, macro/fetchers.py, news/independence.py
- backend: ai/providers/gemini.py, openrouter.py, ai/prompts/classification.py, api/routers/{economic,markets,ai_routing,health}.py, core/{config,security}.py
- scripts: db_backup.py (+check_env.py یک‌خطی)
- docker: frontend.prod.Dockerfile, docker-compose.prod.yml
- apps/web: App.tsx
- tests: ۱۴ فایل (۱۸ تست جدید/تقویت‌شده)

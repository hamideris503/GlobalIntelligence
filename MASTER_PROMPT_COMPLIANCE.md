# MASTER_PROMPT_COMPLIANCE.md — Compliance Matrix

> مبنا (فایل MASTER PROMPT در repo نیست — یافته‌ی ممیزی §0):
> `ARCHITECTURE.md` + `ROADMAP.md` (۵۳ فاز) + بندهای کد + `DECISIONS.md`.
> قاعده: وجود فایل/endpoint/تست ≠ VERIFIED؛ رفتار باید اجرا و دیده شده باشد.

وضعیت‌ها: ✅ VERIFIED | 🟡 PARTIALLY | ⛔ NOT IMPLEMENTED/FAILED | 🔒 BLOCKED | ➖ N/A

## فازها (0–52)

| فاز | عنوان | پیاده‌سازی کلیدی | تست | راستی‌آزمایی مستقل | وضعیت |
|---|---|---|---|---|---|
| 0 | Spec/Architecture | ARCHITECTURE/ROADMAP/DECISIONS + بندهای کد | — (سند) | خوانده شد؛ بندها در کد ارجاع‌اند | ✅ |
| 1 | Env/Skeleton | `.env.example`, `check_env.py`, compose | `test_health.py` | اجرا شد؛ health زنده 200 | ✅ |
| 2 | Skeleton Backend/Frontend | FastAPI + React/Vite + compose | `test_health.py`, build | build موفق؛ سرو زنده | ✅ |
| 3 | PostgreSQL | ۱۵+ مدل + Alembic زنجیره‌ی خطی تک‌head | `test_models.py` | head==current زنده؛ orphan/dup=0 | ✅ |
| 4 | n8n + jobs | workflow نمونه + `/api/jobs/trigger` + `job_runs` | manual/API | ۶ workflow در n8n زنده (`list:workflow`) | ✅ |
| 5 | AI Gateway | gateway + ۵ provider + routing + fallback | `test_ai_gateway.py`, `test_providers_http.py` | fallback/mock-strip در کد + تست؛ رفتار واقعی provider 🔒 | 🟡¹ |
| 6 | Mock AI | MockProvider schema-driven | `test_mock_schema.py` | deterministic؛ فقط فیکسچر (نه رفتار محصول) | 🟡 |
| 7 | Source Registry | `Source` + CRUD `/api/sources` + seed | `test_sources.py` | ۱۹ منبع زنده | ✅ |
| 8 | Ingestion | RSS/Mock + normalizer + pipeline + CLI | `test_ingestion.py`, `test_rss.py` | ۱۳۵ سند زنده؛ واگرایی CLI/API **تعمیر شد** | ✅ |
| 9 | Dedup | MinHash/LSH/UnionFind + service | `test_dedup.py` | قطعی؛ بدون AI | ✅ |
| 10 | Classification | classifier + importance + prompt v3 | `test_classification*.py` (golden) | ورودی بدنه **تعمیر شد**؛ خروجی واقعی LLM 🔒 | 🟡¹ |
| 11 | Events | extractor + fallback سبک + API/CLI | `test_events.py` | ۷۸ رویداد زنده (تک‌مقاله‌ای بودن با mock پذیرفته) | ✅ |
| 12 | Claims | extractor SPO + fallback + API/CLI | `test_claims.py` | ۷۸ claim زنده | ✅ |
| 13 | Evidence | engine + `verify_status` + source/document | `test_evidence.py` | done-جعلی و انتساب **تعمیر شد** + ۲ رگرسیون | ✅ |
| 14 | Independence | dependency graph + Union-Find + corroborated≥۲ مستقل | `test_independence.py` | ۱۹→۱۸ گروه زنده؛ آستانه‌ی مرده حذف شد | ✅ |
| 15 | Knowledge Graph | resolution + relations + fallback | `test_graph.py` | fallback مستند؛ lookup نام‌محور پذیرفته | ✅ |
| 16 | Economic | WorldBank + upsert + API/CLI | `test_economic.py` | داده‌ی واقعی WB زنده دیده شد؛ guard اضافه شد | ✅ |
| 17 | Market | ۴ خانواده fetcher + fallback + API/CLI | `test_markets.py` | قیمت‌های واقعی زنده؛ guard اضافه شد | ✅ |
| 18 | World State | ۹ سیگنال + رژیم + snapshot | `test_worldstate.py` | snapshot واقعی (slowdown/risk_on) | ✅ |
| 19 | Memory | archive ۳ لایه + timeline + API/CLI | `test_memory.py` | ۱۳۵+۳+۳ رکورد زنده | ✅ |
| 20 | Analogue | فاصله‌ی برداری + aftermath + API/CLI | `test_analogues.py` | cosine مرکزدهی‌شده + coverage (ممیزی قبلی) | ✅ |
| 21 | Macro Engine | yoy/شتاب/z/momentum + assessment | `test_macro_engine.py` | مقادیر واقعی (inflation stable) | ✅ |
| 22 | Geopolitical | tension بازیگر + assessment | `test_geopolitics.py` | ۱ بازیگر mock صادقانه | ✅ |
| 23 | Social | mood قلمرو + assessment | `test_society.py` | skip صادقانه با mock | ✅ |
| 24 | Narrative | Union-Find + strength + API/CLI | `test_narratives.py` | ۱ روایت ۷۸ رویداده صادقانه | ✅ |
| 25 | Forecast | baselineها + Ledger | `test_forecast.py` | ۳ baseline واقعی (2.95/4.20/3.38) | ✅ |
| 26 | Ledger | scenario/status + جانشینی + active | `test_forecast.py` | ۷ active زنده | ✅ |
| 27 | Outcome | تطبیق بدون look-ahead + resolved | `test_outcome.py` | resolve واقعی 2.95 + پاک‌سازی | ✅ |
| 28 | Evaluation | Brier/LogLoss/MAE/RMSE/کالیبراسیون | `test_evaluation.py` | MAE=2.05 زنده end-to-end | ✅ |
| 29 | Tournament | رقابت + leaderboard + رکورد | `test_tournament.py` | برنده‌ی واقعی naive در تست/زنده | ✅ |
| 30 | Scenario | base/bull/bear/tail + Ledger | `test_scenarios.py` | بازه‌ی مرکزدار **تعمیر شد**؛ ۴ سناریو زنده | ✅ |
| 31 | Risk | ۸ دسته + assessment | `test_risk.py` | ۷ دسته + ۱ skip زنده | ✅ |
| 32 | Decision | قانون + Recommendation + rank | `test_decision.py` | avoid صادقانه زنده | ✅ |
| 33 | Iran Mode | لنز + تطبیق کلمه‌ای | `test_iran.py` | brief واقعی (۳ macro + بستر) | ✅ |
| 34 | Transmission | ۴ کانال + assessment | `test_transmission.py` | ۳ کانال زنده + ۱ skip | ✅ |
| 35 | Portfolio | CRUD + snapshot | `test_portfolio.py` | CRUD + حذف آبشاری زنده | ✅ |
| 36 | Model Perf | ثبت دوره‌ای + leaderboard | `test_performance.py` | skip صادقانه بدون outcome | ✅ |
| 37 | AI Router | Laplace + inject + API/CLI | `test_ai_routing.py` | زنجیره‌ی واقعی + نرخ یکدست **تعمیر شد** | ✅ |
| 38 | Audit/Replay | لاگ افزودنی + fingerprint | `test_audit.py` | match + drift-detection زنده | ✅ |
| 39 | Self Eval | ۶ چک + grade + تاریخچه | `test_selfeval.py` | نمره‌ی B واقعی؛ همه-warn→D **تعمیر شد** | ✅ |
| 40 | Dashboard | ۷ بخش + کلید + RTL | build + سرو زنده | بیلد موفق؛ صفحه سرو می‌شود | ✅ |
| 41 | Daily | خلاصه‌ی ۲۴h + Briefing | `test_briefings.py` | brief واقعی ۵۰/۵۰ + ریسک جاری **تعمیر شد** | ✅ |
| 42 | Weekly | روند/حرکت/رژیم/دلتا + Briefing | `test_weekly.py` | brief واقعی + off-by-one **تعمیر شد** | ✅ |
| 43 | Alerts | قواعد + cooldown + ack/resolve | `test_alerts.py` | trigger واقعی + cooldown ack-aware **تعمیر شد** | ✅ |
| 44 | Security | هدر/rate/fail-fast/docs | `test_security.py` | ۲۹+۱۴ مسیر 401؛ شکاف‌ها **تعمیر شد** | ✅ |
| 45 | Backup | dump/restore/verify + manifest | `test_backup.py` | چرخه‌ی کامل زنده (۱۳→۲۰ جدول)؛ injection **تعمیر شد** | ✅ |
| 46 | Docker Prod | compose prod + nginx + وریفای ایمیج | config/build/serve | بدون `.env` + non-root + fallback ✅؛ VITE arg **تعمیر شد** | ✅ |
| 47 | Staging | stack جدا + smoke + docs | `test_smoke.py` + smoke ۹/۹ | staging واقعی بالا/پایین شد؛ dev سالم | ✅ |
| 48 | VPS Deploy | automation + docs | `test_deploy.py` + dry-run | dry-run صحیح؛ اجرای زنده **انجام نشده** | 🔒 |
| 49 | 24/7 Automation | ۵ workflow + ops status | `test_n8n_workflows.py`, `test_ops.py` | import زنده هر ۵ + ops واقعی؛ هدر قدیمی‌ها **تعمیر شد** | ✅ |
| 50 | Monitoring | چک‌ها + Prometheus + workflow | `test_monitoring.py` | status=pass زنده؛ `-1→pass` **تعمیر شد** | ✅ |
| 51 | Learning | روند/نرخ/چارک + insights | `test_learning.py` | ۲ بینش واقعی | ✅ |
| 52 | Research | GraphRAG-lite + methods | `test_graphrag.py` | retrieval واقعی؛ bayesian/causal صادقانه deferred | ✅ |

¹ Phase 5/10: رفتار mock کاملاً VERIFIED؛ رفتار Provider واقعی BLOCKED (کلید معتبر نیست).

## الزامات فرافازی

| Req | انتظار | وضعیت | شواهد |
|---|---|---|---|
| R-AUTH | همه‌ی APIها به‌جز health با کلید | ✅ | ۲۹ GET + ۱۴ POST مسیر، 401 (test_security) |
| R-MOCK | mock هرگز در production واقعی استفاده نشود | ✅ | gateway strip + guard سه‌گانه (AI/fetchers) + تست‌ها |
| R-PIT | Point-in-Time (observed/recorded، look-ahead ممنوع) | ✅ | outcome/timeline/analogue گذشته‌محور + aware امن |
| R-DET | هسته‌ی قطعی بدون AI | ✅ | همه‌ی موتورها deterministic + تست مقادیر دقیق |
| R-MIG | migration خطی، تک‌head، جاری با مدل | ✅ | history خطی؛ head==current زنده؛ ۲۰+ جدول |
| R-TEST | تست رفتار واقعی، نه شکلی | 🟡 | ۴۰۰ تست؛ ~۱۰ تست شکلی نگه داشته شد (بخش 3 گزارش ممیزی) |
| R-DOCS | مستندات منطبق با واقعیت | 🟡 | PROGRESS/DECISIONS به‌روز؛ Phase 10/48 عمداً BLOCKED |
| R-BACKUP | بکاپ/بازیابی آزمون‌شده | ✅ | چرخه‌ی کامل زنده با تطابق شمارش |
| R-SEC | secret در repo/ایمیج/لاگ نیست | ✅ | grep تمیز؛ ایمیج بدون `.env`؛ اسکنر آرشیو |
| R-OPS | مانیتورینگ + health + smoke | ✅ | monitoring/metrics/smoke ۹/۹ + n8n فعال‌نشده (مستند) |
| R-REAL | یکپارچگی واقعی خارجی | 🔒 | RSS/WB/ER-API/Yahoo/gold-api زنده دیده شدند؛ LLM واقعی BLOCKED |
| R-PROD | آمادگی production | 🟡 | ایمیج/compose/fail-fast آماده؛ VPS/TLS/cron مانده (PRODUCTION_READINESS) |

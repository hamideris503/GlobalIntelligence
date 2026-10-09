# PROGRESS.md

> گزارش پیشرفت مرحله‌به‌مرحله. بعد از هر مرحله، بخش «Completed / Files changed / Tests / Known issues / Next step» ثبت می‌شود.

---

## Phase 29 — Forecast Tournament
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `backend/database/models/tournament.py`: `Tournament` (نام/اهداف/روش‌ها/leaderboard/برنده)
- migration `bb484db8621f` (up/down موقت + زنده، head=`bb484db8621f`)
- `domains/forecast/tournament.py`: `TournamentEngine` + `rank_key` مستند
- `domains/forecast/run_tournament.py`: CLI
- API: `POST /api/tournaments/run`, `GET /api/tournaments`, `GET /api/tournaments/{id}`
- `EvaluationEngine.summary` پذیرای `targets` شد تا board در scope تورنمنت باشد (نه سراسری)
- تست‌های `tests/test_tournament.py` (۶ تست)

### Tests
- `python -m pytest tests -q` → **253 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: تورنمنت واقعی بدون امتیاز → winner=None صادقانه؛ مسیر برنده با داده تستی (naive برنده) + پاک‌سازی ✅
- زنده: CLI ✅

### Known issues
- تورنمنت فقط baselineها را دارد؛ با آمدن مدل‌های جدید (ARIMA/ML) خودکار وارد رقابت می‌شوند.
- resolve فقط اهداف سررسیده را پوشش می‌دهد؛ تورنمنت روی اهداف آینده امتیازی ندارد (صادقانه).

### Next step
- Phase 30 — Scenario Engine

---

## Phase 28 — Forecast Evaluation
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/forecast/metrics.py`: توابع خالص (`value_scores`/`prob_scores` با clip/`parse_bool`/`aggregate`/`calibrate`)
- `domains/forecast/evaluation.py`: `EvaluationEngine` (امتیازدهی idempotent + خلاصه‌ی live از مقادیر خام، مستقل از run قبلی)
- `domains/forecast/run_evaluate.py`: CLI (+`--summary`/`--model`)
- API: `POST /api/evaluation/run`, `GET /api/evaluation/scores`, `GET /api/evaluation/summary`
- تست‌های `tests/test_evaluation.py` (۱۰ تست)

### Tests
- `python -m pytest tests -q` → **247 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- بدون migration (راستی‌آزمایی شد) ✅
- زنده end-to-end: resolve→evaluate→summary (MAE=2.0505) + پاک‌سازی + CLI ✅
- اصلاح حین کار: summary از مقادیر خام محاسبه می‌کند (نه فقط فیلدهای ذخیره‌شده)؛ import مرتب‌سازی ruff

### Known issues
- کالیبراسیون فقط برای پیش‌بینی‌های احتمالاتی است (هنوز تولید نمی‌شود) → جدول تهی صادقانه.
- خلاصه ذخیره نمی‌شود؛ با رشد Ledger ممکن است کند شود (فازهای بعد: materialize).

### Next step
- Phase 29 — Forecast Tournament

---

## Phase 27 — Outcome Engine
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/forecast/outcome.py`: `OutcomeEngine` + `period_start` (سال/فصل/ماه)
  - قانون ضد look-ahead: دوره‌ی سالانه‌ی جاری قابل استفاده نیست (فقط شروع دوره ≥ target)
  - نرمال‌سازی aware برای بک‌اندهای naive (درس SQLite در تست)
  - `pending()` فقط active/expired سررسیده‌ی بدون outcome؛ idempotent
- `domains/forecast/run_resolve.py`: CLI
- API: `POST /api/outcomes/resolve`, `GET /api/outcomes`, `GET /api/outcomes/pending`
- تست‌های `tests/test_outcome.py` (۸ تست)

### Tests
- `python -m pytest tests -q` → **237 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- بدون migration (۱۲ ستون برابر — راستی‌آزمایی شد) ✅
- زنده: resolve واقعی (تورم 5.0→2.95، resolved) + پاک‌سازی کامل + CLI ✅
- اصلاح حین کار: naive/aware، `session.get` با UUID، انتظار اشتباه تست (۴.۱۲→۲.۹۵ با استدلال look-ahead)

### Known issues
- actual_bool فقط برای پیش‌بینی‌های احتمالاتی (هنوز تولید نمی‌شود).
- امتیازها (brier/log_loss/خطاها) در Phase 28 پر می‌شود.

### Next step
- Phase 28 — Forecast Evaluation

---

## Phase 26 — Forecast Ledger
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- مدل Forecast: `scenario` + `status` (پیش‌فرض active) — انطباق با spec بند 40 ARCHITECTURE
- migration `cb4b37bfa856` (up/down موقت + زنده، head=`cb4b37bfa856`؛ ۵ ردیف قدیمی به active درآمدند)
- `domains/forecast/ledger.py`: `supersede_older` (خودکار در run)، `mark_superseded` (دستی)، `active_as_of` (نیازمند aware)
- engine: پارامتر `scenario` (پیش‌فرض base) + شمارش `superseded` در outcome
- API: `POST /api/forecasts/{id}/supersede` (404 دقیق)، `GET /api/forecasts/ledger/active` (422 برای naive، قبل از `/{id}` ثبت شده تا route سایه نیفتد)
- ۵ تست Ledger (جانشینی خودکار، تفکیک سناریو، ابطال دستی، active as-of، API)

### Tests
- `python -m pytest tests -q` → **229 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: ۷ active در Ledger؛ جانشینی و CLI ✅
- تصمیم مستند: ردیف‌های scenario=NULL دوره‌ی پیش‌از-سناریو می‌مانند (بازنویسی تاریخچه ممنوع)

### Known issues
- `expired` خودکار محاسبه نمی‌شود (Phase 27 Outcome)؛ فقط query و وضعیت دستی.
- سناریوهای bull/bear/tail هنوز تولیدکننده‌ی جدا ندارند (Phase 30).

### Next step
- Phase 27 — Outcome Engine

---

## Phase 25 — Forecast Engine
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/forecast/baselines.py`: سه baseline قطعی (`naive`/`historical_mean`/`random_walk`) با حداقل نقاط مستند و بازه‌ی تهی‌پذیر
- `domains/forecast/engine.py`: `ForecastEngine` (پارس هدف، سری macro/market، افق→target_date، ثبت Ledger با data_version/assumptions/evidence)
- `domains/forecast/run_forecast.py`: CLI
- API: `POST /api/forecasts/run`, `GET /api/forecasts`, `GET /api/forecasts/{id}` (404 دقیق)
- تست‌های `tests/test_forecast.py` (۱۱ تست)

### Tests
- `python -m pytest tests -q` → **224 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- بدون migration (۱۸ ستون جدول با مدل برابر — راستی‌آزمایی شد) ✅
- زنده: ۳ baseline روی تورم آمریکا + ۱ روی WTI و XAUUSD + CLI ✅
- اصلاح حین کار: تست بازه با تفاضل ثابت (واریانس صفر → None) + `strict=False` در zip

### Known issues
- بازه با افق مقیاس نمی‌شود (v1 ساده‌شده و ثبت‌شده در assumptions).
- مدل‌های ARIMA/ETS/Theta/ML/Bayesian به فازهای بعد موکول شد (طبق ROADMAP).

### Next step
- Phase 26 — Forecast Ledger

---

## Phase 24 — Narrative Engine
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/narratives/analytics.py`: توابع خالص (`linked`/`strength`/`stance_split`/`build_title`/`confidence_for`/`UnionFind`)
- `backend/database/models/narrative.py`: `Narrative` با یکتایی (period, signature)
- migration `c5ae5339ede9`: جدول `narratives` (up/down موقت + زنده، head=`c5ae5339ede9`)
- `domains/narratives/engine.py`: `NarrativeEngine` (ویژگی از مقالات+actors، خوشه‌بندی، upsert idempotent)
- `domains/narratives/run_build.py`: CLI
- API: `POST /api/narratives/build`, `GET /api/narratives`, `GET /api/narratives/{id}` (404 دقیق)
- تست‌های `tests/test_narratives.py` (۹ تست)

### Tests
- `python -m pytest tests -q` → **213 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: ۱ روایت (۷۸ رویداد، ۱۳۵ مقاله، strength=1.0 — صادقانه برای mock) + idempotent + CLI ✅

### Known issues
- با mock همه‌ی رویدادها یک خوشه‌اند؛ با داده واقعی روایت‌های متعدد و معنادار.
- برچسب عنوان آماری است، نه زبانی (تفسیر LLM در آینده).

### Next step
- Phase 25 — Forecast Engine

---

## Phase 23 — Social Intelligence
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/society/analytics.py`: تابع خالص `mood` (میانگین احساس تهی‌پذیر، سهم ناآرامی، stance_mix) + `confidence_for`؛ بدون مقاله → None
- `backend/database/models/social_assessment.py`: `SocialAssessment` با یکتایی (scope_type, scope, period)
- migration `bdd7eabe4da2`: جدول `social_assessments` (up/down موقت + زنده، head=`bdd7eabe4da2`)
- `domains/society/analysis.py`: `SocialEngine` (فقط مقالات done؛ قلمرو topic نرمال‌شده + country؛ upsert idempotent)
- `domains/society/run_analyze.py`: CLI
- API: `POST /api/society/analyze`, `GET /api/society/assessments`, `GET /api/society/mood`
- تست‌های `tests/test_society.py` (۸ تست)

### Tests
- `python -m pytest tests -q` → **204 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: مقالات mock بدون topic/country → صادقانه skipped=1 (نه fabrication) ✅
- زنده: مسیر واقعی با ۱ مقاله تستی → ۳ قلمرو ذخیره شد، سپس کامل پاک‌سازی شد (articles=135 دست‌نخورده) ✅
- زنده: CLI ✅

### Known issues
- با mock هیچ قلمرویی ساخته نمی‌شود؛ با Provider واقعی topics/country پر می‌شود.
- احساس مقالات از طبقه‌بندی می‌آید؛ سوگیری مدل طبقه‌بندی منتقل می‌شود.

### Next step
- Phase 24 — Narrative Engine

---

## Phase 22 — Geopolitical Engine
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/geopolitics/analytics.py`: تابع خالص `tension` (v1) + `confidence_for`؛ n=0 → None (بدون assessment)
- `backend/database/models/geopolitical_assessment.py`: `GeopoliticalAssessment` با یکتایی (actor, period)
- migration `5cf8f59a349b`: جدول `geopolitical_assessments` (up/down موقت + زنده، head=`5cf8f59a349b`)
- `domains/geopolitics/analysis.py`: `GeopoliticalEngine` (گروه‌بندی بازیگر، سهم مناقشه از CONFLICT_TYPES، یال‌های گراف بدون double-count، period ماه جاری، upsert idempotent)
- `domains/geopolitics/run_analyze.py`: CLI
- API: `POST /api/geopolitics/analyze`, `GET /api/geopolitics/assessments`, `GET /api/geopolitics/tensions`
- تست‌های `tests/test_geopolitics.py` (۹ تست)

### Tests
- `python -m pytest tests -q` → **196 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: ۱ بازیگر (mock: tension=0.2، فقط حجم — صادقانه) + idempotent + CLI ✅
- اصلاح حین کار: double-count نام‌های موجودیت در sanction_links (تست پیداش کرد)

### Known issues
- با mock فقط یک بازیگر «mock» است؛ با Provider واقعی بازیگران واقعی تفکیک می‌شوند.
- تطبیق نام بازیگر↔موجودیت رشته‌ای است (fuzzy در آینده).

### Next step
- Phase 23 — Social Intelligence

---

## Phase 21 — Macro Engine
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- `domains/macro/analytics.py`: توابع خالص (`yoy`/`acceleration`/`z_score`/`momentum_label`/`confidence_for`/`analyze_series`)
  - yoy کسری دو مشاهده‌ی آخر؛ شتاب = اختلاف yoy؛ z نیازمند ≥۳ نقطه و واریانس مثبت (وگرنه None)؛ momentum=clamp(z/2) با برچسب accelerating/stable/decelerating/unknown؛ confidence از تعداد نقاط (0.1/0.4/0.6/0.8)
- `backend/database/models/macro_assessment.py`: `MacroAssessment` با یکتایی (indicator, country, period)
- migration `ce70a0fa41c3`: جدول `macro_assessments` (up/down روی DB موقت + اعمال زنده، head=`ce70a0fa41c3`)
- `domains/macro/analysis.py`: `MacroEngine` (گروه‌بندی سری‌ها، تحلیل، upsert idempotent، فیلتر indicator/country)
- `domains/macro/run_analyze.py`: CLI
- API: `POST /api/macro/analyze`, `GET /api/macro/assessments`, `GET /api/macro/overview?country=`
- تست‌های `tests/test_macro_engine.py` (۱۰ تست)

### Tests
- `python -m pytest tests -q` → **187 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: ۲ سری تحلیل شد (USA inflation@2024: mom=-0.28 stable؛ IRN gdp@2025: mom=-0.70 decelerating) ✅
- زنده: اجرای دوباره idempotent (۲ duplicate) + overview + CLI ✅

### Known issues
- سری‌های کم‌نقطه (۱–۲) yoy/شتاب تهی دارند و momentum ناشناخته است — صادقانه ثبت می‌شود، نه حدس.
- دوره‌ها رشته‌ای مقایسه می‌شوند (مرتب نزولی)؛ فرمت دوره باید یکدست باشد (در seed فعلی هست).

### Next step
- Phase 22 — Geopolitical Engine

---

## Audit Fix — یافته‌های ممیزی Phase 18/20 (بدون شروع Phase 21)
**تاریخ:** 2026-10-09
**وضعیت:** DONE

### Completed
- **Cosine معنایی شد** (`domains/analogue/similarity.py`): مرکزدهی حول 0.5 داخل `cosine_distance`؛ خنثی↔خنثی → 0؛ خنثی↔جهت‌دار → 1.0؛ `normalize_euclidean` با `sqrt(9/n)`؛ `masked_deltas`؛ `center`/`N_DIMS`/`NEUTRAL` عمومی شدند.
- **پوشش no_data** (`domains/analogue/engine.py`): خواندن `value_metadata`؛ بُعد معتبر = metadata موجود + method != no_data + confidence ≥ 0.3؛ مقایسه فقط ابعاد مشترک معتبر؛ حداقل ۳ بُعد وگرنه 422 صریح؛ هر hit دارای `compared_dims`/`coverage`؛ outcome دارای `valid_dims`/`min_valid_dims`.
- **Drawdown پنجره‌دار** (`domains/worldstate/builder.py`): سقف ۲۵۲ روز اخیر، query محدود ۳۰۰ رکورد مرتب؛ <۲ مقدار → None؛ ثابت‌های `DRAWDOWN_WINDOW_DAYS`/`DRAWDOWN_MAX_POINTS` مستند.
- **Schema API**: `AnalogueHitRead` += compared_dims/coverage؛ `AnalogueOutcomeRead` += valid_dims/min_valid_dims (افزایشی، سازگار).
- **امنیت**: تأیید شد هر ۱۴ router غیر-health با `require_api_key` محافظت می‌شوند؛ بدون کلید → 401؛ health عمومی 200؛ `.env.example` فقط placeholder؛ تغییری لازم نبود.
- **آرشیو تمیز**: `scripts/build_clean_archive.ps1` (اسکن secret بدون چاپ مقدار + راستی‌آزمایی)؛ خروجی `J:\Documents\GlobalIntelligence-clean-20261009-0205.zip` با ۲۴۶ فایل، بدون `.env`/`.git`/`node_modules`/`.venv`/cache؛ فقط `.env.example`؛ فایل `.env` کاربر دست‌نخورده.
- **قابل‌بازتولید**: `npm ci` + `npm run build` موفق (۱۶.۲۹ ثانیه)؛ `docker compose config` معتبر؛ backend بازسازی و healthy با migration head `672f88b5d692`.

### Tests
- `python -m pytest tests -q` → **177 passed** (۱۶۲ قبلی + ۱۵ جدید) ✅
- `ruff check backend domains tests` → All checks passed ✅
- تست‌های جدید: level-shift کسینوسی، خنثی کامل/نزدیک صفر، no_data در برابر neutral واقعی، confidence پایین، پوشش ناکافی (422)، ابعاد متفاوت (نرمال‌سازی)، سقف پنجره/ترتیب/کمبود داده SPX، خطاهای API ✅
- زنده: analogues با compared_dims=7/coverage=0.778 (دو بُعد no_data صادقانه گزارش شد، قبلاً ۹/۱.۰ بود) ✅

### Known issues
- وزن یکسان ابعاد (v1) و آستانه‌های ثابت (0.3/۳ بُعد/۲۵۲ روز) — وزن‌دهی تطبیقی به آینده موکول شد.
- `.env` محلی کاربر دارای مقادیر واقعی احتمالی است و در RAR قدیمی بوده؛ طبق دستور، کلیدها را بررسی/باطل کنید (من مقادیر را نمی‌خوانم و چاپ نمی‌کنم).

### Next step
- Phase 21 — Macro Engine (شروع نشده ⛔)

---

## Phase 20 — Historical Analogue
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/analogue/similarity.py`: توابع خالص (`to_vector`/`euclidean`/`cosine_distance`/`similarity`/`deltas`)؛ None→0.5 خنثی
- `domains/analogue/engine.py`: `AnalogueService`
  - مرجع مشخص یا آخرین snapshot؛ فقط گذشته (captured_at قدیمی‌تر)؛ top_k؛ دو متریک
  - `aftermath`: snapshotهای بعدی + رویدادهای layer=event حافظه بعد از آنالوگ
- `domains/analogue/run_analogues.py`: CLI (حالت analogues و aftermath)
- API: `GET /api/analogues` (422 متریک نامعتبر، 404 مرجع ناموجود)، `GET /api/analogues/{id}/aftermath`
- تست‌های `tests/test_analogues.py` (۱۲ تست)

### Tests
- `python -m pytest tests -q` → **162 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: ۲ آنالوگ similarity=1.0 + deltas صفر ✅
- زنده: aftermath (۱ snapshot بعدی، ۰ رویداد بعدی — درست، چون رویدادها قبل‌اند) + cosine + CLI ✅

### Known issues
- با ۳ snapshot نزدیک‌به‌هم، آنالوگ‌ها بدیهی‌اند؛ با تاریخچه‌ی بلندتر معنادار می‌شوند (هر build جدید تاریخچه می‌سازد).
- وزن یکسان هر ۹ سیگنال (v1)؛ وزن‌دهی تطبیقی در فازهای بعدی.

### Next step
- Phase 21 — Macro Engine

---

## Phase 19 — Historical Memory
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `backend/database/enums.py`: `MemoryLayer` (۷ لایه؛ raw/event/state فعال، بقیه رزرو)
- `backend/database/models/memory.py`: `MemoryRecord` با UniqueConstraint (layer, ref_type, ref_id) + ایندکس‌های layer/ref_id/observed_at
- migration `672f88b5d692`: جدول `memory_records` (up/down روی DB موقت + اعمال زنده، head=`672f88b5d692`)
- `domains/memory/service.py`: `HistoricalMemoryService`
  - `event_score` = 0.5*surprise + 0.5*min(1, articles/5)، آستانه‌ی 0.3
  - raw: importance≥7؛ state: همه‌ی snapshotها
  - `timeline(as_of)`: «در زمان T چه می‌دانستیم؟» + فیلتر لایه؛ `as_of` naive → 422
- `domains/memory/run_archive.py`: CLI
- API: `POST /api/memory/archive`, `GET /api/memory/timeline`, `/stats`, `/records`
- تست‌های `tests/test_memory.py` (۹ تست)

### Tests
- `python -m pytest tests -q` → **150 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: archive → ۱۳۵ raw + ۳ event + ۳ state، ۰ failed ✅
- زنده: timeline گذشته=۰، اجرای دوباره=۱۴۱ duplicate (idempotent) ✅
- زنده: CLI ✅

### Known issues
- با mock، فقط ۳ رویداد از ۷۸ آستانه را رد کردند (surprise تهی)؛ با Provider واقعی پوشش بهتر می‌شود.
- لایه‌های forecast/outcome/model/decision رزرو است (فازهای ۲۵–۳۶).

### Next step
- Phase 20 — Historical Analogue

---

## Phase 18 — World State
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/worldstate/signals.py`: ۹ تابع سیگنال خالص و قطعی (0..1، خنثی=0.5) + `macro_regime`/`market_regime`
  - نگاشت‌های v1 مستند: GDP YoY، CPI/10، نقدینگی YoY، میانگین بازده/افت، ترکیب مناقشه/غافلگیری، باند نفت ۵۰–۱۵۰، تراز تجاری، سهم رویدادی
  - نبود داده → 0.5 با confidence پایین و method=`no_data` (بدون عدد جعلی)
- `domains/worldstate/builder.py`: `WorldStateBuilder`
  - ورودی‌ها: macro_observations + market_observations + events/claims/articles
  - YoY تک‌کشوری (ترجیح USA) تا ترکیب کشورها خراب نشود
  - هر build یک snapshot جدید (State Memory by design) با value_metadata کامل
- `domains/worldstate/run_build.py`: CLI
- API: `POST /api/world-state/build`, `GET /api/world-state/current` (404 اگر snapshot نباشد), `GET /api/world-state/history`
- تست‌های `tests/test_worldstate.py` (۱۰ تست: نگاشت‌ها، رژیم‌ها، builder واقعی، تک‌کشوری، API)

### Tests
- `python -m pytest tests -q` → **141 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: snapshot واقعی (macro=slowdown، market=risk_on، inflation=0.295، energy=0.4758، conf=0.5) ✅
- زنده: current/history/CLI ✅
- یافته‌ی ممیزی میانی: ستون‌های `captured_at`/`confidence` از قبل در جدول بودند (خروجی psql قبلاً truncate شده بود) → migration اضافی حذف شد، بدون drift ✅

### Known issues
- با داده‌ی mock، سیگنال‌های رویدادی کم‌اطلاع‌اند (political/social=0.2)؛ با Provider واقعی معنادار می‌شوند.
- GDP تک‌کشوری است (ترجیح USA)؛ میانگین جهانی وزنی در فازهای بعدی.

### Next step
- Phase 19 — Historical Memory

---

## Phase 17 — Market Data
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/markets/fetchers.py`: کاتالوگ ۱۳ نماد (`SYMBOLS`) + ۵ fetcher رایگان بدون کلید
  - FX: `ErApiFxFetcher` (open.er-api.com، primary) + `EcbFxFetcher` (XML رسمی ECB، fallback)
  - طلا/نقره: `GoldApiFetcher` (gold-api.com: XAU/XAG)
  - نفت/سهام/اوراق/کالا: `YahooFetcher` (v8 chart: CL=F/BZ=F/GC=F/SI=F/AAPL/^GSPC/^TNX/NG=F/HG=F)
  - `MockFetcher` (deterministic برای آفلاین)
- `domains/markets/engine.py`: `MarketDataService`
  - زنجیره‌ی primary→fallback برای هر نماد؛ خطای هر نماد ایزوله
  - upsert idempotent در `MarketObservation` بر اساس (symbol, observed_at, source_name) — بدون migration جدید
- `domains/markets/run_fetch.py`: CLI (`--symbol`, `--asset-class`, `--all`, `--fetcher`)
- API: `POST /api/markets/fetch`, `GET /api/markets/observations`, `/symbols`, `/latest`
- تست‌های `tests/test_markets.py` (۱۱ تست)

### Tests
- `python -m pytest tests -q` → **131 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- زنده: هر ۱۳ نماد fetch موفق، ۰ failed (XAU=4131.40، WTI=91.19، EURUSD=1.12، US10Y=5.23٪) ✅
- زنده: اجرای دوباره mock → duplicate (idempotent) ✅
- زنده: `GET /api/markets/latest` هر ۱۳ نماد با source ✅
- زنده: CLI ✅؛ ردیف‌های mock تستی از DB زنده پاک شد ✅

### Audit note (Phase 0–16)
- ممیزی کامل انجام شد: ۱۲۰ تست پاس، ruff تمیز، migration head درست، APIهای همه‌ی فازها زنده OK
- اصلاح: README/ROADMAP نشانگر کهنه‌ی فاز ۱۵ → ۱۶ (commit `b0c8d1c`)
- منابع ناموفق مستند شد: Frankfurter (Cloudflare block)، Stooq (JS challenge)، FRED/EIA (نیازمند کلید)

### Known issues
- Frankfurter و Stooq از داخل شبکه مسدود/غیرقابل دسترس‌اند؛ جایگزین‌ها (er-api/ECB/Yahoo/gold-api) تأیید زنده شدند.
- Yahoo Finance بدون قرارداد رسمی است؛ fallback و ایزولاسیون خطا برای همین طراحی شد.

### Next step
- Phase 18 — World State

---

## Phase 16 — Economic Data
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `backend/database/enums.py`: `EconomicIndicator` (inflation/gdp/unemployment/interest_rate/trade_balance/liquidity) + `DataFrequency`
- `backend/database/models/market.py`: فیلدهای `series_id` و `meta` (JSON) روی `MacroObservation`
- `domains/macro/fetchers.py`: `WorldBankFetcher` (API رایگان بانک جهانی، بدون کلید) + `MockFetcher` (deterministic)
  - نگاشت شاخص‌ها به کدهای بانک جهانی: `FP.CPI.TOTL.ZG` (inflation)، `NY.GDP.MKTP.CD` (gdp)، `SL.UEM.TOTL.ZS` (unemployment)، `FR.INR.RINR` (interest_rate)، `NE.RSB.GNFS.ZS` (trade_balance)، `LTDT.DOMS.CD` (liquidity)
- `domains/macro/engine.py`: `EconomicDataService`
  - fetch → normalize → upsert idempotent بر اساس UniqueConstraint (indicator, country, period, source_name)
  - شمارش stored/duplicates/failed/errors
- `domains/macro/run_fetch.py`: CLI (`--indicator`, `--country`, `--all`, `--fetcher`)
- migration `9800836e7fcc`: افزودن `series_id` + `meta` + ایندکس
- API: `POST /api/economic/fetch`, `GET /api/economic/observations`, `/indicators`, `/latest`
- تست‌های `tests/test_economic.py` (۹ تست)

### Tests
- `python -m pytest tests -q` → **120 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- تست‌های موردی: upsert idempotent، ذخیره‌ی series_id/meta، چند شاخص×کشور، API fetch/observations/indicators/latest ✅

### Known issues
- در حالت Mock همه‌ی مقادیر deterministic و ثابت‌اند؛ داده‌ی واقعی فقط با `WorldBankFetcher` (اینترنت لازم).
- بسیاری از شاخص‌های بانک جهانی `annual` هستند؛ فرکانس ماهانه/فصلی در فازهای بعدی.

### Next step
- Phase 17 — Market Data

---

## Phase 15 — Knowledge Graph
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/graph/prompts.py`: prompt نسخه‌دار `EXTRACT_RELATIONS` v1 + `RELATIONS_SCHEMA` (enum از `RelationType`)
- `domains/graph/engine.py`: `KnowledgeGraphEngine`
  - Entity resolution: نام نرمال‌شده (`casefold`) به‌عنوان identity؛ upsert بر اساس نام، ارتقای نوع از `other` به نوع مشخص، ثبت aliases
  - استخراج رابطه با AI (structured JSON) از `actors` + `Article.entities` + متن رویداد
  - اعتبارسنجی روابط (موجودیت ناشناخته/رابطه نامعتبر/خودارجاع → رد با شمارش `rejected`)
  - fallback هم‌رویدادی (`affects`) در نبود رابطه‌ی معتبر
  - idempotency با `Event.graph_extracted` و تقویت وزن/اعتماد یال تکراری
- فیلد `EntityRelationship.confidence` + فیلد `Event.graph_extracted` + migration `34b4e7f87ba7`
- `domains/graph/run_graph.py`: CLI
- API: `POST /api/graph/extract`, `GET /api/graph/entities`, `/entities/{id}`, `/relationships`, `/neighbors/{id}`
- تست‌های `tests/test_graph.py` (۹ تست)

### Tests
- `python -m pytest tests -q` → **111 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- migration `34b4e7f87ba7`: upgrade/downgrade روی DB موقت + اعمال روی DB اصلی ✅
- زنده: رویداد Fed → Entity `Federal Reserve (central_bank)` و `US Dollar (currency)` + رابطه `affects` ✅
- زنده: اجرای دوباره idempotent (`entities_created=0`) ✅
- زنده: `GET /api/graph/neighbors/{id}` یال خروجی، entity 404، CLI ✅

### Known issues
- با Mock همه‌ی موجودیت‌ها `"mock"` می‌شوند، پس گراف معنادار نیازمند Provider واقعی است (fallback فقط با ≥۲ موجودیت متمایز کار می‌کند).
- entity resolution فعلاً نام‌محور است؛ fuzzy/embedding-based در فازهای بعدی.

### Next step
- Phase 16 — Economic Data

---

## Phase 14 — Source Independence
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- مدل `SourceDependency` + جدول `source_dependencies` (یال وابستگی خودارجاع، `kind`/`weight`/`detected_by`، یکتایی جفت)
- فیلدهای استقلال روی `Claim`: `supporting_source_count` (mention)، `independent_source_count` (تأیید مستقل)، `source_independence` (نسبت 0..1)
- `domains/news/independence.py`:
  - `SourceIndependenceEngine.build_groups` → گراف وابستگی (یال‌های ثبت‌شده + heuristic هم‌دامنه) + Union-Find
  - نماینده‌ی هر گروه = بالاترین credibility سپس independence (deterministic)
  - `compute_for_claim` → فروکاست منابع وابسته به منبع مستقل + نسبت استقلال
  - `_refresh_status` → `corroborated` فقط با ≥۲ منبع مستقل (نه صرفاً ≥۲ mention)
  - `SourceDependencyService` → CRUD روی یال‌ها (idempotent)
- `domains/news/run_independence.py`: CLI
- API: `POST /api/independence/run`, `GET/POST/DELETE /api/independence/dependencies`, `GET /api/independence/groups`
- فیلدهای استقلال در پاسخ `GET /api/claims`
- migration `cb46c0938264` (up/down روی PostgreSQL واقعی تست شد)
- تست‌های `tests/test_independence.py` (۹ تست)

### Tests
- `python -m pytest tests -q` → **102 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- migration `cb46c0938264`: upgrade/downgrade روی DB موقت + اعمال روی DB اصلی ✅
- زنده: ۱۹ منبع → ۱۸ گروه (ECB هم‌دامنه فروکاست شد)؛ ۳ Claim → `corroborated` با `independent=18`, `independence=0.9474` ✅
- زنده: افزودن وابستگی دستی → `groups` ۱۸→۱۷؛ حذف → 204؛ self-dependency → 400 ✅

### Known issues
- heuristic وابستگی فعلاً هم‌دامنه‌محور است؛ syndication/ownership واقعی نیاز به داده‌ی بیرونی دارد (یال دستی پشتیبانی می‌شود).
- با Mock، `supporting_source_count` بالا است چون همه‌ی مقالات mock از منابع متنوع‌اند؛ با Provider/داده‌ی واقعی معنادار می‌شود.

### Next step
- Phase 15 — Knowledge Graph (done in Phase 15)

---

## Phase 13 — Evidence Engine
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/claims/evidence_prompts.py`: prompt نسخه‌دار `EXTRACT_EVIDENCE` v1 + `EVIDENCE_SCHEMA`
  (enum برای `direction`: `supports`/`contradicts`)
- `domains/claims/evidence.py`: `EvidenceEngine`
  - `collect_for_claim` → داده‌ی نامزد از مقالات همان Event، استخراج ساختاریافته با AI Gateway
  - `_ingest_items` → ساخت `Evidence` معتبر + شمارش و لاگ موارد ردشده (`rejected`)
  - `verify_status(supports, contradicts)` ماتریس قطعی: unverified/single_source/corroborated/contradicted/disputed
  - پر کردن `source_id` و `document_id` برای استقلال منابع (موردنیاز Phase 14)
  - idempotency با `claim.evidence_extracted`
- فیلد `Claim.evidence_extracted` + migration `9b2bac1ae190` (با `server_default="false"`)
- `domains/claims/run_evidence.py`: CLI
- API: `POST /api/claims/evidence` (+ `rejected` در پاسخ)، evidence در `GET /api/claims`، `GET /api/claims/{id}/evidence`
- رفع باگ Mock Provider: `_mock_from_schema` حالا `const`/`enum`/`default`/`anyOf`/`oneOf`/`minimum`/`maximum`/`minItems` را رعایت می‌کند
- تست‌های `tests/test_evidence.py` (۷) و `tests/test_mock_schema.py` (۱۷)
- تست چندمنبعی در `tests/test_ingestion.py` (یک آیتم از دو منبع → ۲ سند)

### Tests
- `python -m pytest tests -q` → **93 passed** ✅
- `ruff check backend domains tests` → All checks passed ✅
- migration `9b2bac1ae190`: downgrade -1 و upgrade head روی PostgreSQL واقعی ✅
- زنده: ۳ Claim → ۳ Evidence (`direction=supports`، `source_id` پر)، `verification_status=single_source` ✅

### Known issues
- با Mock Provider مقادیر نمایشی‌اند (`mock`) جز فیلدهای schema-driven.
- استخراج/شواهد هنوز همگام است.
- `mypy` (خارج از CI) چند خطای type دارد.

### Next step
- Phase 14 — Source Independence (تشخیص وابستگی منابع) → انجام شد در فاز ۱۴
- Phase 15 — Knowledge Graph

---

## Phase 12 — Claim Extraction
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/claims/prompts.py`: prompt نسخه‌دار `EXTRACT_CLAIMS` v1 + `CLAIMS_SCHEMA`
- `domains/claims/extractor.py`: `ClaimExtractor` — استخراج Claim اتمی از متن مقالات یک Event،
  یک‌بار به‌ازای هر رویداد (`claims_extracted`)، fallback سبک در نبود AI
- فیلد `Event.claims_extracted` + migration `f6e19dcde0b6`
- CLI: `domains/claims/run_extract.py`
- API: `POST /api/claims/extract`, `GET /api/claims`
- تست‌های `tests/test_claims.py` (۵ تست)

### Files changed
- `domains/claims/{__init__,prompts,extractor,run_extract}.py`
- `backend/api/routers/claims.py`, `backend/main.py`
- `backend/database/models/event.py`, `db/migrations/versions/f6e19dcde0b6_*.py`
- `tests/test_claims.py`

### Tests
- `python -m pytest tests -q` → **68 passed در ~1.3s** ✅
- `ruff check` → All checks passed ✅
- migration `f6e19dcde0b6` روی PostgreSQL واقعی ✅
- زنده: ۳ رویداد → ۳ Claim؛ اجرای دوباره idempotent ✅

### Known issues
- با Mock Provider مقادیر Claim نمایشی‌اند (`mock`).
- Evidence در Phase 13 ساخته شد (`domains/claims/evidence.py`).
- استخراج هنوز همگام است.

### Next step
- Phase 13 — Evidence Engine (supporting + contradicting evidence)

---

## Phase 11 — Event Extraction
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/events/prompts.py`: prompt نسخه‌دار `EXTRACT_EVENT` v1 + `EVENT_SCHEMA`
- `domains/events/extractor.py`: `EventExtractor` — گروه‌بندی بر اساس `duplicate_cluster`،
  استخراج ساختاریافته با AI Gateway، fallback سبک در نبود AI
- اتصال مقالات به رویداد (`event_id`, `event_cluster`) و ثبت `event_metadata`
- `domains/events/run_extract.py`: CLI
- API: `POST /api/events/extract`, `GET /api/events`
- migration `f58aab369371` (اضافه‌شدن `events.event_metadata`)
- تست‌های `tests/test_events.py` (۵ تست)
- **Phase 10 validation**: `tests/test_classification_golden.py` با Provider واقع‌گرایانه

### Files changed
- `domains/events/{__init__,prompts,extractor,run_extract}.py`
- `backend/api/routers/events.py`, `backend/main.py`
- `backend/database/models/event.py`, `db/migrations/versions/f58aab369371_*.py`
- `domains/news/classifier_schema.py` (historical_significance دیگر از LLM خواسته نمی‌شود)
- `tests/test_events.py`, `tests/test_classification_golden.py`

### Tests
- `python -m pytest tests -q` → **63 passed در ~1s** ✅
- `ruff check` → All checks passed ✅
- migration `f58aab369371` روی PostgreSQL واقعی ✅
- pipeline زنده: ingest(19 منبع) → dedup → classify(60) → events(3 رویداد، 60 مقاله متصل) ✅
- golden: importance در بازه‌های مختلف (نه همه ۱۰)، country ذخیره شود، meta ثبت شود ✅

### Known issues
- با Mock Provider مقادیر رویداد نمایشی‌اند (`event_type=mock`)؛ با Provider واقعی معنادار می‌شوند.
- استخراج رویداد هنوز همگام است (انتقال به workers در TODO).
- تقسیم یک خوشه‌ی بزرگ به چند رویداد بر اساس نام‌گذاری وابستگی به AI دارد؛ فعلاً یک خوشه = یک رویداد.

### Next step
- Phase 12 — Claim Extraction (Event/Article → Claims)

---

## Phase 10 fix round — رفع اشکالات بازبینی (P0/P1)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed (P0)
- **P0-1:** مسیریابی Gateway اصلاح شد؛ mock در production حذف و `is_mock` اضافه شد؛ classifier mock را در production رد می‌کند.
- **P0-2:** `feed_url`/`endpoint_config` به Source؛ `/api/ingest/all` فقط منابع rss با feed_url را در حالت واقعی برمی‌دارد؛ ۵ منبع خبری RSS واقعی به seed اضافه شد؛ RSS با feedparser + fixture تست شد.
- **P0-3:** ذخیره‌ی همه‌ی اسناد؛ یکتایی فقط درون منبع `(source_id, hash, content_hash)`؛ افزایش revision؛ FK به RESTRICT.
- **P0-4:** پرامپت v2 با ابعاد importance اجباری + prompt-injection guard + `<article>`؛ اعتبارسنجی jsonschema؛ فیلتر topics؛ clamp sentiment/confidence؛ ذخیره‌ی country و classification_meta؛ وضعیت/تلاش/خطا؛ novelty و historical_significance deterministic.
- **P0-5:** احراز هویت `X-API-Key`؛ validator production (fail-fast)؛ حذف metadata از API عمومی و سقف پیام/tokens.

### Completed (P1 برگزیده)
- `available_at = retrieved_at` (رفع look-ahead) + علامت‌گذاری تاریخ آینده.
- `raw_payload` نسخه‌ی خام اصلی (بند ۱۹).
- LSH به 32×2 (recall بهتر)؛ اسناد کوتاه/خالی از MinHash کنار گذاشته شدند؛ شناسه‌ی خوشه قطعی (min id).
- savepoint به‌ازای هر آیتم؛ ثبت last_success/last_error منبع هنگام ingestion.
- کلید Gemini در هدر `x-goog-api-key` (نه URL).
- n8n به `2.42.4` pin شد؛ `N8N_BASIC_AUTH_*` حذف؛ پورت‌ها روی 127.0.0.1؛ compose با `${VAR:?}`.
- entrypoint در staging/production fail-fast؛ کاربر غیر root در Dockerfile.
- timeout از تنظیمات (نه ثابت).
- تست‌ها سریع‌ون‌سبک (۱ ثانیه) + fixture RSS/Atom + تست provider با MockTransport + رفع isolation با conftest.

### Files changed
- `backend/ai/{gateway/gateway.py,routing/router.py,schemas/types.py,providers/*}`
- `backend/core/config.py`, `backend/auth/deps.py`, `backend/main.py`, `backend/api/*`
- `domains/news/{fetchers,normalizer,ingestion,classifier,classifier_schema,dedup,dedup_service,source_registry}.py`
- `backend/database/models/{document,source,article}.py`, `db/migrations/versions/69c88e2ff7c5_*.py`, `db/seed/sources.py`
- `docker-compose.yml`, `docker/backend.Dockerfile`, `docker/backend-entrypoint.sh`, `.env.example`
- `tests/{conftest,test_rss,test_providers_http,test_ai_gateway,test_classification,test_dedup,test_health}.py`, `tests/fixtures/*`
- `LICENSE`, `.github/workflows/ci.yml`, README/TASKS/DECISIONS

### Tests
- `python -m pytest tests -q` → **57 passed in ~1s** ✅
- migration `69c88e2ff7c5` upgrade/downgrade روی PostgreSQL واقعی ✅
- احراز هویت: بدون کلید 401، با کلید 200، `/health` باز ✅
- همه‌ی منابع ذخیره می‌شوند: ۶۰ سند از ۲۰ منبع ✅
- `is_mock:true` در پاسخ mock ✅

### Known issues (باقی‌مانده برای فازهای بعد)
- تست‌ها هنوز روی SQLite اجرا می‌شوند (CI روی PostgreSQL اضافه شد).
- endpointهای سنگین هنوز همگام‌اند (انتقال به workers در TODO).
- topics/entities هنوز Text هستند (JSONB در TODO).
- اجرای واقعی با Provider واقعی/اینترنت هنوز در این محیط ممکن نشد.

### Next step
- Phase 10 (redo): اجرای واقعی کوچک با یک Provider واقعی؛ سپس Phase 11

---

## Phase 10 — Article Classification
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `backend/ai/prompts/classification.py`: `CLASSIFY_ARTICLE`, `EXTRACT_ENTITIES` (نسخه‌دار)
- `domains/news/classifier_schema.py`: `CLASSIFY_SCHEMA`, `EXTRACT_SCHEMA`, `Entity`,
  `ImportanceInputs`, `ClassificationResult`
- `domains/news/classifier.py`: `ArticleClassifier` + `compute_importance` (deterministic)
- API: `POST /api/classify/run`, `GET /api/classify/articles`
- CLI: `domains/news/run_classify.py`
- `tests/test_classification.py` (۷ تست)

### Files changed
- `backend/ai/prompts/classification.py`
- `domains/news/{classifier,classifier_schema,run_classify}.py`
- `backend/api/routers/classify.py`, `backend/main.py`
- `tests/test_classification.py`

### Tests
- `python -m pytest tests -q` → **45 passed** ✅
- `compute_importance`: ورودی مهم → ۱..۳ ، ورودی عادی → ۷..۱۰ ✅
- `ClassificationResult.from_dict` پارس درست ✅
- `ArticleClassifier.classify_pending` با Mock → classified=1 ✅
- API زنده: ۳ مقاله طبقه‌بندی شد ✅

### Known issues
- با Mock Provider مقادیر نمایشی‌اند (topics=["mock"]، importance=10 چون ابعاد صفرند).
  با Provider واقعی، مقادیر معنادار می‌شوند.
- فیلد `country` روی Article ذخیره نمی‌شود (مدل فیلد country ندارد)؛ در فاز بعدی یا با
  استفاده از Entity می‌توان اضافه کرد.

### Next step
- Phase 11 — Event Extraction: چند مقاله مرتبط → یک Event

---

## Phase 9 — Deduplication (exact / near / repost / same-story)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/news/dedup.py`:
  - shingling (k-gram) + MinHash (۶۴ permutation)
  - LSH banding (۱۶ باند × ۴ ردیف) برای یافتن کارای کاندیدها
  - Union-Find برای خوشه‌بندی
  - تشخیص exact (content_hash)، near (Jaccard)، repost (بین منابع)
- `domains/news/dedup_service.py`: اجرا روی Documentهای ذخیره‌شده و ثبت cluster
- `domains/news/run_dedup.py`: CLI
- API: `POST /api/dedup/run` (limit + near_threshold)
- ادغام اختیاری با ingestion با `DEDUP_ON_INGEST=true`
- config: `dedup_near_threshold`, `dedup_window`, `dedup_on_ingest`
- `tests/test_dedup.py` (۸ تست)

### Files changed
- `domains/news/{dedup,dedup_service,run_dedup}.py`
- `backend/api/routers/dedup.py`, `backend/main.py`, `backend/core/config.py`
- `domains/news/ingestion.py` (hook اختیاری)
- `tests/test_dedup.py`

### Tests
- `python -m pytest tests -q` → **38 passed** ✅
- MinHash: متن یکسان → 1.0، متن متفاوت → <0.3 ✅
- exact dup clustering ✅
- repost detection بین دو منبع (آستانه ۰.۴۵) → `repost_pairs=1` ✅
- `POST /api/dedup/run` زنده ✅
- CLI `python -m domains.news.run_dedup` ✅

### Known issues
- آستانه‌ی پیش‌فرض ۰.۷ محافظه‌کارانه است؛ برای عناوین کوتاه/بازنویسی‌شده ممکن است نیاز به تنظیم پایین‌تر باشد (قابل تنظیم است).
- هر اجرا روی پنجره‌ی محدود (`limit`) کار می‌کند؛ برای دیتاست بزرگ، اجرای دوره‌ای لازم است.

### Next step
- Phase 10 — Article Classification (topic, language, country, importance, entities) با AI

---

## Phase 8 — News Ingestion (SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `domains/news/fetchers.py`: `BaseFetcher`, `RSSFetcher` (RSS2.0 + Atom با stdlib)، `MockFetcher` (آفلاین)
- `domains/news/normalizer.py`: clean_text، detect_language، hash/content_hash، Point-in-Time
- `domains/news/ingestion.py`: `NewsIngestionPipeline` (async + sync)، dedup بر اساس content_hash
- `domains/news/run_ingest.py`: worker CLI برای همه‌ی منابع فعال
- API: `POST /api/ingest`, `POST /api/ingest/all`, `GET /api/ingest/documents`
- workflow n8n: `phase8-scheduled-ingestion.json` (هر ۳۰ دقیقه → `/api/ingest/all`)
- `tests/conftest.py` (رفع مشکل isolation تست‌ها) + `tests/test_ingestion.py`

### Files changed
- `domains/news/{fetchers,normalizer,ingestion,run_ingest}.py`
- `backend/api/routers/ingestion.py`, `backend/api/schemas/ingestion.py`, `backend/main.py`
- `integrations/n8n/workflows/phase8-scheduled-ingestion.json`
- `tests/conftest.py`, `tests/test_ingestion.py`, `tests/test_jobs.py`, `tests/test_sources.py`

### Tests
- `python -m pytest tests -q` → **31 passed** ✅
- `POST /api/ingest` (منبع CBI) → `fetched=3 stored=3` ✅
- اجرای دوباره → `stored=0 duplicates=3` (dedup) ✅
- `POST /api/ingest/all` → ۱۴ منبع پردازش شد ✅
- `python -m domains.news.run_ingest` → اجرا شد ✅
- import workflow در n8n → موفق ✅

### Known issues
- در MOCK_MODE همه‌ی منابع داده‌ی نمونه‌ی یکسان می‌گیرند، بنابراین dedup بین منابع هم فعال است (رفتار درست برای نمونه).
- `RSSFetcher` به URL واقعی فید نیاز دارد؛ در Phase 8 آدرس فید هنوز در Source ذخیره نمی‌شود (فاز بعدی می‌تواند فیلد feed_url اضافه کند).

### Next step
- Phase 9 — Deduplication: near-duplicate، repost، same-story clustering

---

## Phase 7 — Data Source Registry
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- سرویس دامنه `SourceRegistry` در `domains/news/source_registry.py`
  - list (با فیلتر active/country/type)، get، get_by_name، create، update، set_active
  - `record_success` / `record_error` برای پیگیری سلامت (بند 17)
- API `/api/sources`: GET (list)، POST (create)، GET/{id}، PATCH/{id}، POST/{id}/health
- schemas: `SourceCreate/Update/Read/HealthUpdate`
- seed بازنویسی‌شده: ۱۴ منبع معتبر رایگان + امتیاز اولیه + تکمیل رکوردهای موجود
- Docker build حالا پوشه‌ی `domains/` را هم کپی می‌کند
- تست‌ها: `tests/test_sources.py` (۶ تست)

### Files changed
- `domains/__init__.py`, `domains/news/__init__.py`, `domains/news/source_registry.py`
- `backend/api/routers/sources.py`, `backend/api/schemas/sources.py`, `backend/main.py`
- `db/seed/sources.py`, `docker/backend.Dockerfile`, `tests/test_sources.py`
- `DATA_SOURCES.md` (جدول منابع پیاده‌سازی‌شده)

### Tests
- `python -m pytest tests -q` → **22 passed** ✅
- seed → «seeded 9 new source(s)» سپس «enriched 17 field(s)» ✅
- `GET /api/sources` → ۱۴ منبع ✅
- `GET /api/sources?country=IR` → ۲ منبع ✅
- `POST /api/sources` → 201 ✅
- `POST /api/sources/{id}/health` → `last_success` ثبت شد ✅
- رفع تکرار نام‌ها (ECB) ✅

### Known issues
- امتیازهای credibility/independence اولیه‌اند و باید در فازهای بعدی از عملکرد واقعی به‌روز شوند (بند 56).
- فصل `terms`/`license` برخی منابع نیازمند بررسی نهایی است.

### Next step
- Phase 8 — News Ingestion: SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE

---

## Phase 5 — AI Gateway (Provider-Agnostic, Mock-First)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- `backend/ai/schemas/types.py`: AIRequest/AIResponse/AIUsage/AIError/Message/ProviderHealth
- `backend/ai/providers/`:
  - `base.py`: اینترفیس `AIProvider` (Protocol) + `BaseProvider` با `generate/structured_generate/classify/extract/health`
  - `mock.py`: Mock Provider (deterministic، بدون هزینه) — Phase 6 نیز پوشش داده شد
  - `http_base.py`: پایه‌ی مشترک HTTP با timeout/retry/error mapping
  - `openai.py`, `anthropic.py`, `gemini.py`, `openrouter.py`: adapterهای واقعی
  - `registry.py`: نگاشت نام → Provider (تنها نقطه‌ی شناخت نام‌ها)
- `backend/ai/routing/router.py`: نگاشت نقش/وظیفه → زنجیره‌ی Provider
- `backend/ai/gateway/gateway.py`: Gateway با fallback/retry/timeout/logging/usage tracking
- `backend/ai/prompts/`: قالب‌های نسخه‌دار prompt
- `backend/ai/evaluation/`: ساختار پایه‌ی ثبت عملکرد مدل
- API: `POST /api/ai/generate`, `GET /api/ai/providers`
- config: افزودن کلیدهای Provider (همه Optional)

### Files changed
- `backend/ai/**` (schemas, providers, routing, gateway, prompts, evaluation)
- `backend/api/routers/ai.py`, `backend/api/schemas/ai.py`, `backend/main.py`
- `backend/core/config.py`, `tests/test_ai_gateway.py`

### Tests
- `python -m pytest tests -q` → **16 passed** ✅
- `POST /api/ai/generate` (mock) → پاسخ با provider=mock ✅
- `GET /api/ai/providers` → mock سالم؛ بقیه `not configured` بدون crash ✅
- fallback تست شد: Provider شکست‌خورده → mock ✅

### Known issues
- Providerهای واقعی بدون API Key غیرفعال‌اند (طبق قانون 72) — این رفتار مورد انتظار است.
- Providerها async هستند؛ در endpointهای sync باید با async تعریف شوند (انجام شد).

### Next step
- Phase 6 (Mock AI) عملاً پوشش داده شد؛ در ادامه Phase 7 — Data Source Registry

---

## Phase 4 — n8n orchestration (Trigger → Backend → Database)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- n8n نسخه 2.42.4 در حال اجرا (http://localhost:5678)
- مدل `JobRun` + جدول `job_runs` + migration `71f41613dd11`
- jobs API:
  - `POST /api/jobs/trigger` → ثبت JobRun در PostgreSQL
  - `GET /api/jobs` → آخرین اجراها
- workflow نمونه: `integrations/n8n/workflows/phase4-trigger-backend-database.json`
  - Schedule Trigger (هر ۵ دقیقه) → HTTP POST به `http://backend:8000/api/jobs/trigger`
- import + publish workflow در n8n + ری‌استارت
- اسکریپت کمکی: `scripts/import_n8n_workflows.py`

### Files changed
- `backend/database/models/job.py`, `models/__init__.py`
- `backend/api/schemas/jobs.py`, `backend/api/routers/jobs.py`, `backend/main.py`
- `db/migrations/versions/71f41613dd11_add_job_runs.py`
- `integrations/n8n/workflows/phase4-trigger-backend-database.json`, `integrations/n8n/README.md`
- `tests/test_jobs.py`, `scripts/import_n8n_workflows.py`

### Tests
- `python -m pytest tests -q` → **9 passed** ✅
- import workflow در n8n → «Successfully imported 1 workflow» ✅
- publish + restart → «1 published workflows» ✅
- **اجرای زمان‌بندی‌شده‌ی واقعی**: n8n در 2026-10-07 21:25:01 خودکار درخواست زد و
  رکورد `scheduled_heartbeat` با source=`n8n` در `job_runs` ثبت شد ✅
- تست شبکه از داخل کانتینر n8n به `http://backend:8000` ✅

### Known issues
- در n8n 2.x، فایل workflow باید فیلد `id` داشته باشد و از `publish:workflow`
  استفاده شود (نه صرفاً active کردن). اسکریپت کمکی این را مدیریت می‌کند.
- n8n با volume خودش (`n8n_data`) کار می‌کند؛ workflowها در DB داخلی n8n ذخیره می‌شوند.

### Next step
- Phase 5 — AI Gateway (Provider interface + Mock provider + routing پایه)

---

## Phase 3 — PostgreSQL (models + migrations)
**تاریخ:** 2026-10-08
**وضعیت:** DONE

### Completed
- مدل‌های ORM موجودیت‌های اصلی (۱۵ جدول):
  sources, documents, articles, events, claims, evidence, entities,
  entity_relationships, market_observations, macro_observations,
  world_states, scenarios, forecasts, forecast_outcomes, recommendations
- `base.py`: `Base`, `UUIDMixin`, `TimestampMixin`, `PointInTimeMixin`
- `enums.py`: SourceType, VerificationStatus, EntityType, RelationType, EvidenceDirection
- Alembic setup: `alembic.ini`, `db/migrations/env.py`, `script.py.mako`
- migration اولیه autogenerate: `50834c9c3273_initial_schema.py`
- entrypoint بکاند: اجرای خودکار `alembic upgrade head` پیش از سرور
- session factory + `get_db()` + health/db با نسخه‌ی migration
- seed منابع اولیه (`db/seed/sources.py`) — ۶ منبع
- تست‌های مدل (`tests/test_models.py`)

### Files changed
- `backend/database/base.py`, `enums.py`, `session.py`, `__init__.py`
- `backend/database/models/` (۱۲ فایل مدل + `__init__.py`)
- `alembic.ini`, `db/migrations/{env.py,script.py.mako}`, `db/migrations/versions/50834c9c3273_initial_schema.py`
- `docker/backend.Dockerfile`, `docker/backend-entrypoint.sh`
- `db/seed/sources.py`, `tests/test_models.py`

### Tests
- `python -m pytest tests -q` → **7 passed** ✅
- `alembic upgrade head` → ۱۶ جدول (۱۵ + alembic_version) ✅
- `alembic downgrade base` → ۱ جدول (فقط alembic_version) ✅
- `alembic upgrade head` دوباره → ۱۶ جدول ✅ (migration برگشت‌پذیر)
- اجرای داخل Docker: entrypoint migration را اجرا و سرور را بالا آورد ✅
- seed → ۶ منبع ثبت شد ✅
- `/health/db` → `{"ok":true,"server":"PostgreSQL 16.15...","migration":"50834c9c3273"}` ✅

### Known issues
- فایل `.env` باید UTF-8 باشد؛ اگر با PowerShell و encoding اشتباه بازنویسی شود، pydantic-settings خطای decode می‌دهد (با کپی مستقیم از `.env.example` حل شد).
- در شبکه‌ی محدود، `PIP_INDEX_URL` در `.env` باید ست بماند تا build بکاند موفق شود.

### Next step
- Phase 4 — n8n: ساخت workflow ساده Trigger → Backend → Database

---

## Phase 2 — Skeleton (Backend + Frontend + DB + Health)
**تاریخ:** 2026-10-07
**وضعیت:** DONE

### Completed
- Backend FastAPI با endpoints: `/`, `/health` (liveness)، `/health/db` (readiness)
- تنظیمات مرکزی با `pydantic-settings` (خواندن از `.env`)
- لایه‌ی دیتابیس: `get_engine()` و `check_database()` (بدون crash در نبود DB)
- Frontend React + Vite با HTML `dir="rtl"`، Dark Mode و نمایش وضعیت API/DB
- `docker-compose.yml` شامل postgres, backend, frontend, n8n
- Dockerfiles برای backend و frontend + `.dockerignore`
- ۳ تست pytest برای health endpoints

### Files changed
- `backend/main.py`, `backend/asgi.py`, `backend/__init__.py`
- `backend/core/{__init__,config,logging}.py`
- `backend/database/{__init__,session}.py`
- `backend/api/__init__.py`, `backend/api/routers/{__init__,health}.py`
- `apps/web/{index.html,vite.config.ts,tsconfig.json}`
- `apps/web/src/{main.tsx,App.tsx,styles.css,vite-env.d.ts}`
- `docker-compose.yml`, `.dockerignore`, `docker/{backend,frontend}.Dockerfile`
- `tests/{__init__.py,test_health.py}`

### Tests
- `python -m pytest tests -q` → **3 passed** ✅
- اجرای زنده uvicorn روی پورت 8010:
  - `/` → `{"name":"GlobalIntelligence","env":"development","status":"ok","docs":"/docs"}` ✅
  - `/health` → `{"status":"ok"}` ✅
  - `/health/db` → `{"status":"degraded", ...}` (graceful، چون Postgres در دسترس نبود) ✅
- `npx tsc --noEmit` → exit 0 ✅
- `npm run build` → build موفق (dist ساخته شد) ✅
- `docker compose config --quiet` → معتبر ✅

### Known issues
- **Docker Desktop در ابتدا خراب بود** و حل شد: نسخه‌ی قدیمی 4.19 با WSL 3.x ناسازگار بود؛ با به‌روزرسانی به Server **29.8.2** درست شد.
- **شبکه‌ی PyPI ناپایدار** (`files.pythonhosted.org` خطای SSL EOF می‌داد) — با استفاده از آینه‌ی `mirror-pypi.runflare.com` در build حل شد (قابل تنظیم از `.env`).
- `/health/db` در نبود DB به‌درستی `degraded` می‌دهد و crash نمی‌کند (طبق قانون 72).

### Docker stack (اجراشده و تأییدشده)
| سرویس | وضعیت | URL |
|---|---|---|
| backend | healthy | http://localhost:8000 |
| frontend | up | http://localhost:5173 |
| postgres | healthy | localhost:5432 |
| n8n | up | http://localhost:5678 |

آدرس‌های تست‌شده:
- `/health` → `{"status":"ok"}` ✅
- `/health/db` → `{"status":"ok","database":{"ok":true,"detail":"connected"}}` ✅
- `/docs` → 200 ✅
- `:5173` → 200 (دارای `#root`) ✅
- `:5678` → 200 ✅

### Next step
- Phase 3 — PostgreSQL: مدل‌ها، Alembic، migration اولیه، اتصال کامل و health check دیتابیس

---

## Phase 1 — Environment Preparation & Repository Skeleton
**تاریخ:** 2026-10-07
**وضعیت:** DONE

### Completed
- بررسی و تأیید ابزارهای محیط (Git, Python, pip, Node, npm, Docker CLI, Compose)
- ساخت اسکریپت `scripts/check_env.py` (بدون وابستگی خارجی)
- فایل نسخه‌های مرجع `config/environment.toml`
- فایل‌های وابستگی Backend: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `backend/.gitignore`
- فایل‌های Frontend: `apps/web/package.json`, `.npmrc`, `.gitignore`
- تنظیمات ویرایشگر: `.editorconfig`
- ساخت `.env` محلی از `.env.example` (تأیید شد که توسط Git نادیده گرفته می‌شود)

### Files changed
- `scripts/check_env.py` (جدید)
- `config/environment.toml` (جدید)
- `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pyproject.toml`, `backend/.gitignore` (جدید)
- `apps/web/package.json`, `apps/web/.npmrc`, `apps/web/.gitignore` (جدید)
- `.editorconfig` (جدید)
- `.env` (جدید، محلی و gitignored)
- `PROGRESS.md`, `TASKS.md`, `DECISIONS.md`, `README.md` (به‌روزرسانی)

### Tests
- `python -m py_compile scripts/check_env.py` → OK
- `python scripts/check_env.py` → exit code 0 (همه ابزارهای حیاتی OK)
- `git check-ignore .env` → تأیید شد که `.env` نادیده گرفته می‌شود

### Known issues
- **Docker Daemon در حال اجرا نیست** (Docker Desktop باید شروع شود). CLI و Compose نصب‌اند و برای Phase 2 کافی است.
- خطای اولیه‌ی انکودینگ کنسول ویندوز (cp1256) برطرف شد (reconfigure به UTF-8 + تغییر کدگذاری subprocess).
- npm روی ویندوز فقط از طریق `npm.cmd` اجرا می‌شود؛ اسکریپت این حالت را پوشش می‌دهد.

### Next step
- Phase 2 — Skeleton: Backend (FastAPI) + Frontend (Vite) + Database + Health endpoint + `docker-compose.yml` پایه

---

## Phase 0 — Project Specification & Architecture
**تاریخ:** 2026-10-07
**وضعیت:** DONE (اسناد پایه)

### Completed
- تعریف نهایی محصول، Goals و Non-goals
- معماری کلان (Runtime View + Logical Pipeline)
- ساختار Repository
- طراحی مفهومی AI Gateway (Provider-Agnostic)
- تعریف مدل داده Core Entities
- تعریف Memory (۷ لایه) و Forecast Ledger
- تعریف اصول: Free-First، Point-in-Time Integrity، Reproducibility
- ساخت اسکلت پوشه‌ها
- ساخت ۱۰ سند پایه

### Files changed
- `.gitignore`
- `.env.example`
- `README.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `TASKS.md`
- `PROGRESS.md`
- `DECISIONS.md`
- `LICENSES.md`
- `DATA_SOURCES.md`
- `AI_MODELS.md`
- اسکلت پوشه‌ها (backend, workers, domains, integrations, ml, db, tests, docs, scripts, config, data, docker, apps/web)

### Tests
- (Phase 0 فقط اسناد است — تست کد ندارد)
- بررسی محیط: Git ✅، Python 3.14 ✅، Node v24 ✅، Docker 23 ✅

### Known issues
- مجوز پروژه هنوز تعیین نشده (در DECISIONS.md پیگیری می‌شود)
- انتخاب Provider پیش‌فرض برای AI هنوز نهایی نشده (Mock پیش‌فرض است)

### Next step
- Phase 1 — آماده‌سازی محیط و اسکلت اجرایی Repository (package files، Docker skeleton)

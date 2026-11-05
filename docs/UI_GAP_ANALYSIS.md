# تحلیل شکاف رابط کاربری و نقشهٔ راه اتصال به بک‌اند

> سند تحلیل و برنامه‌ریزی — بدون تغییر کد.
> شاخه: `ui-gap-analysis` · تاریخ: ۲۰۲۶‑۱۱‑۰۶
> منبع قرارداد: `backend/static/index.html` (UI تک‌فایلی، RTL/فارسی)
> منبع پیاده‌سازی: `backend/api/routers/` (۴۷ روتر، ۲۰۱ مسیر)، `backend/database/models/`، `domains/`
> این سند فقط «چه چیزی کم است و به چه ترتیبی ساخته شود» را تعیین می‌کند؛ هیچ endpoint یا جدولی در این مرحله ساخته نشده است.

---

## ۱) خلاصهٔ اجرایی

1. **UI کامل‌تر از بک‌اند است، نه برعکس.** ۲۵ صفحه با ساختار اطلاعاتی مشخص وجود دارد، اما هیچ‌کدام دادهٔ واقعی نمی‌گیرد. اکثر صفحات به endpoint «خام دامنه» وصل می‌شوند، ولی چند صفحه به شکل فعلی هیچ منبع داده‌ای ندارند: **نقشهٔ جهانی (GeoJSON)، مرکز تحلیل AI، صندوق ورودی یکپارچه، تأیید/رد انسانی تصمیم و غربالگری، و گزارش تحلیل (AI Synthesis)**.
2. **احراز هویت فعلی برای UI چندکاربره مناسب نیست.** یک `API_KEY` ثابت در هدر `X-API-Key` وجود دارد؛ نه هویت کاربر، نه نقش، نه نشست، نه audit actor. `POST /api/auth/login` در واقع همان کلید ثابت را برمی‌گرداند. UI آن را در `sessionStorage` نگه می‌دارد (بهتر از localStorage، اما همچنان توکن حامل قابل خواندن توسط هر XSS است).
3. **نقشهٔ جهانی به یک endpoint جدید نیاز دارد**: `GET /api/geo/events` با خروجی GeoJSON `FeatureCollection`. دادهٔ لازم (رویداد، زمان، منبع، اطمینان، دسته) در `events` + `sources` + `claims` وجود دارد، اما مختصات جغرافیایی **ذخیره نمی‌شود** و در زمان خواندن از یک resolver با نقشهٔ مرکز کشورها حل می‌شود.
4. **معماری رندر UI برای دادهٔ زنده آماده نیست.** هر صفحه یک رشتهٔ HTML همگام برمی‌گرداند؛ نه state، نه بارگذاری async، نه خطای قابل بازیابی. زیرساخت Step 0 (`api()`, `giLoadingHtml`…) هست، ولی هر صفحه به یک «بارگذار داده + re-render» کوچک نیاز دارد.
5. **صفحه‌بندی و فیلتر سمت سرور تقریباً وجود ندارد.** فقط `screening/queue` یک پاسخ صفحه‌بندی‌شده دارد. بقیهٔ لیست‌ها `limit` ساده دارند و فرادادهٔ `total/has_more` برنمی‌گردانند.
6. **مدل خطا ناهمگون است**: `HTTPException(detail)` در جاهای مختلف، ۴۲۲ پیش‌فرض Pydantic، و ۴۲۹ بدون `Retry-After`. UI به یک پاکت خطای یکنواخت با `code`/`request_id` نیاز دارد.
7. **Telegram Archive و Auto-purge در بک‌اند هست، ولی عمداً محدود**: ارسال به تلگرام پشت `TELEGRAM_ARCHIVE_ENABLED` و credentialهای env است، و purge فقط «preview» دارد و هیچ مسیر حذفی اجرا نمی‌شود. این وضعیت **درست** است؛ قبل از هر حذف واقعی باید state machine تأیید از راه برسد.
8. **ترتیب پیشنهادی کار**: احراز هویت → قرارداد پاسخ/خطا/صفحه‌بندی → GeoJSON → صفحات داده‌محور (منابع، صندوق، غربالگری) → تحلیل/پیش‌بینی/ریسک/تصمیم → صفحات دامنه → عملیات/تنظیمات → گزارش/آرشیو → به‌روزرسانی زنده و سخت‌سازی. جزئیات در بخش ۶.

---

## ۲) وضعیت فعلی UI از نظر فنی (محدودیت‌هایی که نقشهٔ راه را شکل می‌دهند)

| موضوع | واقعیت فعلی | پیامد برای نقشهٔ راه |
|---|---|---|
| ساختار صفحه | `const pages = {...}` با ۲۵ کلید؛ `pageRenderers` فقط ۱۷ صفحه را نگاشت می‌کند؛ `world` جدا و ۷ صفحه از `genericDomain` می‌آیند | برای هر صفحه یک تابع بارگذار مستقل لازم است، نه یک رندر عمومی |
| رندر | `renderPage(id)` کل `innerHTML` را با یک رشتهٔ همگام می‌سازد | بارگذاری async نیاز به «رندر اسکلت → fetch → re-render ناحیه» دارد؛ بدون آن، هر fetch کل صفحه را قفل می‌کند |
| رویدادها | delegation سراسری روی `[data-action]` (حدود خط ۶۸۰) و `notifyAction(action)` که فعلاً toast «به بک‌اند وصل نیست» می‌دهد | نقشهٔ اقدام‌ها آماده است؛ فقط باید به فراخوانی واقعی `api()` تبدیل شود |
| لایهٔ اتصال | Step 0: `api(method,path,{body,query})`، هدر `X-API-Key`، timeout ۱۵s، `{status,message}`، مودال کلید در `sessionStorage` | قابل استفاده است؛ برای نشست کوکی‌محور باید `credentials` و مدل خطا تکمیل شود |
| صفحه‌های وصل‌شده | `connectedPages` خالی است؛ ribbon همه‌جا «داده نمونه» نشان می‌دهد | ثبت هر صفحه در این Set، معیار «اتصال کامل شد» در هر مرحله است |
| دادهٔ نمونه | همهٔ اعداد/جدول‌ها hard-coded در توابع رندر هستند (مثلاً ۲۴۸ تحلیل، ۸۴٪ اطمینان) | حذف تدریجی دادهٔ نمونه باید بخشی از Definition of Done هر مرحله باشد |
| نقشهٔ جهانی | MapLibre از CDN، catalog ۱۴ لایه، یک endpoint دلخواه، فیلتر دسته سمت کلاینت، بازهٔ زمانی سمت کلاینت | بک‌اند باید همان قرارداد را تأمین کند؛ فیلتر زمانی/دسته باید سمت سرور هم پشتیبانی شود |
| دسترس‌پذیری | `role="status"`، `aria-*` در برخی بخش‌ها، اما جدول‌ها/نمودارها بدون معادل متنی | در مرحلهٔ آخر باید بررسی شود؛ مانع اتصال داده نیست |
| دارایی‌های خارجی | MapLibre از `unpkg.com` و CSS آن | بدون اینترنت بارگذاری نمی‌شود؛ برای «local-first» باید self-host شود |

---

## ۳) فهرست صفحات: داده‌ها، اقدام‌ها، نگاشت بک‌اند و شکاف

راهنمای وضعیت:

- ✅ endpoint موجود است و شکل پاسخ برای این صفحه کافی است.
- ⚠️ endpoint موجود است، اما فیلد/تجمیع/صفحه‌بندی کم است.
- ❌ هیچ endpoint یا منبع داده‌ای برای این نیاز وجود ندارد.

### ۳.۱ `overview` — مرکز هوشمندی (`dashboard`)

**داده‌های نمایش‌داده‌شده**
- جمع‌بندی راهبردی AI: عنوان آخرین تحلیل، تاریخ/ساعت، متن سنتز، اطمینان ترکیبی (۸۴٪)، تعداد منابع (۱۲)، رویداد مرتبط (۴)، مدل ارزیابی‌شده (۳)، اجماع مدل‌ها (۸۱٪)، کیفیت شواهد (۰٫۸۴)، موضع هر مدل (Kev/Laya/Gateway).
- کارت‌های KPI بالای صفحه + نمودار روند شاخص ریسک (۱۹ نقطه) + دونات «توزیع همگرایی مدل‌ها».
- پنل «پیشنهادهای اولویت‌دار AI».
- زنجیرهٔ «شواهد تا نتیجه» (تعداد منبع/رویداد/ادعا/شاهد/جمع‌بندی).
- شبکهٔ ارتباطات تحلیل منتخب (`miniNetwork`).
- «کیفیت مدل‌ها در ارزیابی اخیر» (نوارهای امتیاز).
- جدول «آخرین خروجی‌های هوشمند» با ستون‌های: خروجی تحلیل، حوزه، مدل/مسیر، اطمینان، وضعیت شواهد، زمان، ↗.

**اقدام‌های کاربر**
- `data-action="refresh"` تازه‌سازی نما.
- `data-action="report"` ساخت گزارش تحلیلی.
- `data-action="trace"` باز کردن ردیابی هر ردیف.
- لینک به `ai-analysis`، `decisions`، `entity-graph`، `evaluation`، `evidence`.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| KPI و جمع‌بندی | `/api/decisions`، `/api/forecasts`، `/api/risk/overview`، `/api/evaluation/summary`، `/api/ai/status`، `/api/ops/status` | ⚠️ تجمیع سمت کلاینت یعنی ۷+ درخواست و منطق تکراری |
| اجماع مدل‌ها / اختلاف | `/api/debate/scorecard`، `/api/debate/runs/{id}` (`consensus_probability`, `disagreement`) | ⚠️ به «آخرین تحلیل» گره نخورده |
| زنجیرهٔ شواهد | `/api/claims`، `/api/claims/{id}/evidence`، `/api/events`، `/api/graph/*` | ⚠️ شمارش تجمیعی ندارد |
| جدول خروجی‌ها | `/api/decisions`، `/api/briefings` | ⚠️ ستون «وضعیت شواهد» وجود ندارد |

**شکاف و تغییر لازم**
1. افزودن `GET /api/dashboard/overview` که در یک پاسخ برگرداند: `last_analysis`، `kpis`، `risk_series`، `model_consensus`، `evidence_chain_counts`، `priority_suggestions`، `latest_outputs` (با `evidence_status`)، `model_quality`.
2. افزودن فیلد مشتق `evidence_status` (کافی/ناکافی/نیازمند بررسی) بر اساس `Claim.verification_status` و تعداد شاهد مستقل؛ نه ذخیرهٔ جدا.
3. برای «آخرین تحلیل» یک مفهوم پایدار لازم است (بخش ۳.۲) — این endpoint به آن وابسته است.

---

### ۳.۲ `ai-analysis` — مرکز تحلیل هوشمند AI

**داده‌های نمایش‌داده‌شده**
- ۴ KPI: تحلیل‌های ذخیره‌شده (۲۴۸)، اطمینان میانگین (۷۹٫۶٪)، نیازمند بررسی انسانی (۱۷)، شواهد ناکافی (۹).
- فیلترها: حوزه (ژئوپلیتیک/اقتصاد کلان)، وضعیت (تکمیل‌شده/نیازمند بررسی)، مدل (Kev/Laya/AI Gateway) + جست‌وجوی تحلیل/شناسه.
- نمودار «تغییر اطمینان تحلیل‌ها در طول زمان» (۱۶ نقطه).
- جدول تحلیل‌های قابل بررسی (`genericTable`).
- جزئیات تحلیل منتخب: شناسه `ANL-2026-0842`، وضعیت، اولویت `P1`، عنوان، خلاصه، اطمینان مدل (۸۴٪)، کیفیت شواهد (۰٫۸۴)، ۳ مرحلهٔ قابل ممیزی (شناسایی الگو / پیوند ادعا به شاهد / سنتز و اختلاف‌سنجی) با شمارش رویداد/ادعا/شاهد/نیازمند تأیید.

**اقدام‌های کاربر**
- `data-action="analysis"` درخواست تحلیل جدید.
- `data-action="trace"` باز کردن ردیابی کامل.
- فیلترها و جست‌وجو (بدون `data-action`؛ باید به state فیلتر وصل شوند).

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| لیست تحلیل‌ها | — | ❌ هیچ موجودیت «Analysis» وجود ندارد؛ نزدیک‌ترین‌ها `Recommendation`، `DebateRun`، `Forecast` هستند |
| ردیابی (trace) تحلیل | `/api/claims/{id}/evidence`، `/api/graph/neighbors/{id}` | ⚠️ تکه‌تکه؛ ردیابی واحد ندارد |
| KPIها | `/api/decisions`، `/api/evaluation/summary` | ⚠️ «شواهد ناکافی» و «نیازمند بررسی» قابل استخراج نیست |
| درخواست تحلیل جدید | `/api/ai/generate`، `/api/debate/run` | ⚠️ خروجی تحلیل ساختاریافته ذخیره نمی‌شود |

**شکاف و تغییر لازم**
1. **تصمیم معماری لازم است** (بخش ۷، سؤال ۱): یا جدول `analyses` ساخته شود (`id, title, domain, priority, model, model_version, confidence, evidence_quality, status, summary, trace_json, created_at, updated_at, observed_at`) با migration، یا یک «نمای تحلیل» از `recommendations` + `debate_runs` + `forecasts` ساخته شود و هیچ جدول جدیدی اضافه نشود. پیشنهاد: نمای تجمیعی بدون جدول جدید در گام اول؛ جدول فقط اگر ویرایش/تأیید انسانی لازم شد.
2. `GET /api/analyses` با فیلتر `domain, status, model, q` و صفحه‌بندی؛ `GET /api/analyses/{id}/trace` که زنجیرهٔ `source → document → event → claim → evidence → synthesis` را با شمارش برگرداند.
3. `POST /api/analyses/request` که یک job تحلیل ایجاد کند (با `dispatch` موجود)، نه فراخوانی مستقیم LLM از UI.

---

### ۳.۳ `ai-chat` — گفت‌وگوی هوشمند

**داده‌های نمایش‌داده‌شده**
- پیام‌های کاربر و AI با متادیتای «شما · ساعت» و «AI Gateway · مدل · ساعت».
- وضعیت `Mock · نمونه`.
- پنل «Attribution و مصرف جلسه»: مسیر اجرا، Provider، Model ID، Token input/output، Latency، Free Policy.
- هشدار «این پنجره به مدل واقعی متصل نیست».

**اقدام‌های کاربر**
- `data-action="sendChat"` ارسال پیام (`#chatInput`).
- `data-action="chatSettings"` تنظیم مدل.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| ارسال پیام | `POST /api/ai/chat` | ✅ `text, provider, model, usage, cost_estimate, latency_ms, is_mock, model_version` |
| وضعیت Mock/Real | `GET /api/ai/status` | ✅ |
| Providerهای سالم | `GET /api/ai/providers` | ✅ |
| تاریخچهٔ گفت‌وگو | — | ❌ نه جدول thread/message، نه endpoint |
| تنظیم مدل در UI | `GET /api/settings/models` | ⚠️ endpoint هست، انتخاب نقش/مدل در UI وجود ندارد |

**شکاف و تغییر لازم**
1. جدول‌های `ai_conversations` و `ai_messages` (migration) + `GET/POST /api/ai/conversations`، `GET /api/ai/conversations/{id}/messages`. بدون این، بازکردن صفحه بعد از refresh همه‌چیز را از دست می‌دهد.
2. اتصال `chatSettings` به `GET /api/settings/models` و `PUT /api/settings/agent-assignments`.
3. اختیاری (فاز ۱۰): استریم پاسخ با SSE؛ فعلاً پاسخ کامل کافی است، اما timeout باید از ۱۵s بیشتر شود یا برای این endpoint خاص تنظیم شود.

---

### ۳.۴ `debate` — مناظره و اختلاف‌سنجی مدل‌ها

**داده‌های نمایش‌داده‌شده**
- KPI: مدل‌های مشارکت‌کننده (۳)، سطح توافق (۸۱٪)، هزینهٔ تخمینی.
- فرم موضوع مناظره: پرسش تحلیل، افق (۳۰ روز)، سقف خروجی (۲۰۰۰ توکن)، «تأیید اجرا لازم است».
- موضع هر مدل با برچسب (محافظه‌کارانه/مرحله‌ای/مشروط) و اطمینان.
- «نقشهٔ اختلاف دیدگاه‌ها»: ۴ محور (جهت اثر ۹۲٪، شدت ۶۸٪، زمان‌بندی ۵۴٪، پایداری ۶۱٪).
- جمع‌بندی + ۲ اقدام: «ثبت بررسی انسانی»، «ابطال/خنثی‌سازی اجرا».

**اقدام‌های کاربر**
- `data-action="debate"` ساخت مناظرهٔ جدید.
- `data-action="ack"` ثبت بررسی انسانی.
- `data-action="void"` ابطال اجرا.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| اجرا | `POST /api/debate/run` (`dry_run`/`live`) | ✅ |
| فهرست و جزئیات | `GET /api/debate/runs`، `/runs/{id}` | ✅ |
| مشارکت‌کنندگان/مواضع/هزینه | `DebateRunRead.messages[]` با `probability_up, confidence, quality_score, tokens, cost, latency` | ✅ |
| توافق/اختلاف | `consensus_probability`, `disagreement` | ✅ |
| محورهای اختلاف (۴ محور) | — | ❌ در مدل نیست؛ UI آن را ساختگی تولید می‌کند |
| ابطال اجرا | `POST /api/settings/debate-runs/{run_id}/void` | ✅ |
| ثبت بررسی انسانی | — (فقط `audit/log`) | ⚠️ audit عمومی هست، اما ثبت ack مخصوص مناظره نیست |

**شکاف و تغییر لازم**
1. محورهای اختلاف: اگر می‌خواهیم واقعی باشند، باید در `DebateMessage` یا یک `run_metadata` ذخیره شوند؛ در غیر این صورت از UI حذف شوند. **حذف بهتر از جعل است** — پیشنهاد: هر ۴ محور با دادهٔ واقعی پر نمی‌شوند، پس با « disagreement` واقعی + مواضع مدل‌ها» جایگزین شوند.
2. `review_ack` برای مناظره: یا از `audit/log` با `action=debate_ack` استفاده شود (بدون migration)، یا جدول عمومی `human_reviews` (بخش ۳.۹ و ۳.۱۹ به آن نیاز دارند) — **یک جدول مشترک** بسازیم، نه سه جدول.

---

### ۳.۵ `evaluation` — آزمایشگاه ارزیابی AI

**داده‌های نمایش‌داده‌شده**
- Macro F1 (۰٫۸۶)، Precision (۰٫۸۹)، Recall (۰٫۸۳)، Abstain rate (۶٫۲٪).
- مقایسهٔ مدل‌ها: Kev 86، Laya 82، Rules 74، Gateway 89 (F1/Precision/Recall).
- ماتریس خطای ۳×۳ (مثبت/منفی/نامشخص) با FP=۸، FN=۶.
- کالیبراسیون اعتماد: confidence bins در برابر دقت مشاهده‌شده + خط مرجع ۴۵ درجه.
- «کیفیت در برابر منابع مصرفی»: latency میانه ۱٫۸s، اوج RAM ۳٫۲GB، توکن ۱۲٫۴k، هزینه.

**اقدام‌های کاربر**
- `data-action="evaluate"` اجرای ارزیابی.
- تب‌های F1 / Precision / Recall.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| اجرا | `POST /api/evaluation/run` | ✅ |
| امتیازها | `GET /api/evaluation/scores` (`brier`, `log_loss`, `mae`, `rmse`) | ✅ |
| خلاصه + کالیبراسیون | `GET /api/evaluation/summary` (`calibration: list[dict]`) | ✅ |
| F1/Precision/Recall به‌تفکیک مدل | — | ❌ معیارهای فعلی رگرسیونی‌اند، نه طبقه‌بندی |
| ماتریس خطا / abstain | — | ❌ |
| latency/RAM/توکن | `/api/local-runtimes/status`، `provider_run_stat` | ⚠️ دادهٔ سخت‌افزاری هست، endpoint تجمیعی نیست |

**شکاف و تغییر لازم**
1. `GET /api/evaluation/classification` با ورودی `model, since`: `precision, recall, f1, support, confusion_matrix (3x3), abstain_rate`. منبع: برچسب انسانی (Gold set) که هنوز وجود ندارد → تا آن زمان باید `INSUFFICIENT_EVIDENCE` برگردد و UI عدد نمایش ندهد.
2. `GET /api/evaluation/runtime` برای latency/RAM/توکن به‌تفکیک مدل (از `local_runtimes` + `provider_run_stat`).
3. **مهم**: صفحه فعلی اعداد نمایشی نشان می‌دهد؛ تا Gold set واقعی نباشد، UI باید به‌جای عدد، «دادهٔ کافی نیست» نشان دهد. این با قانون «بدون عدد بی‌منبع» پروژه هم‌راستاست.

---

### ۳.۶ `evidence` — شواهد و ردیابی

**داده‌های نمایش‌داده‌شده**
- گراف زنجیره: منبع (۱۲) → رویداد (۴) → ادعا (۹) → شاهد (۱۷) → جمع‌بندی AI (۱) با گره‌های `SRC 01/07`، `E-14/21/25`، `CLM 08/11`.
- ۵ نوار کیفیت: پوشش، استقلال، تازگی، سازگاری، تأییدپذیری.
- راهنمای رنگ‌ها.
- جدول شواهد (`genericTable`).

**اقدام‌های کاربر**
- کلیک روی گره (بدون `data-action` فعلی) برای drill-down.
- `data-action="filter"` از جدول عمومی.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| شواهد یک ادعا | `GET /api/claims/{claim_id}/evidence` | ✅ |
| ادعاها | `GET /api/claims` (با `verification_status`, `independent_source_count`, `source_independence`) | ✅ |
| گراف موجودیت | `GET /api/graph/entities`، `/relationships`، `/neighbors/{id}` | ✅ |
| شمارش زنجیره | — | ⚠️ باید سمت کلاینت از چند endpoint جمع شود |
| ۵ معیار کیفیت | — | ❌ هیچ‌کدام به‌صورت متریک محاسبه نمی‌شود |

**شکاف و تغییر لازم**
1. `GET /api/evidence/summary?claim_id=` یا `?event_id=` که برگرداند: `counts {sources, events, claims, evidence, syntheses}` و `quality {coverage, independence, freshness, consistency, verifiability}` با `method` و `observed_at`.
2. تعریف دقیق هر معیار در `docs/` (مثلاً «تازگی = نیمه‌عمر ۷۲ ساعت») — بدون تعریف، عدد ممنوع.
3. `GET /api/evidence/trace/{claim_id}` که زنجیرهٔ کامل (نه فقط evidence همان claim) را برای گراف بدهد.

---

### ۳.۷ `forecasts` — پیش‌بینی‌ها و سناریوها

**داده‌های نمایش‌داده‌شده**
- KPI: پیش‌بینی فعال (۳۶)، نیازمند outcome (۱۲)، میانگین افق (۳۰ روز)، کالیبراسیون (نامشخص).
- نمودار «بادبزنی» (fan chart) با بازهٔ عدم‌قطعیت ۳۰ روزه.
- درخت سناریو: کاهش تنش ۳۵٪ / تداوم ۴۵٪ / تشدید (بقیه).
- دفتر پیش‌بینی‌ها (`genericTable`).

**اقدام‌های کاربر**
- `data-action="forecast"` اجرای پیش‌بینی.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| اجرا | `POST /api/forecasts/run` | ✅ |
| لیست/فیلتر | `GET /api/forecasts` (`target, model, limit`) | ⚠️ صفحه‌بندی و فیلتر زمانی ندارد |
| دفتر فعال | `GET /api/forecasts/ledger/active` | ✅ |
| فیلدها | `ForecastRead` شامل `interval_low/high, confidence, scenario, status, horizon, target_date` | ✅ |
| سری زمانی برای fan chart | — | ❌ فقط نقطه‌های تک‌مقداری |
| وزن سناریوها | — | ❌ سناریوها ردیف جدا هستند، تجمیع احتمال ندارند |
| جایگزینی | `POST /api/forecasts/{id}/supersede` | ✅ |

**شکاف و تغییر لازم**
1. `GET /api/forecasts/outlook?target=&horizon=` که برگرداند: `series[{date, p50, low, high}]`، `scenarios[{name, probability, drivers}]`، `calibration` (از evaluation)، `method`, `data_version`.
2. قاعدهٔ تجمیع احتمال سناریوها (نرمال‌سازی؟ رأی مدل؟) باید مستند و قطعی باشد؛ در غیر این صورت UI نباید درصد نشان دهد.

---

### ۳.۸ `risk` — مرکز ریسک و سناریو

**داده‌های نمایش‌داده‌شده**
- ماتریس ۵×۵ احتمال × شدت با شمارش در خانه‌ها و رنگ‌بندی (پایین/متوسط/بالا).
- «سیگنال‌های ریسک برجسته»: عنوان، حوزه، تعداد شاهد، اطمینان، امتیاز (۸۶/۶۸/۵۹/…).

**اقدام‌های کاربر**
- `data-action="risk"` اجرای تحلیل ریسک.
- `data-action="riskCell"` کلیک روی خانه برای drill-down.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| اجرا | `POST /api/risk/analyze` | ✅ |
| ارزیابی‌ها | `GET /api/risk/assessments` (`category, period`) | ✅ |
| نمای کلی | `GET /api/risk/overview` | ✅ |
| احتمال و شدت جدا | `RiskAssessmentRead` فقط `score` و `level` دارد | ❌ ماتریس بدون این دو محور جعلی است |
| امتیاز/شاهد هر سیگنال | `drivers[]`, `confidence` | ⚠️ `evidence_count` ندارد |

**شکاف و تغییر لازم**
1. افزودن `probability: float | None` و `impact: float | None` (و اختیاری `likelihood_band`, `impact_band`) به جدول `risk_assessments` + migration + به `RiskAssessmentRead`.
2. `GET /api/risk/matrix?period=` که `cells[{probability_band, impact_band, count, risk_ids}]` بدهد.
3. افزودن `evidence_count` (محاسبه‌شده از claims مرتبط) به پاسخ assessments.

---

### ۳.۹ `decisions` — میز تصمیم‌سازی

**داده‌های نمایش‌داده‌شده**
- کارت پیشنهاد برتر: عنوان، متن، برچسب‌ها (۱۲ شاهد، ۳ مدل، ۲ اختلاف حل‌نشده، افق ۷–۳۰ روز)، اطمینان ۸۴٪، «نیازمند بررسی انسانی».
- KPI: پیشنهاد باز (۱۸)، نیازمند شواهد بیشتر (۷)، تأیید انسانی (۵).
- جدول: پیشنهاد | نوع | امتیاز | اطمینان | پشتیبانی شواهد | وضعیت | (بررسی).

**اقدام‌های کاربر**
- `data-action="decision"` اجرای موتور تصمیم.
- `data-action="filter"` نمای فقط موارد نیازمند تصمیم.
- دکمه‌های «بررسی» (بدون action فعلی) → باید تأیید/رد/درخواست شواهد باشد.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| اجرا | `POST /api/decisions/run`، `POST /api/decisions/from-debate` | ✅ |
| لیست/جزئیات | `GET /api/decisions`، `/decisions/{id}` | ✅ |
| فیلدها | `Recommendation`: `score, confidence, direction, horizon, main_drivers, main_risks, invalidation` | ✅ |
| پشتیبانی شواهد | `evidence_for/against` (متن JSON) | ⚠️ شمارش/لینک ساختاریافته ندارد |
| وضعیت انسانی | — | ❌ فقط `decision` ماشینی |
| تأیید/رد/بازبینی | — | ❌ |

**شکاف و تغییر لازم**
1. جدول `human_reviews` (مشترک با مناظره/غربالگری): `id, entity_type, entity_id, action(approve|reject|request_evidence|ack), actor, note, created_at`. یک migration، سه مصرف‌کننده.
2. `POST /api/decisions/{id}/review` + `GET /api/decisions/{id}/reviews`.
3. افزودن `evidence_support {for, against, independent_sources}` به `DecisionRead` (محاسبه از claims، بدون ذخیرهٔ تکراری).

---

### ۳.۱۰ `inbox` — صندوق هوشمندی و مقالات

**داده‌های نمایش‌داده‌شده**
- KPI: P0/P1 جدید (۲۳)، نیازمند screening (۴۱)، Duplicate candidate (۱۷)، شواهد ناکافی (۹).
- فیلترها: جست‌وجو (عنوان/شناسه/منبع)، اولویت (P0–P4)، حوزه (ژئوپلیتیک/اقتصاد/بازار)، وضعیت تحلیل (تکمیل‌شده/در انتظار) + «فیلتر پیشرفته».
- جدول مقالات و ورودی‌های اخیر (`genericTable`).

**اقدام‌های کاربر**
- `data-action="filter"` ذخیرهٔ نمای فیلتر / فیلتر پیشرفته.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| مقالات | `GET /api/ingest/documents` | ⚠️ فقط لیست ساده؛ فیلتر اولویت/حوزه/وضعیت ندارد |
| طبقه‌بندی | `GET /api/classify/articles`، `/articles/{id}` | ✅ |
| صف غربالگری | `GET /api/screening/queue` | ✅ صفحه‌بندی‌شده |
| خوشه‌های تکراری | `GET /api/dedup/clusters` | ✅ |
| نمای یکپارچهٔ صندوق | — | ❌ |
| ذخیرهٔ نمای فیلتر | — | ❌ |

**شکاف و تغییر لازم**
1. `GET /api/inbox` با `q, priority, domain, analysis_status, dedup_state, page, page_size, sort` و پاسخ `{items, total, page, page_size, has_more}`. هر item: `article_id, title, source_name, priority, domain, analysis_status, duplicate_cluster_id, screening_status, evidence_status, retrieved_at`.
2. اگر «نمای ذخیره‌شده» واقعاً لازم است: جدول `saved_views (id, user_id, page, name, query_json)`؛ در غیر این صورت حذف از UI (کوچک‌ترین تغییر).

---

### ۳.۱۱ `world` — نقشهٔ هوشمندی جهانی (صفحهٔ محوری)

**داده‌های نمایش‌داده‌شده**
- نقشهٔ پایهٔ MapLibre + کلاستر + heatmap + نقاط رویداد.
- کاتالوگ ۱۴ لایه: `conflict, attacks, military, protests, sanctions, economic, aviation, maritime, infrastructure, natural, cyber, risk, heat, routes` با گروه، رنگ، آیکون و توضیح.
- بازهٔ زمانی: همه، ۷ روز، ۴۸، ۲۴، ۶، ۱ ساعت.
- پنل لایه‌ها: جست‌وجوی لایه، فعال‌سازی انتخاب‌ها، پاک‌کردن.
- نمای جغرافیایی: جهان/خاورمیانه/اروپا/آسیا/آمریکا؛ zoom/reset/fullscreen/pin.
- بازرس: وضعیت اتصال، لایه‌های انتخابی، فهرست عارضه‌ها، تازگی (`wmFreshness`)، ساعت UTC، مختصات ماوس، شمارش عارضه.
- انتخاب عارضه: عنوان/متادیتا/جزئیات.
- کانکتور: `endpoint` + «نگهداری آدرس در همین مرورگر» + تست + اتصال.
- قرارداد پذیرش: `FeatureCollection`، `geometry` معتبر، `properties.category|type|layer`، اختیاری `title/name/timestamp/source/confidence`.

**اقدام‌های کاربر**
- اتصال/آزمایش/ذخیرهٔ endpoint.
- `↻ دریافت دوبارهٔ داده`.
- toggle لایه‌ها، فعال/غیرفعال همه، بازهٔ زمانی، انتخاب عارضه.
- ناوبری نقشه، تمام‌صفحه، جمع‌کردن پنل‌ها.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| GeoJSON رویدادها | — | ❌ |
| دادهٔ رویداد | `GET /api/events` (`event_type, occurred_at, location, confidence, latitude, longitude, country, location_precision, location_source, location_confidence`) | ✅ دادهٔ خام موجود است |
| منبع/زمان | `Event.sources` (JSON list)، `occurred_at`، `available_at` | ⚠️ نام منبع resolve نمی‌شود |
| دسته | `event_type` رشتهٔ آزاد LLM | ❌ نگاشت قطعی به ۱۴ لایهٔ UI وجود ندارد |
| هندسه برای `routes`/`aviation`/`maritime` | — | ❌ دادهٔ مسیر/پرواز/کشتی وجود ندارد |

**شکاف و تغییر لازم (دقیق)**
1. `GET /api/geo/events` با پارامترهای `bbox, since, until, categories, min_confidence, limit` و پاسخ:
   ```json
   {"type":"FeatureCollection","features":[{
     "type":"Feature",
     "geometry":{"type":"Point","coordinates":[lon,lat]},
     "properties":{"id":"...","category":"conflict","title":"...","timestamp":"...",
                   "source":["...","..."],"confidence":0.7,"country":"IR",
                   "location_precision":"country","location_source":"country_centroid"}
   }]}
   ```
   فقط رویدادهای دارای مختصات برگردند (بدون حدس). `category` از نگاشت صریح `event_type → layer`؛ دسته‌های نامعلوم حذف شوند، نه به `other` تخصیص یابند.
2. فایل `domains/geo/category_map.py` با نگاشت صریح و تست واحد + مستندسازی هر نگاشت.
3. **ذخیرهٔ مختصات در DB** (migration): افزودن `latitude`, `longitude`, `country`, `location_precision`, `location_confidence` به `events` (nullable) و ایندکس `(country)` + `(latitude, longitude)`. دلیل: فیلتر bbox در SQL، مرتب‌سازی، و پایداری پاسخ. در حال حاضر resolver در زمان خواندن اجرا می‌شود و فقط ~۲۵ کشور را می‌شناسد (`domains/geo/resolver.py`, `shortcut` شناخته‌شده).
4. لایه‌های بدون داده (`routes`, `aviation`, `maritime`, `infrastructure`) در پاسخ ظاهر نشوند و UI برای آن‌ها «داده‌ای موجود نیست» نشان دهد؛ **هیچ هندسهٔ ساختگی تولید نشود**.
5. تصمیم دربارهٔ احراز هویت این endpoint (بخش ۷، سؤال ۲): کانکتور UI به‌طور طراحی‌شده هدر کلید نمی‌فرستد.
6. کلاستر/heatmap سمت کلاینت کافی است؛ فقط اگر حجم >۵۰۰۰ عارضه شد، `bbox` + `limit` سمت سرور الزامی می‌شود.

---

### ۳.۱۲ `geopolitics` — تنش منطقه‌ای (`genericDomain`)

**داده‌های نمایش‌داده‌شده**
- هدر دامنه + KPI اطمینان (۷۶٪) + نمودار روند شاخص حوزه (۱۰ نقطه) + توزیع سیگنال‌ها (۸ دسته) + جمع‌بندی AI + ۳ مرحلهٔ استنتاج + جدول «موارد و ارتباطات مرتبط».
- تنظیم محدوده (`data-action="filter"`)، باز کردن تحلیل مرتبط.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| ارزیابی تنش | `GET /api/geopolitics/tensions`، `/assessments` (`tension, conflict_share, event_count, sanction_links, top_types, confidence`) | ✅ |
| اجرا | `POST /api/geopolitics/analyze` | ✅ |
| سری زمانی نمودار | — | ⚠️ assessments چند دوره دارد، اما endpoint سری ندارد |
| توزیع سیگنال | `top_types: dict` | ✅ (برای یک actor) |
| «موارد مرتبط» | `/api/analogues`، `/api/narratives` | ⚠️ نگاشت مشخص نیست |

**شکاف لازم**: `GET /api/geopolitics/overview?actors=&period=` که سری `tension` و `signal_distribution` و فهرست موارد مرتبط را یکجا بدهد (یا UI از همان assessments با groupBy بسازد — کم‌ترین تغییر).

---

### ۳.۱۳ `iran` — کانال‌های انتقال اثر

**داده‌های نمایش‌داده‌شده**: مشابه قالب دامنه + KPI + نمودار + جمع‌بندی + جدول مرتبط؛ در بک‌اند داده‌های غنی‌تری (رویداد/ادعا/ماکرو/تصمیم/وضعیت جهان/کانال انتقال) موجود است.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| خلاصهٔ یکپارچه | `GET /api/iran/brief` (`events, claims, macro, decisions, world_state, counts`) | ✅ |
| رویدادها | `GET /api/iran/events` | ✅ |
| کانال انتقال | `GET /api/iran/transmission` + `POST /transmission/analyze` (`channel, exposure, impact, drivers, confidence`) | ✅ |
| سری زمانی نمودار | — | ⚠️ باید از `macro`/`transmission` ساخته شود |

**شکاف لازم**: سری زمانی از `transmission` (چند دوره) — افزودن `period` به فیلتر و مرتب‌سازی زمانی در همان endpoint کافی است.

---

### ۳.۱۴ `macro` — چرخهٔ اقتصاد کلان

**داده‌های نمایش‌داده‌شده**: شاخص، دوره، مقدار، YoY، شتاب، z-score، مومنتوم، منبع/زمان observation + نمودار + جدول.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| نمای کلی | `GET /api/macro/overview` | ✅ |
| ارزیابی‌ها | `GET /api/macro/assessments` (`latest_value, yoy_change, acceleration, z_score, momentum, momentum_label, method, confidence`) | ✅ |
| سری observation | `GET /api/economic/observations`، `/indicators`، `/latest` | ⚠️ سری تجمیعی برای نمودار ندارد |
| اجرا | `POST /api/macro/analyze`، `POST /api/economic/fetch` | ✅ |

**شکاف لازم**: `GET /api/macro/series?indicator=&country=&period=` که نقاط `{period, value, unit, source, observed_at}` بدهد (از `economic_observations`).

---

### ۳.۱۵ `markets` — بازارها

**داده‌های نمایش‌داده‌شده**: قیمت/بازده، محرک‌های خبری، پیوند رویداد↔قیمت، نمودار.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| نقل‌قول‌ها | `GET /api/markets/latest`، `/observations` (`symbol, asset_class, value, unit, currency, source_name, observed_at`) | ✅ |
| نمادها | `GET /api/markets/symbols` | ✅ |
| دریافت | `POST /api/markets/fetch` | ✅ |
| سری تاریخی/OHLC | — | ❌ `QuoteRead` فقط یک مقدار دارد |
| پیوند رویداد-قیمت | — | ❌ |

**شکاف لازم**: `GET /api/markets/series?symbol=&since=` (از جدول `market_quotes` با ترتیب زمانی)؛ برای «محرک خبری» یک join به `events.affected_assets` — اگر `affected_assets` پر شود.

---

### ۳.۱۶ `portfolio` — پرتفوی و snapshotها

**داده‌های نمایش‌داده‌شده**: ارزش، تخصیص، ریسک، ارز، snapshotهای تاریخی (بازده انتظاری، عدم‌قطعیت، تمرکز، تنوع، پوشش).

**اقدام‌های کاربر (بالقوه در UI)**: ساخت/حذف پرتفوی، ثبت snapshot.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| CRUD | `POST/GET/DELETE /api/portfolios` | ✅ |
| snapshot | `POST /api/portfolios/{id}/snapshot`، `GET .../snapshots` | ✅ |
| فیلدها | `PortfolioRead(positions: dict[str,float])`، `SnapshotRead(expected_return, uncertainty, concentration, diversification, coverage, detail)` | ✅ |
| ارزش‌گذاری/ارز | — | ⚠️ موقعیت‌ها فقط مقدارند؛ قیمت/ارز/دارایی ندارند |
| رابط ساخت پرتفوی | — | ❌ فرم در UI وجود ندارد (فقط نمایش) |

**شکاف لازم**: اگر ارزش‌گذاری واقعی لازم است، `positions` باید ساختاریافته شود (`symbol, quantity, cost_basis, currency`) — تغییر مدل + migration. برای نسخهٔ اول، نمایش خام کافی است و ادعای «ارزش بازار» نباید ساخته شود.

---

### ۳.۱۷ `entity-graph` — شبکهٔ موجودیت‌ها

**داده‌های نمایش‌داده‌شده**: گراف موجودیت/رابطه، entity resolution، provenance، جدول مرتبط.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| موجودیت‌ها | `GET /api/graph/entities` (`type, canonical_name, aliases, country`) | ✅ |
| روابط | `GET /api/graph/relationships` (`from, to, relation, weight, confidence`) | ✅ |
| همسایه‌ها | `GET /api/graph/neighbors/{id}` | ✅ |
| استخراج | `POST /api/graph/extract` | ✅ |
| خروجی گراف برای رندر | — | ⚠️ دو درخواست + ادغام سمت کلاینت؛ بدون `total`/limit |
| provenance | `weight/confidence` | ⚠️ منبع/سند اصلی در رابطه نیست |

**شکاف لازم**: `GET /api/graph/export?limit=&types=` با `{nodes, edges, truncated}`؛ افزودن `source_ids`/`evidence_ids` به edges برای provenance.

---

### ۳.۱۸ `alerts` — هشدارها

**داده‌های نمایش‌داده‌شده**: ❌ صفحه هیچ طرح اختصاصی ندارد؛ `genericDomain('alerts')` به قالب پیش‌فرض می‌افتد (چون در map تنظیمات `alerts` وجود ندارد). یعنی UI برای هشدارها **هیچ محتوایی** ندارد.

**نگاشت بک‌اند** (غنی‌تر از UI)

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| قواعد | `POST/GET /api/alerts/rules`، `PATCH /rules/{id}` | ✅ |
| ارزیابی | `POST /api/alerts/evaluate` | ✅ |
| هشدارها | `GET /api/alerts`، `/alerts/{id}` | ✅ |
| ack/resolve | `POST /api/alerts/{id}/ack`، `/resolve` | ✅ |
| تحویل | `POST /api/alerts/deliver/pending`، `/{id}/deliver/{channel}` | ✅ |

**شکاف لازم**: این تنها صفحه‌ای است که مشکل آن **بک‌اند نیست، UI است**. باید یک صفحهٔ واقعی (لیست هشدار، قاعده‌ساز، ack/resolve، کانال تحویل) طراحی شود. این کار در نقشهٔ راه مرحلهٔ ۷ است.

---

### ۳.۱۹ `sources` — مدیریت منابع

**داده‌های نمایش‌داده‌شده**
- KPI: منابع ثبت‌شده (۱۲۸)، فعال (۹۴)، نیازمند بررسی (۸)، آخرین دریافت.
- فیلتر: adapter (RSS/Atom، REST/JSON، CSV، HTML)، وضعیت (فعال/غیرفعال/نیازمند adapter)، جست‌وجو.
- جدول: منبع | Adapter | منطقه/زبان | وضعیت | آخرین دریافت | Revision | عملیات (ویرایش/بررسی/مشخصات).
- قیف دریافت (۹۸۰→۶۸۸) + چرخهٔ ایمن تعریف منبع (۴ مرحله: adapter، اعتبارسنجی URL/credential، Test Fetch/Preview، تأیید و فعال‌سازی).

**اقدام‌های کاربر**
- `data-action="source"` افزودن منبع (فرم: `sName, sUrl, sAdapter, sRegion, sLang, sKey`).
- `data-action="fetchAll"` اجرای دریافت آزمایشی.
- ویرایش / بررسی (health/recheck) / مشخصات / حذف draft (محلی).

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| CRUD | `GET/POST /api/sources`، `GET/PATCH /{id}` | ✅ |
| Preview/Test | `POST /api/sources/{id}/preview` | ✅ |
| سلامت | `POST /{id}/health`، `POST /{id}/recheck` | ✅ |
| خروجی | `GET /api/sources/export/all` | ✅ |
| adapter | `type` + `collection_method` + `validation_status` | ✅ تقریباً |
| Revision | — | ❌ ستون/تاریخچهٔ revision وجود ندارد |
| KPI و قیف ingest | — | ❌ |
| اجرای دریافت برای همه | `POST /api/ingest`، `/ingest/all`، `/ingest/bot`، `/ingest/jobs` | ✅ |

**شکاف و تغییر لازم**
1. `GET /api/ingest/stats` با `{fetched, normalized, deduped, prioritized, analyzed, stored}` و `window` (+ شمارش منابع فعال/نیازمند بررسی/آخرین دریافت). می‌تواند از `documents`, `article_dispatch`, `articles` محاسبه شود.
2. Revision: جدول `source_revisions (source_id, revision, payload_json, created_by, created_at, active)` + migration، و `revision` در `SourceRead`. یا حداقل `config_version` عددی روی `sources` — **کم‌ترین تغییر: یک ستون `revision: int`**، تاریخچه بعداً.
3. `POST /api/sources/preview` (بدون id) برای «Test Fetch قبل از ذخیره» تا چرخهٔ ۴ مرحله‌ای UI واقعی شود.

---

### ۳.۲۰ `providers` — مرکز کنترل Provider و مدل‌ها

**داده‌های نمایش‌داده‌شده**
- KPI: شناخته‌شده در Catalog (۹)، اتصال تأییدشده.
- کارت Provider: نام، adapter، وضعیت credential/model/policy/gateway، «جزئیات وضعیت»، «پیکربندی draft»، «مشاهدهٔ ارزیابی».
- چرخهٔ آمادگی ۶ مرحله‌ای: کشف → credential/adapter → اتصال تأییدشده → مدل تأییدشده → Policy approved → Enabled/Routed.
- مصرف امروز + Budget cap.

**اقدام‌های کاربر**
- `data-action="provider"` افزودن Provider (فرم: provider/kind/base URL/API key/model/policy).
- `data-action="discover"` همگام‌سازی کاتالوگ.
- `data-action="evaluation"`? (لینک به `evaluation`).

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| کاتالوگ/ثبت | `GET /api/settings/providers`، `/providers/catalog`، `POST /providers` | ✅ |
| کلید (write-only) | `POST /providers/{id}/key` | ✅ |
| تست اتصال | `POST /providers/{id}/test` | ✅ |
| مدل‌ها | `GET /providers/{id}/models`، `/settings/models` | ✅ |
| Policy/blocked | `POST /models/{id}/block`، `GET /settings/diversity` | ⚠️ |
| مصرف امروز | `GET /api/settings/spend-today` | ✅ |
| Runtime محلی | `GET /api/local-runtimes/status` | ✅ |
| «آمادگی» ترکیبی | — | ⚠️ باید از چند منبع محاسبه شود |
| Budget cap | `GET/PUT /api/settings/app` | ⚠️ وجود فیلد باید بررسی/افزوده شود |

**شکاف لازم**: `GET /api/providers/readiness` که برای هر provider وضعیت ۶ مرحله را قطعی برگرداند (`discovered, credentials_configured, connection_verified, model_verified, policy_approved, enabled`) + دلیل. این از پرس‌وجوی چند جدول قابل ساخت است (بدون migration).

---

### ۳.۲۱ `screening` — غربالگری و بازبینی انسانی

**داده‌های نمایش‌داده‌شده**
- KPI: در صف (۳۷)، نتیجهٔ مرتبط (۷۴٪)، Uncertain/Abstain (۹٪)، Runtime Kev/Laya.
- کارت‌های صف: عنوان، `Machine: RELEVANT/UNCERTAIN · مدل · confidence/margin`، دلیل نیاز به بازبینی، دکمه‌های «تأیید انسانی»/«رد».
- «تفکیک چهار حقیقت مستقل» (Machine/Human/Runtime/Dispatch).
- جدول صف Dispatch (`genericTable`).

**اقدام‌های کاربر**
- `data-action="filter"` فقط نیازمند بازبینی.
- `data-action="approve"` / `data-action="reject"` (تأیید/رد).
- (بالقوه) ack.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| صف | `GET /api/screening/queue` (`items, page, page_size, has_more`) | ✅ |
| فیلدها | `screening, review_required, review_reasons, review_acknowledged, priority, classification_status` | ✅ |
| ack | `POST /api/screening/review/{article_id}/ack` | ✅ |
| approve/reject | — | ❌ فقط ack وجود دارد |
| صف dispatch | `GET /api/dispatch/jobs`، `/dispatch/status` | ✅ |
| Runtime | `GET /api/local-runtimes/status` | ✅ |
| درصد/تجمیع | — | ⚠️ محاسبه سمت کلاینت |

**شکاف و تغییر لازم**
1. `POST /api/screening/review/{article_id}/decision` با `{decision: approve|reject, note?}` که در `human_reviews` ثبت شود و `classification_meta.human_review` را پر کند؛ **هرگز خروجی ماشین را overwrite نکند** (فقط فیلد جدا).
2. `GET /api/screening/summary` برای KPIها (queue_count, relevant_pct, uncertain_pct, runtime_state).

---

### ۳.۲۲ `operations` — عملیات و جریان تحلیل

**داده‌های نمایش‌داده‌شده**
- قیف pipeline: Sources ۹۴ → Normalize ۸۶۲ → Dedup ۸۰۳ → Priority ۷۲۱ → Analysis ۶۸۸ → Results ۶۴۱.
- نمودار Jobها در زمان (Queued/Running/Failed).
- سلامت: Backend API، PostgreSQL، AI Gateway، Worker/Scheduler، Telegram Archive.
- جدول Jobها با Correlation ID، attempt، checkpoint، آخرین خطا.

**اقدام‌های کاربر**
- `data-action="refresh"`.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| سلامت | `/health`، `/health/db`، `GET /api/ops/status` | ✅ |
| Jobها | `GET /api/jobs` (`JobRunRead`)، `/api/dispatch/jobs`، `/dispatch/status` | ✅ |
| متریک | `GET /api/ops/metrics` (Prometheus text)، `/api/ops/monitoring` | ✅ |
| قیف stage counts | — | ❌ |
| سری زمانی Job | — | ❌ |
| وضعیت Telegram | — | ❌ (فقط از env قابل حدس) |
| Worker/Scheduler | `GET /api/local-runtimes/status` | ⚠️ فقط runtimeهای محلی |

**شکاف لازم**
1. `GET /api/ops/pipeline?window=24h` → شمارش هر مرحله با تعریف صریح (Document→Article→Dedup→Dispatch→Analysis).
2. سری زمانی از `job_runs` (groupBy دقیقه/ساعت) یا از `ops/metrics`.
3. `GET /api/ops/services` که وضعیت Telegram/Gateway/Worker را از config + last error بدهد (بدون افشای توکن).

---

### ۳.۲۳ `archive` — آرشیو تلگرام (Roadmap)

**داده‌های نمایش‌داده‌شده**
- KPI: Batchها، Remote verified، Restore tested، Purge eligible (همه ۰ در نمونه).
- State machine: PACKAGED → UPLOADED → REMOTE VERIFIED → RESTORE VERIFIED → PURGE ELIGIBLE.
- کنترل‌ها: فعال‌سازی Telegram Archive (پیش‌فرض خاموش)، Automatic Deletion/Purge (غیرفعال و غیرقابل‌فعال‌سازی در UI)، Dry-run، حداکثر ZIP 18MB، Restore staging.
- Catalog: ID، checksum، تعداد آیتم، metadata پیام، نتیجهٔ restore.

**اقدام‌های کاربر**
- `data-action="dryrun"` اجرای Dry Run.
- `data-action="restore"` بررسی مسیر بازیابی.
- toggleها (`#archiveToggle` غیرفعال، `#purgeToggle`).

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| فضا | `GET /api/archive/storage` | ✅ |
| تنظیمات (فقط خواندن) | `GET /api/archive/settings` | ⚠️ نوشتن ندارد |
| کاتالوگ | `GET /api/archive/catalog`، `/catalog/{id}` | ✅ |
| اعتبارسنجی ZIP | `POST /api/archive/validate` | ✅ |
| Restore | `POST /api/archive/restore/dry-run`، `/restore` | ✅ |
| Purge preview | `GET /api/archive/purge/preview` (فقط dry) | ✅ |
| ارسال تلگرام | `POST /api/archive/telegram/{archive_id}` (پشت env) | ✅ |
| ساخت batch/بسته‌بندی | — | ❌ |
| تأیید از راه دور (re-download + SHA-256) | — | ❌ (بخشی در `domains/archive/service.py` هست، مسیر API ندارد) |
| اجرای purge | — (عمداً) | ⛔ نباید ساخته شود تا state machine کامل شود |

**شکاف و تغییر لازم**
1. `POST /api/archive/batches` (ساخت بسته از بازهٔ داده) + `POST /api/archive/{id}/verify-remote` + `POST /api/archive/{id}/restore-test`.
2. `PUT /api/archive/settings` با اعتبارسنجی سمت سرور و فقط برای نقش admin؛ `purge` و `telegram` باید **قفل سخت** داشته باشند (env + admin + audit).
3. هیچ endpoint حذف واقعی؛ eligibility فقط محاسبه و نمایش. مراحل امن در بخش ۵.۶.

---

### ۳.۲۴ `reports` — گزارش‌ها و Briefingها

**داده‌های نمایش‌داده‌شده**
- ۳ کارت: Daily Briefing، Weekly Briefing، AI Synthesis (با شناسه `ANL-0842`).
- ۲ نمودار: تعداد گزارش‌ها در بازه، ترکیب گزارش‌ها.

**اقدام‌های کاربر**
- `data-action="report"` ساخت Briefing.
- `data-action="trace"` باز کردن تحلیل.

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| ساخت روزانه/هفتگی | `POST /api/briefings/daily`، `/weekly` | ✅ |
| لیست/جزئیات | `GET /api/briefings`، `/{id}` (`kind, period, title, content, method, observed_at`) | ✅ |
| گزارش تحلیلی (AI Synthesis) | — | ❌ نوع سوم وجود ندارد |
| نمودار تجمیعی | — | ❌ |

**شکاف لازم**: یا `kind=analysis` به `briefings` اضافه شود (با ارجاع به تحلیل)، یا صفحه فقط دو نوع اول را نشان دهد. پیشنهاد: نوع سوم را حذف نکنیم، اما به `briefings.kind` اضافه شود تا یک مسیر داده داشته باشیم.

---

### ۳.۲۵ `settings` — تنظیمات و کنترل پیکربندی

**داده‌های نمایش‌داده‌شده**
- ۷ بخش: عمومی و ظاهر، Provider و مدل‌ها، منابع و Integration، پیام‌رسانی و هشدار، پردازش و Automation، آرشیو و نگه‌داری، پیشرفته.
- چرخهٔ امن: DRAFT → VALIDATED → TESTED → APPROVED → ACTIVE.
- Revision فعال، تغییرات ذخیره‌نشده، Secret write-only، مرزهای امنیتی.

**اقدام‌های کاربر**
- `data-action="settings"` مشاهدهٔ پیکربندی نمونه.
- تب‌های `data-setting` (بدون action؛ باید محتوا را عوض کنند).

**نگاشت بک‌اند**

| نیاز | endpoint موجود | وضعیت |
|---|---|---|
| تعاریف | `GET /api/configuration/definitions`، `/{kind}` | ✅ |
| نمونه‌ها | `GET/POST /api/configuration/instances` | ✅ |
| Revision | `POST /instances/{id}/revisions` | ✅ |
| validate/test/activate/rollback | `POST .../validate`، `/test`، `/activate`، `/rollback` | ✅ |
| تنظیمات اپ | `GET/PUT /api/settings/app` | ⚠️ بدون چرخهٔ revision |
| secret store | `POST /providers/{id}/key` | ✅ write-only |
| بخش پیام‌رسانی/آرشیو | `GET /api/archive/settings` (فقط خواندن)، alerts delivery | ⚠️/❌ ناقص |

**شکاف لازم**: سیم‌کشی تب‌ها به `definitions/instances`؛ یکسان‌سازی `settings/app` با چرخهٔ revision (یا مستندسازی استثنا)؛ افزودن `PUT /api/archive/settings` و تنظیمات کانال هشدار.

---

## ۴) ماتریس خلاصهٔ وضعیت

| صفحه | داده ✅ | داده ⚠️ | داده ❌ | بزرگ‌ترین شکاف |
|---|---|---|---|---|
| overview | ۰ | ۴ | ۱ | endpoint تجمیعی `dashboard/overview` |
| ai-analysis | ۰ | ۳ | ۱ | موجودیت «Analysis» + trace |
| ai-chat | ۲ | ۱ | ۱ | تاریخچهٔ گفت‌وگو |
| debate | ۵ | ۰ | ۱ | محورهای اختلاف واقعی |
| evaluation | ۲ | ۲ | ۲ | معیارهای طبقه‌بندی + Gold set |
| evidence | ۳ | ۲ | ۱ | متریک‌های کیفیت + trace واحد |
| forecasts | ۴ | ۱ | ۲ | سری زمانی/وزن سناریو |
| risk | ۳ | ۱ | ۱ | `probability`/`impact` در DB |
| decisions | ۳ | ۱ | ۲ | گردش‌کار تأیید انسانی |
| inbox | ۳ | ۲ | ۲ | `GET /api/inbox` یکپارچه |
| world | ۱ | ۱ | ۳ | `GET /api/geo/events` + ذخیرهٔ مختصات |
| geopolitics | ۳ | ۲ | ۰ | endpoint overview سری |
| iran | ۳ | ۱ | ۰ | سری زمانی انتقال |
| macro | ۳ | ۲ | ۰ | سری observation |
| markets | ۳ | ۰ | ۲ | سری تاریخی/OHLC |
| portfolio | ۳ | ۱ | ۰ | ارزش‌گذاری/ارز |
| entity-graph | ۴ | ۲ | ۰ | خروجی گراف یکجا + provenance |
| alerts | ۵ | ۰ | ۰ (بک‌اند) | UI صفحه ندارد |
| sources | ۵ | ۱ | ۲ | revision + ingest stats |
| providers | ۵ | ۳ | ۰ | readiness تجمیعی |
| screening | ۴ | ۱ | ۱ | تصمیم approve/reject |
| operations | ۳ | ۱ | ۳ | pipeline stats + سرویس‌ها |
| archive | ۵ | ۱ | ۲ | batch/verify + settings write |
| reports | ۲ | ۰ | ۲ | نوع AI Synthesis + تجمیع |
| settings | ۵ | ۲ | ۰ | سیم‌کشی تب‌ها |

**جمع‌بندی**: ۲۴ endpoint جدید/گسترش‌یافته و ۳ migration اصلی لازم است (مختصات رویداد، احتمال/شدت ریسک، بازبینی انسانی مشترک). بقیهٔ شکاف‌ها با گسترش endpointهای موجود و بدون جدول جدید قابل حل است.

---

## ۵) موضوعات معماری

### ۵.۱ احراز هویت کاربر (جایگزینی `X-API-Key` خام)

**وضعیت فعلی**
- `backend/auth/deps.py:require_api_key` یک `API_KEY` ثابت را با `secrets.compare_digest` مقایسه می‌کند.
- `POST /api/auth/login` نام کاربری/رمز را می‌گیرد و **همان `settings.api_key`** را برمی‌گرداند؛ یعنی هیچ هویت واقعی ساخته نمی‌شود.
- محدودیت نرخ ورود در حافظه (`_LOGIN_HITS`، ۱۰ در دقیقه) — با چند worker بی‌اثر می‌شود.

**پیشنهاد (ADR لازم است)**
1. `users` (id, username, password_hash با Argon2id, role: viewer|analyst|admin, active, created_at).
2. `sessions` (id, user_id, token_hash, created_at, expires_at, last_seen_at, ip, user_agent, revoked_at) — کوکی `HttpOnly; Secure; SameSite=Lax`.
3. `POST /api/auth/session` (ورود)، `DELETE /api/auth/session` (خروج)، `GET /api/auth/me`.
4. `require_user` جای `require_api_key` برای UI؛ `X-API-Key` فقط برای n8n/اسکریپت‌ها بماند (سرویس‌به‌سرویس).
5. CSRF: چون SameSite=Lax کافی نیست برای درخواست‌های state-changing از سایت دیگر، یک هدر `X-CSRF-Token` + توکن در کوکی غیر-HttpOnly.
6. `audit_records.actor` باید از نشست پر شود، نه `"system"`.
7. برای گذار: هر دو مکانیزم فعال باشند؛ UI ابتدا login را امتحان کند، در ۴۰۱ به فرم ورود برگردد. کلید دستی به‌عنوان «حالت پیشرفته» بماند.
8. `RateLimitMiddleware` فعلی در حافظه است؛ برای production چند-worker به Redis یا حداقل per-user در DB نیاز دارد. (ADR موجود را بررسی کنید.)

**ریسک**: مهاجرت کاربران فعلی وجود ندارد؛ چون تنها ادمین است، می‌توان `users` را با یک رکورد seed کرد. `.env` دست نخورد.

### ۵.۲ نقشهٔ هوشمندی جهانی (GeoJSON)

جزئیات endpoint در ۳.۱۱. نکات معماری:
- **مالکیت داده**: `Event` منبع حقیقت است. `Claim` و `Source` فقط برای غنی‌سازی properties.
- **نگاشت دسته**: فایل قطعی `domains/geo/category_map.py` با تست؛ نگاشت ناشناخته → حذف. هیچ LLM در مسیر درخواست نقشه.
- **مختصات**: `shortcut` فعلی resolver فقط مرکز ~۲۵ کشور است. برای نقشهٔ واقعی، یا Gazetteer (GeoNames) یا ذخیرهٔ مختصات از منبع. تا آن زمان precision کشور صادقانه در `properties.location_precision` بیاید و UI آن را نشان دهد.
- **پاسخ‌دهی**: صفحه‌بندی/limit سمت سرور (`limit` پیش‌فرض ۲۰۰۰، حداکثر ۵۰۰۰)، فیلتر `bbox` روی ایندکس.
- **کش**: `ETag` بر اساس `max(updated_at)` + `Cache-Control: private, max-age=30`؛ در فاز ۱۰ به SSE ارتقا.
- **امنیت**: اگر endpoint محافظت‌شده باشد، کانکتور UI نمی‌تواند هدر بفرستد (طراحی فعلی). دو گزینه: (الف) endpoint same-origin با کوکی نشست و حذف فیلد endpoint آزاد از UI؛ (ب) endpoint عمومی read-only با محدودیت نرخ و فقط دادهٔ غیرحساس. تصمیم در بخش ۷.

### ۵.۳ به‌روزرسانی زنده

- **فاز ۱ (کم‌ترین تغییر، توصیه‌شده)**: polling با `If-None-Match`/`ETag` هر ۳۰s برای نقشه و صندوق؛ `?updated_since=` برای دریافت افزایشی. بدون WebSocket.
- **فاز ۲**: `GET /api/stream` با SSE: `event: alert|event|job`, `id:` به‌عنوان last-event-id، heartbeat ۱۵s. منبع رویداد داخلی: یک `EventBus` ساده در پروسه (asyncio.Queue per subscriber). با چند worker نیاز به Redis pub/sub دارد → تا آن زمان polling.
- UI: یک `subscribe(path, handler)` کوچک که در `renderPage` ثبت/لغو شود؛ در `disposeWorldMap` نیز unsubscribe.
- هرگز دادهٔ حساس (کلید، توکن) در stream نرود.

### ۵.۴ صفحه‌بندی و فیلتر سمت سرور

- پاکت استاندارد: `{items, total, page, page_size, has_more}` (همان الگوی `screening/queue`).
- helper مشترک `backend/api/pagination.py` با `page/page_size` (پیش‌فرض ۵۰، حداکثر ۲۰۰) و `sort` allowlist.
- اعمال روی: events، claims، sources، decisions، forecasts، briefings، jobs، documents، alerts، inbox، geo.
- فیلترها باید allowlist باشند؛ هر فیلتر جدید = تست.
- `offset` فعلی بعضی endpointها حفظ شود برای سازگاری، اما UI از `page` استفاده کند.

### ۵.۵ خطای یکنواخت

- میان‌افزار `backend/api/errors.py`: هر پاسخ خطا
  ```json
  {"error":{"code":"INVALID_API_KEY","message":"...","details":{},"request_id":"..."}}
  ```
  و **همزمان** `detail` قدیمی حفظ شود (n8n/تست‌های موجود نشکنند).
- نگاشت: ۴۰۱ `AUTH_REQUIRED`/`INVALID_API_KEY`، ۴۰۳ `FORBIDDEN`، ۴۰۴ `NOT_FOUND`، ۴۲۲ `VALIDATION_ERROR` (با `fields`)، ۴۲۹ `RATE_LIMITED` + `Retry-After`، ۵۰۳ `DB_UNAVAILABLE`.
- `X-Request-ID` پذیرفته/تولید و در لاگ و پاسخ بیاید.
- UI: `api()` باید `error.code` را دربیاورد و پیام فارسی مناسب نشان دهد؛ برای ۴۲۹ شمارش معکوس.

### ۵.۶ Telegram Archive و Auto-purge — چه چیزی امن است ساخته شود

**اصول ثابت (نباید نقض شود)**
- ارسال ZIP به تلگرام هیچ‌وقت به‌تنهایی «تأیید آرشیو» یا «مجوز حذف» نیست.
- Purge فقط پس از: `REMOTE VERIFIED` (بازدانلود + SHA-256 + تطابق محتوا) و `RESTORE VERIFIED` (restore در staging + بررسی شمارش/چکسام) و در پایان دورهٔ مهلت.
- پیش‌فرض همه‌چیز خاموش؛ فعال‌سازی نیازمند: `env` + نقش admin + ثبت audit + تأیید دوم (two-person) یا تأیید صریح با تایپ نام.
- Dry-run همیشه اول؛ خروجی diff قابل دانلود.

**ترتیب ساخت (هرکدام تست مستقل)**
1. کاتالوگ فقط-خواندنی (موجود) + `storage` (موجود) → سیم‌کشی UI.
2. ساخت batch و محاسبهٔ SHA-256 (`POST /api/archive/batches`) + manifest غیرقابل‌تغییر.
3. `verify-remote` با بازدانلود و مقایسه.
4. `restore-test` در schema/staging جدا + بررسی تعداد رکورد.
5. `purge/preview` با فهرست دقیق + اندازه + دلیل eligibility (موجود، گسترش با دلیل).
6. `purge/execute` **فقط** با feature flag + admin + audit + مهلت ۷ روزه + soft-delete (`deleted_at`) و نگهداری manifest. در این سند توصیه می‌شود مرحلهٔ ۶ در نقشهٔ راه **نباشد** تا مراحل ۱–۵ در عمل پایدار شوند.

**محدودیت تلگرام**: Bot API سقف ۲۰MB دانلود/۵۰MB آپلود دارد؛ UI سقف ۱۸MB را نشان می‌دهد که محافظه‌کارانه است. اگر بزرگ‌تر لازم شد، local Bot API server یا تکه‌تکه‌سازی (که در کاتالوگ `part_index/total_parts` دیده شده) لازم است.

### ۵.۷ سایر موضوعات عرضی

| موضوع | وضعیت | پیشنهاد |
|---|---|---|
| CSP و assets | بدون CSP؛ MapLibre از unpkg | self-host `maplibre-gl` در `backend/static/vendor/`، CSP با `script-src 'self'` (inline script نیاز به nonce/hash دارد) |
| کاشی نقشه | تأمین‌کنندهٔ کاشی مشخص نیست | تصمیم: OSM raster (ToS) / MapTiler / self-host؛ مسئلهٔ حریم خصوصی |
| Local-first | UI به اینترنت نیاز دارد (CDN) | در مرحلهٔ ۹/۱۰ self-host شود |
| زمان و تقویم | تاریخ‌ها میلادی با ارقام فارسی؛ مخلوط | قاعدهٔ واحد: ISO در API، نمایش شمسی/میلادی طبق تنظیم کاربر |
| اعداد و واحد | «٪» و واحد پول بدون منبع در نمونه‌ها | نمایش `source` و `observed_at` کنار هر عدد (قانون پروژه) |
| دسترس‌پذیری | نمودارها/گراف بدون معادل متنی | `aria-label` + جدول پنهان برای هر نمودار |
| تست UI | فقط Playwright e2e در CI (قبلاً حذف شده) | افزودن تست‌های سبک برای `api()` و هر صفحهٔ وصل‌شده (jsdom یا e2e محدود) |
| لاگ سمت کلاینت | `console.error` بدون correlation | ارسال `request_id` خطا به toast و امکان کپی برای پشتیبانی |

---

## ۶) نقشهٔ راه مرحله‌ای (۱۰ مرحله)

هر مرحله باید: تست خودکار داشته باشد، `connectedPages` را به‌روز کند، دادهٔ نمونهٔ همان صفحه را حذف کند، و مستقل commit شود.

### مرحلهٔ ۰ — زیرساخت اتصال ✅ انجام‌شده
`api()`, مودال کلید، ribbon سلامت، helperهای loading/empty/error، `connectedPages`.
**فایل‌ها**: `backend/static/index.html`.

---

### مرحلهٔ ۱ — هویت کاربر و نشست
**هدف**: ورود واقعی، نقش، خروج، actor در audit؛ `X-API-Key` فقط برای سرویس‌ها.
**وابستگی**: ندارد.
**تغییرات**:
- `backend/database/models/user.py`, `session.py` (جدید)
- `db/migrations/versions/<rev>_users_sessions.py`
- `backend/auth/deps.py` (`require_user`, `require_role`)، `backend/auth/passwords.py`
- `backend/api/routers/auth.py` (`/session`, `/me`, `DELETE /session`)
- `backend/main.py` (dependency)
- `backend/static/index.html` (مودال ورود، حذف ورود با کلید خام از مسیر پیش‌فرض)
- `tests/test_auth_sessions.py` (ورود/خروج/۴۰۱/۴۰۳/انقضا/CSRF)
**خروج**: `/health` عمومی؛ بقیه با کوکی؛ خروج نشست را باطل می‌کند؛ تست‌های موجود با `API_KEY=""` نشکنند.

---

### مرحلهٔ ۲ — قرارداد پاسخ، خطا و صفحه‌بندی
**هدف**: یک شکل پاسخ و خطا در همه‌جا؛ helper مشترک صفحه‌بندی.
**وابستگی**: ۱ (برای `request_id` و actor).
**تغییرات**:
- `backend/api/errors.py` (جدید)، `backend/api/pagination.py` (جدید)
- `backend/main.py` (middleware)
- `backend/api/routers/screening.py` (مهاجرت به helper، حفظ سازگاری)
- `backend/static/index.html` (`api()` با `error.code`, `Retry-After`)
- `tests/test_api_errors.py`, `tests/test_pagination.py`
**خروج**: ۴۰۱/۴۲۲/۴۲۹/۵۰۳ شکل یکسان + `request_id`؛ `detail` قدیمی حفظ شود.

---

### مرحلهٔ ۳ — GeoJSON و نقشهٔ جهانی
**هدف**: `GET /api/geo/events` + سیم‌کشی صفحهٔ `world`.
**وابستگی**: ۲ (پاکت خطا/صفحه‌بندی)، ۱ (اگر احراز هویت اجباری).
**تغییرات**:
- `backend/api/routers/geo.py` (جدید)، `backend/api/schemas/geo.py` (جدید)
- `domains/geo/category_map.py` (جدید)، `domains/geo/resolver.py` (گسترش/Caching)
- `backend/database/models/event.py` (ستون‌های مختصات) + migration + backfill job
- `backend/static/index.html` (endpoint پیش‌فرض `/api/geo/events`، حذف فیلد URL آزاد یا محدودسازی، پیام «داده‌ای موجود نیست» برای لایه‌های بی‌داده)
- `tests/test_geo_events.py` (FeatureCollection، bbox، دسته‌بندی، بدون هندسهٔ جعلی)
**خروج**: نقشه با دادهٔ واقعی؛ لایه‌های بدون داده خالی و صادق؛ `world` در `connectedPages`.

---

### مرحلهٔ ۴ — منابع و دریافت
**هدف**: صفحهٔ `sources` زنده + قیف دریافت.
**وابستگی**: ۲.
**تغییرات**:
- `backend/api/routers/sources.py` (`revision`, `preview` بدون id)
- `backend/database/models/source.py` (+`revision`)، migration
- `backend/api/routers/ingestion.py` (`GET /api/ingest/stats`)
- `backend/static/index.html` (فرم منبع، جدول، فیلتر، پیش‌نمایش)
- `tests/test_sources_api.py`, `tests/test_ingest_stats.py`
**خروج**: CRUD + preview + health + revision؛ بدون نوشتن در pipeline هنگام preview.

---

### مرحلهٔ ۵ — صندوق ورودی، غربالگری و بازبینی انسانی
**هدف**: `inbox` و `screening` زنده + تصمیم انسانی مشترک.
**وابستگی**: ۲، ۴ (دادهٔ ingest).
**تغییرات**:
- `backend/api/routers/inbox.py` (جدید) یا گسترش `classify.py`
- `backend/database/models/human_review.py` (جدید) + migration
- `backend/api/routers/screening.py` (`/decision`, `/summary`)
- `backend/api/routers/dispatch.py` (سیم‌کشی نمایش، بدون تغییر منطق)
- `backend/static/index.html`
- `tests/test_inbox.py`, `tests/test_screening_decision.py`
**خروج**: فیلتر/صفحه‌بندی سمت سرور؛ approve/reject در `human_reviews`؛ خروجی ماشین دست‌نخورده.

---

### مرحلهٔ ۶ — تحلیل، پیش‌بینی، ریسک، تصمیم، ارزیابی
**هدف**: صفحات `ai-analysis`, `forecasts`, `risk`, `decisions`, `evaluation`, `overview`.
**وابستگی**: ۲، ۵ (`human_reviews`).
**تغییرات**:
- `backend/api/routers/analyses.py` (جدید) + `dashboard.py` (جدید)
- `backend/api/routers/risk.py` (+`probability`, `impact`) + migration `risk_assessments`
- `backend/api/routers/decisions.py` (`/review`, `evidence_support`)
- `backend/api/routers/evaluation.py` (`/classification`, `/runtime`)
- `backend/api/routers/forecasts.py` (`/outlook`)
- `backend/static/index.html` (۶ صفحه)
- `tests/test_analyses.py`, `test_risk_matrix.py`, `test_decisions_review.py`, `test_evaluation_classification.py`
**خروج**: KPIها و جدول‌ها واقعی؛ جایی که داده کافی نیست `INSUFFICIENT_EVIDENCE`؛ `overview` با یک درخواست.

---

### مرحلهٔ ۷ — صفحات دامنه (شامل `alerts`)
**هدف**: `geopolitics`, `iran`, `macro`, `markets`, `portfolio`, `entity-graph`, `alerts`.
**وابستگی**: ۲؛ (۶ برای پیوند «تحلیل مرتبط»).
**تغییرات**:
- `backend/api/routers/geopolitics.py` (`/overview`)
- `macro.py` (`/series`)، `markets.py` (`/series`)
- `iran.py` (مرتب‌سازی دوره)، `graph.py` (`/export` + provenance)
- `portfolios.py` (اختیاری: ساختار positions)
- `alerts.py` (بدون تغییر بک‌اند؛ فقط UI جدید)
- `backend/static/index.html` (۷ صفحه + طراحی صفحهٔ alerts)
- `tests/` مربوطه
**خروج**: هر ۷ صفحه از endpoint واقعی؛ `alerts` دارای UI مستقل (لیست/قاعده/ack/resolve).

---

### مرحلهٔ ۸ — عملیات، Providerها، تنظیمات
**هدف**: `operations`, `providers`, `settings` زنده.
**وابستگی**: ۲، ۴.
**تغییرات**:
- `backend/api/routers/ops.py` (`/pipeline`, `/services`)؛ `monitoring.py` (سری زمانی)
- `backend/api/routers/settings.py` (`/providers/readiness`, budget cap)
- `backend/api/routers/configuration.py` (سیم‌کشی موجود؛ بدون تغییر منطق)
- `backend/api/routers/archive.py` (`PUT /settings` برای بخش آرشیو)
- `backend/static/index.html`
- `tests/test_ops_pipeline.py`, `test_provider_readiness.py`
**خروج**: قیف واقعی، وضعیت سرویس‌ها، readiness ۶ مرحله‌ای، تب‌های تنظیمات داده‌دار.

---

### مرحلهٔ ۹ — گزارش‌ها و آرشیو (فقط-خواندنی/ایمن)
**هدف**: `reports`، `archive` تا مرحلهٔ RESTORE VERIFIED.
**وابستگی**: ۶ (برای AI Synthesis)، ۸ (settings).
**تغییرات**:
- `backend/api/routers/briefings.py` (نوع `analysis` + تجمیع)
- `backend/api/routers/archive.py` (`batches`, `verify-remote`, `restore-test`)
- `domains/archive/service.py` (تکمیل verify)
- `backend/static/index.html`
- `tests/test_briefings.py`, `test_archive_verify.py`
**خروج**: catalog و state machine واقعی؛ purge اجرا نمی‌شود؛ همهٔ toggleها پیش‌فرض خاموش.

---

### مرحلهٔ ۱۰ — به‌روزرسانی زنده و سخت‌سازی
**هدف**: SSE/polling، CSP/self-host، دسترس‌پذیری، e2e.
**وابستگی**: همهٔ مراحل قبلی.
**تغییرات**:
- `backend/api/routers/stream.py` (جدید)، `backend/core/event_bus.py` (جدید) — یا فقط polling با ETag
- `backend/main.py` (CSP، static vendor)
- `backend/static/vendor/maplibre/*` (self-host)
- `backend/static/index.html` (subscribe/unsubscribe، aria، Jalali)
- `tests/test_stream.py`، و آزمون e2e سبک
**خروج**: نقشه و صندوق با polling/SSE به‌روز؛ بدون CDN؛ CSP فعال.

---

## ۷) سؤال‌های تصمیم (نیازمند پاسخ صاحب پروژه)

1. **موجودیت «تحلیل»**: جدول مستقل `analyses` بسازیم یا نمای تجمیعی از `recommendations` + `debate_runs` + `forecasts`؟ (پیشنهاد: نمای تجمیعی تا زمانی که ویرایش/تأیید انسانی لازم نشده.)
2. **دسترسی به `/api/geo/events`**: کوکی نشست (same-origin، کانکتور حذف شود) یا endpoint عمومی read-only با rate limit؟ کانکتور فعلی عمداً هدر کلید نمی‌فرستد.
3. **تأمین‌کنندهٔ کاشی نقشه**: OSM raster، MapTiler، Carto، یا self-host؟ (حریم خصوصی + ToS + هزینه.)
4. **Local-first واقعی**: آیا UI باید بدون اینترنت کار کند (self-host MapLibre)؟ این تصمیم CSP و اندازهٔ فایل را تعیین می‌کند.
5. **چندکاربره بودن**: یک ادمین کافی است یا نقش‌های viewer/analyst/admin لازم است؟ actor در audit چقدر مهم است؟
6. **گردش‌کار تأیید انسانی**: یک نفر یا two-person rule برای تأیید تصمیم/غربالگری/حذف؟
7. **مهلت و سیاست حذف (Auto-purge)**: چند روز مهلت، چه کسی مجاز است، soft-delete کافی است؟
8. **تلگرام**: توکن/chat ID مالکیت، حداکثر اندازهٔ batch، آیا local Bot API server راه‌اندازی می‌شود؟
9. **نگه‌داشت داده و حریم خصوصی**: دادهٔ منابع/مقالات چقدر نگه داشته شود؟ آیا متن کامل مقاله در مرورگر نمایش داده شود؟
10. **زبان و تقویم**: UI فقط فارسی بماند یا دوزبانه؟ تاریخ شمسی پیش‌فرض یا میلادی؟
11. **صفحه‌بندی**: پیش‌فرض ۵۰ کافی است یا ۲۰ برای موبایل؟ آیا «نمای ذخیره‌شده» واقعاً لازم است (در غیر این صورت از UI حذف شود)؟
12. **مدل‌های محلی Kev/Laya**: برای صفحهٔ screening، آیا runtime واقعی روی همین ماشین اجرا می‌شود یا فقط advisory از راه دور؟

---

## ۸) پیوست — فهرست مسیرهای موجود (۲۰۱ مسیر)

<!---->

| دامنه | مسیرها (خلاصه) |
|---|---|
| ai | `POST /api/ai/generate`, `GET /api/ai/providers`, `GET /api/ai/status`, `POST /api/ai/chat` |
| ai-routing | `POST /record`, `GET /stats`, `GET /routes`, `POST /apply` |
| alerts | `rules` CRUD/PATCH, `POST /evaluate`, `GET /alerts`, `/{id}`, `ack`, `resolve`, `deliver/pending`, `{id}/deliver/{channel}` |
| analogues | `GET /api/analogues`, `/{id}/aftermath` |
| archive | `storage`, `settings`, `catalog`, `catalog/{id}`, `validate`, `restore/dry-run`, `restore`, `purge/preview`, `telegram/{id}` |
| audit | `POST /log`, `GET /records`, `POST /replay`, `GET /engines` |
| auth | `POST /login` |
| briefings | `POST /daily`, `POST /weekly`, `GET /`, `GET /{id}` |
| claims | `POST /extract`, `POST /evidence`, `GET /`, `GET /{id}/evidence` |
| classify | `POST /run`, `GET /articles`, `GET /articles/{id}` |
| configuration | definitions, instances, revisions, validate, test, activate, rollback |
| debate | `POST /run`, `GET /runs`, `GET /runs/{id}`, `GET /scorecard` |
| decisions | `POST /run`, `POST /from-debate`, `GET /`, `GET /{id}` |
| dedup | `GET /clusters`, `POST /run` |
| dispatch | `status`, `jobs`, `{id}/retry`, `{id}/recover`, `run`, `articles/{id}` |
| economic | `fetch`, `observations`, `indicators`, `latest` |
| evaluation | `run`, `scores`, `summary` |
| events | `POST /extract`, `GET /` |
| forecasts | `run`, `GET /`, `ledger/active`, `{id}`, `{id}/supersede` |
| geopolitics | `analyze`, `assessments`, `tensions` |
| graph | `extract`, `entities`, `entities/{id}`, `relationships`, `neighbors/{id}` |
| health | `/health`, `/health/db` |
| independence | `run`, `dependencies` GET/POST/DELETE, `groups` |
| ingestion | `POST /ingest`, `/ingest/all`, `/ingest/bot`, `/ingest/jobs`, `GET /ingest/jobs/{id}`, `GET /ingest/documents` |
| iran | `brief`, `events`, `transmission/analyze`, `transmission` |
| jobs | `POST /trigger`, `GET /` |
| learning | `run`, `insights` |
| local-runtimes | `status`, `status/{name}`, `enabled`, `start`, `stop` |
| macro | `analyze`, `assessments`, `overview` |
| markets | `fetch`, `observations`, `symbols`, `latest` |
| memory | `archive`, `timeline`, `stats`, `records` |
| monitoring | `GET /api/ops/monitoring`, `GET /api/ops/metrics` |
| narratives | `build`, `GET /`, `GET /{id}` |
| ops | `GET /api/ops/status` |
| outcomes | `resolve`, `GET /`, `pending` |
| performance | `record`, `GET /`, `history` |
| portfolios | `POST /`, `GET /`, `GET /{id}`, `DELETE /{id}`, `snapshot`, `snapshots` |
| research | `graphrag`, `methods` |
| risk | `analyze`, `assessments`, `overview` |
| scenarios | `run`, `GET /` |
| screening | `screen`, `queue`, `review/{article_id}/ack` |
| selfeval | `run`, `latest`, `history` |
| settings | providers CRUD/key/test/models، models CRUD/verify/block، agent-assignments، diversity، app GET/PUT، import-from-env، void run/forecast، spend-today |
| society | `analyze`, `assessments`, `mood` |
| sources | `GET /`, `POST /`, `GET/PATCH /{id}`, `preview`, `health`, `recheck`, `export/all` |
| tournaments | `run`, `GET /`, `GET /{id}` |
| worldstate | `build`, `current`, `history` |

---

## ۹) محدودیت‌های این تحلیل

- UI با استخراج خودکار توابع/داده‌ها از فایل ۲۴۶KB بررسی شد؛ ممکن است برخی مقادیر نمونه داخل templateها که در این سند «داده» شمرده شده‌اند، در آینده با یک متغیر جایگزین شوند. ساختار و اقدام‌ها کامل استخراج شده‌اند.
- وضعیت endpointها از روی schemaهای Pydantic و مدل‌های SQLAlchemy خوانده شده؛ رفتار runtime (مثلاً پر بودن واقعی جدول‌ها) بررسی نشده است.
- «✅» یعنی قرارداد پاسخ کافی است، نه اینکه دادهٔ واقعی از قبل موجود است.
- Migrationها پیشنهاد شده‌اند، اما سازگاری با دادهٔ موجود و هزینهٔ backfill بررسی دقیق نشده است (به‌خصوص مختصات رویدادهای قدیمی).
- هیچ‌کدام از تست‌ها یا رفتار `.env`/production بررسی نشد؛ سند فقط تحلیل قرارداد است.

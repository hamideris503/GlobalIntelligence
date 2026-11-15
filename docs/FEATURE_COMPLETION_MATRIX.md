# ماتریس تکمیل قابلیت‌ها — GlobalIntelligence

**تاریخ:** ۱۵ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc` + dirty tree
**واژگان وضعیت (طبق Roadmap v2.2 §2.1):** `VERIFIED_COMPLETE` · `IMPLEMENTED_NOT_ACCEPTED` · `PARTIALLY_VERIFIED` · `NOT_VERIFIED` · `EVIDENCE_STALE` · `BLOCKED_OWNER_INPUT` · `BLOCKED_EXTERNAL` · `FAILED` · `DEFERRED_BY_OWNER` · `NOT_IMPLEMENTED` · `NOT_APPLICABLE`

> هیچ قابلیتی فقط به دلیل وجود فایل `VERIFIED` نشده است. ستون «شاهد امروز» یعنی چیزی که در همین ممیزی دیده یا اجرا شده.

---

## 1. سطح سیستم

| # | قابلیت | وضعیت | شاهد امروز | شکاف |
|---|---|---|---|---|
| 1 | Backend / FastAPI app factory | VERIFIED_COMPLETE | app ساخته شد، 220 path / 235 operation، `/` و `/health` 200 | — |
| 2 | API contract (error envelope, pagination) | VERIFIED_COMPLETE | 401/403/422 با `{error:{code,message,request_id}}` مشاهده شد | — |
| 3 | Database schema / migrations | PARTIALLY_VERIFIED | 51 revision، 1 head؛ ولی DDL SQLite خراب (GI-DB-001) | نوشتن روی SQLite |
| 4 | Authentication (session) | VERIFIED_COMPLETE | login 200 → `/api/auth/me` 200 با role=admin | — |
| 5 | Authorization / RBAC | VERIFIED_COMPLETE | `docs/ROLE_MATRIX.md` + `required_role()`؛ CSRF 403؛ 401 بدون هویت | سند یک route عقب است (GI-DOC-001) |
| 6 | CSRF | VERIFIED_COMPLETE | POST بدون token → 403 | — |
| 7 | Rate limiting | PARTIALLY_VERIFIED | middleware + جدول `login_attempts` در کد | تک‌فرایندی؛ چند worker پشتیبانی نمی‌شود |
| 8 | Security headers / CSP | VERIFIED_COMPLETE (CODE-INSPECTED) | `backend/core/security.py` | تست مرورگری اجرا نشد |
| 9 | SSRF guard | VERIFIED_COMPLETE (CODE-INSPECTED) | `GuardedTransport`, `host_is_private`, تست‌های امنیتی | — |
| 10 | Secrets / credential encryption | VERIFIED_COMPLETE (CODE-INSPECTED) | `credentials.py` Fernet + `APP_ENCRYPTION_KEY` SET | — |
| 11 | Logging / audit | VERIFIED_COMPLETE | `audit | action=auth.login` در لاگ واقعی | — |
| 12 | Backup / Restore | PARTIALLY_VERIFIED | `scripts/db_backup.py` (pg_dump داخل Docker) | SQLite/local بدون Docker پشتیبانی ندارد |
| 13 | Retention / disk monitoring | IMPLEMENTED_NOT_ACCEPTED | `domains/retention/service.py`, `disk_status` | اجرای E2E و purge تأیید نشد (پیش‌فرض خاموش) |
| 14 | Windows 24/7 runtime | **NOT_IMPLEMENTED** | WP-16 خودش DEFERRED | سرویس/Task Scheduler/runbook نیست |
| 15 | CI (remote) | NOT_VERIFIED | 3 job در فایل موجود | اجرای راه‌دور تأیید نشد؛ suite محلی سرخ |
| 16 | Docker stack | VERIFIED_COMPLETE (CODE-INSPECTED) | Docker 29.8.2 + Compose v5.6.0 نصب | در این نوبت compose up اجرا نشد |

---

## 2. هوش مصنوعی

| # | قابلیت | وضعیت | شاهد امروز | شکاف |
|---|---|---|---|---|
| 17 | AI Gateway (routing/retry/fallback/budget) | VERIFIED_COMPLETE | فراخوان زنده 200، `is_mock=false` | error-mapping در fallback (GI-AI-001) |
| 18 | Provider adapters (mock/gemini/openai/anthropic/openrouter/groq/cloudflare/local) | VERIFIED_COMPLETE (CODE-INSPECTED) | 13 ماژول provider؛ catalog API 200 | — |
| 19 | Free Policy | VERIFIED_COMPLETE | allowlist دقیق؛ `openrouter/free` مجاز | — |
| 20 | Budget / cost ledger | IMPLEMENTED_NOT_ACCEPTED | `backend/ai/budget.py` + `ai_token_ledger` | `cost_estimate:null` در پاسخ زنده → قیمت‌گذاری واقعی محاسبه نشد |
| 21 | Model/Provider catalog در UI | VERIFIED_COMPLETE | `/api/settings/providers/catalog` 7 kind با policy status | — |
| 22 | Local AI runtime (Kev/Laya) | BLOCKED (تصمیم مالک: خاموش تا Gold Set) | status=`DISABLED`؛ مسیرهای `H:` موجود | اجرای واقعی انجام نشد |
| 23 | Local screening (advisory) | IMPLEMENTED_NOT_ACCEPTED | `local_screening/*` + تست؛ dispatch `blocked` طراحی‌شده | بدون runtime، خروجی واقعی صفر |
| 24 | AI Chat | VERIFIED_COMPLETE | POST `/api/ai/chat` → `PONG` واقعی | — |
| 25 | AI Debate | PARTIALLY_VERIFIED | `domains/debate/*` + تست | اجرای چندمدلی واقعی انجام نشد |
| 26 | AI Evaluation Lab | PARTIALLY_VERIFIED | `domains/selfeval`, `/api/evaluation/*` | ارزیابی واقعی با Gold Set گزارش‌شده، بازتولید نشد |
| 27 | Gold Set انسانی | BLOCKED_OWNER_INPUT → اکنون موجود | manifest: 382 برچسب (295 مثبت/87 منفی)؛ فایل‌های `H:\GIRuntime\labeling` موجود | اتصال و ارزیابی مجدد انجام نشد |

---

## 3. داده و پردازش خبر

| # | قابلیت | وضعیت | شاهد امروز | شکاف |
|---|---|---|---|---|
| 28 | Ingestion واقعی RSS | VERIFIED_COMPLETE | BBC World: `fetched=5, stored=5` با عناوین واقعی | — |
| 29 | Source Management | PARTIALLY_VERIFIED | GET/POST API؛ ساخت روی SQLite مهاجرت‌شده 503 | GI-DB-001, GI-OPS-001 |
| 30 | Dedup / cluster | VERIFIED_COMPLETE | اجرای دوم: `stored=0, duplicates=5` | خوشه در inbox `null` (چون فقط یک منبع) |
| 31 | Priority / relevance | VERIFIED_COMPLETE | اخبار واقعی با `P2/P3` رتبه‌بندی شدند | — |
| 32 | Document raw + provenance | VERIFIED_COMPLETE | `documents=3→8` همگام با مقالات | — |
| 33 | Classification (قواعد + AI) | PARTIALLY_VERIFIED | ساختار و تست موجود؛ `classified=0` در اجرای ما | AI classification در ingest اجرا نشد |
| 34 | Article dispatch (durable/idempotent) | PARTIALLY_VERIFIED | `/api/dispatch/status` 200؛ کد claim با `SKIP LOCKED` | هیچ task واقعی در اجرای ما تولید نشد |
| 35 | Source Bot | PARTIALLY_VERIFIED | `source_bot/*` + scheduler + lock | lock در temp؛ stop path `/tmp`؛ 24/7 ندارد |
| 36 | n8n workflows | NOT_VERIFIED | JSONها موجود؛ compose سرویس n8n دارد | import/اجرا انجام نشد |

---

## 4. تحلیل دامنه‌ای

| # | قابلیت | وضعیت | شاهد | شکاف |
|---|---|---|---|---|
| 37 | Economic/Macro (World Bank واقعی) | VERIFIED_COMPLETE (CODE) | `WorldBankFetcher` واقعی + Mock جدا | اجرای زنده انجام نشد |
| 38 | Markets (er-api/ECB/gold-api/Yahoo) | VERIFIED_COMPLETE (CODE) | 5 fetcher واقعی + mock | اجرای زنده انجام نشد |
| 39 | Geopolitics | PARTIALLY_VERIFIED | `domains/geopolitics/*` + API | اجرای واقعی با داده کافی انجام نشد |
| 40 | Iran domain | PARTIALLY_VERIFIED | `/api/iran/brief` + دامنه | داده واقعی نداشت |
| 41 | Country profile (US دوم) | IMPLEMENTED_NOT_ACCEPTED | `country_profile` + `/api/country-profiles` | پروفایل US ساخته/seed نشد |
| 42 | Entity extraction | PARTIALLY_VERIFIED | `domains/events/actor_extraction.py`؛ جدول `entities` | `domains/entities/` خالی است؛ entities=0 |
| 43 | Claims & Evidence | PARTIALLY_VERIFIED | `domains/claims/*` (7 فایل) + API | evidence=0 (وابسته به آنالیز) |
| 44 | Knowledge Graph / GraphRAG | PARTIALLY_VERIFIED | `domains/graph/*`, `domains/research/graphrag.py` | ارزیابی با پاسخ synthetic؛ گراف واقعی ساخته نشد |
| 45 | Forecast engine | PARTIALLY_VERIFIED (CODE) | `domains/forecast/*` (14 فایل) + API | پیش‌بینی واقعی بدون provider/داده ثبت نشد |
| 46 | Scenario engine | PARTIALLY_VERIFIED | `domains/scenarios/*` | خروجی واقعی صفر |
| 47 | Risk engine | PARTIALLY_VERIFIED | `domains/risk/*`, `/api/risk/*` | ماتریس واقعی بدون داده محاسبه نشد |
| 48 | Decision support | PARTIALLY_VERIFIED | `domains/decision/*` | توصیه واقعی صفر |
| 49 | Memory | PARTIALLY_VERIFIED | `domains/memory/*` + جدول | مصرف مؤثر اثبات نشد |
| 50 | World Monitor / map | PARTIALLY_VERIFIED | `worldMonitorPage()` + `/api/geo/events`؛ state=`DISABLED`-like خالی | رویداد geo واقعی صفر |
| 51 | Translation (offline) | IMPLEMENTED_NOT_ACCEPTED | `domains/translation/*` | اجرای واقعی انجام نشد |

---

## 5. UI و گزارش‌دهی

| # | قابلیت | وضعیت | شاهد | شکاف |
|---|---|---|---|---|
| 52 | Single-file UI shell (26 صفحه) | VERIFIED_COMPLETE | 495 KB سرو شد؛ 26 registry؛ nav/route | — |
| 53 | اتصال صفحات به API واقعی | VERIFIED_COMPLETE برای صفحات دیده‌شده | 18 کانتینر live + 36 loader؛ dashboard KPIs واقعی | برخی صفحات هنوز بلوک نمونه دارند |
| 54 | Charts | PARTIALLY_VERIFIED | SVG chart واقعی از `risk_series` | `chartPanel` با نقاط ثابت نمونه باقی است |
| 55 | Notifications / Alerts | PARTIALLY_VERIFIED | `delivery.py` (Telegram + SMTP واقعی) | ارسال زنده انجام نشد |
| 56 | Telegram archive | CODE-INSPECTED | `send_archive_to_telegram`, `download_file`, roundtrip | نیازمند credential |
| 57 | Archive build/validate/restore | PARTIALLY_VERIFIED | `/api/archive/*` ۹ operation؛ تست‌ها | اجرای واقعی restore انجام نشد |
| 58 | Settings / Control plane | VERIFIED_COMPLETE | 24 operation؛ catalog 200 | — |
| 59 | Export/report pages | PARTIALLY_VERIFIED | `/api/briefings/*`, `reportsPage()` | خروجی فایل واقعی تولید نشد |
| 60 | Accessibility / RTL / responsive | NOT_VERIFIED | 1 spec axe موجود | اجرا نشد |

---

## 6. تست

| # | قابلیت | وضعیت | شاهد |
|---|---|---|---|
| 61 | Unit/Integration (SQLite lane) | **FAILED** | 9 failed / 1900 passed / 1 skipped |
| 62 | PostgreSQL lane | EVIDENCE_STALE | آخرین اعداد از گزارش قبلی؛ در این نوبت اجرا نشد |
| 63 | Migration up/down/up | PARTIALLY_VERIFIED | زنجیره سالم و single-head؛ downgrade در این نوبت اجرا نشد |
| 64 | E2E Playwright | NOT_VERIFIED | 7 spec موجود؛ در CI نیست؛ اجرا نشد |
| 65 | Windows compatibility tests | NOT_IMPLEMENTED | هیچ lane مخصوص Windows در CI نیست |
| 66 | Security tests | PARTIALLY_VERIFIED | تست‌های SSRF/CSRF/rate-limit در suite | suite سرخ؛ اجرای تفکیکی انجام نشد |

---

## 7. نقشه‌راه Stage 96–104

| Stage | هدف | ادعای قبلی | وضعیت واقعی امروز | شاهد/شکاف |
|---|---|---|---|---|
| 96 | تثبیت PG + CI | COMPLETE | PARTIALLY_VERIFIED | فایل CI درست است؛ اجرای راه‌دور NOT_VERIFIED؛ suite محلی سرخ |
| 97 | Gold Set + ارزیابی | VERIFIED/PARTIAL | PARTIALLY_VERIFIED | 382 برچسب معتبر (manifest)؛ ارزیابی مجدد انجام نشد |
| 98 | Alert delivery + Settings | VERIFIED | PARTIALLY_VERIFIED | کد کانال‌ها واقعی؛ ارسال زنده تست نشد |
| 99 | Country profile قابل تنظیم | VERIFIED | IMPLEMENTED_NOT_ACCEPTED | پروفایل دوم (US) پر نشد |
| 100 | Retention + disk | VERIFIED | IMPLEMENTED_NOT_ACCEPTED | dry-run موجود؛ اجرا/پایش واقعی نه |
| 101 | ترجمه آفلاین | VERIFIED | IMPLEMENTED_NOT_ACCEPTED | کد موجود؛ اجرای واقعی نه |
| 102 | بدهی فنی/مقیاس | VERIFIED | PARTIALLY_VERIFIED | SKIP LOCKED/ETag/JobRun رفع شده؛ N+1 و Text→JSONB باز |
| 103 | VPS/TLS | OUT OF SCOPE | NOT_APPLICABLE | طبق v2.2 خارج از دامنه |
| 104 | کالیبراسیون پیش‌بینی | PARTIAL | NOT_VERIFIED | نیازمند پیش‌بینی واقعی چندماهه |

## 8. Work Packageهای v2.2

| WP | وضعیت ادعایی | وضعیت ممیزی | دلیل |
|---|---|---|---|
| 00 | VERIFIED | VERIFIED | وضعیت Git/شمارش‌ها امروز بازتولید شد |
| 01 | VERIFIED | VERIFIED | Secrets فقط حضورشان بررسی شد |
| 02 | VERIFIED (CI NOT_VERIFIED) | PARTIALLY_VERIFIED | suite محلی سرخ (9 failure) |
| 03 | VERIFIED | VERIFIED | UI manifest و صفحات شمارش شد |
| 04 | VERIFIED | VERIFIED | login/session/CSRF زنده اثبات شد |
| 05 | VERIFIED | PARTIALLY_VERIFIED | 26 صفحه واقعی؛ بعضی بلوک‌ها نمونه‌اند |
| 06 | VERIFIED | VERIFIED | configuration plane پاسخ 200 |
| 07 | VERIFIED (live AI BLOCKED) | VERIFIED_COMPLETE | **live AI امروز کار کرد** (openrouter) |
| 07.1 | VERIFIED | IMPLEMENTED_NOT_ACCEPTED | lifecycle تست دارد ولی promotion واقعی اجرا نشد |
| 08 | READY_FOR_EVALUATION | PARTIALLY_VERIFIED | دیتاست معتبر؛ ارزیابی مجدد نشد |
| 09 | VERIFIED | FAILED (روی SQLite) | ساخت منبع 503 |
| 10 | VERIFIED | VERIFIED | گاردها و تست‌ها موجود |
| 11 | VERIFIED | PARTIALLY_VERIFIED | dedup زنده اثبات شد؛ provenance/cluster کامل نه |
| 12 | VERIFIED | PARTIALLY_VERIFIED | کد و API سالم؛ task واقعی تولید نشد |
| 13 | PARTIAL | PARTIALLY_VERIFIED | تحلیل end-to-end با AI واقعی اجرا نشد |
| 14 | VERIFIED | PARTIALLY_VERIFIED | alert live تست نشد |
| 15 | VERIFIED | IMPLEMENTED_NOT_ACCEPTED | restore واقعی اجرا نشد |
| 16 | NOT_VERIFIED/DEFERRED | **NOT_IMPLEMENTED** | هیچ سرویس/runbook اجرایی نیست |
| 17 | VERIFIED | PARTIALLY_VERIFIED | Ruff پاک؛ ولی مستندات عددی کهنه |
| 18 | VERIFIED | **FAILED** | ادعای «1908 passed» با 9 failure امروز نمی‌خواند |

---

## 9. درصد پیشرفت

**N/A** — طبق §2.2 نقشه‌راه v2.2، درصد کلی بدون ماتریس وزن‌دهی مستند ممنوع است و در مخزن چنین ماتریسی با وزن‌های مصوب وجود ندارد. جایگزین: شمارش معیارها در جدول‌های بالا (VERIFIED / PARTIAL / NOT_IMPLEMENTED / BLOCKED).


---

## به‌روزرسانی ماتریس — ۱۴ نوامبر ۲۰۲۶

| قابلیت | وضعیت قبلی | وضعیت جدید | شاهد |
|---|---|---|---|
| RSS Ingestion | PARTIAL (بدون مسیر UI) | **VERIFIED_COMPLETE** | E2E واقعی: ساخت منبع از UI → `fetched=20, stored=20` |
| Deduplication | VERIFIED (تست) | **VERIFIED_COMPLETE (عملیاتی)** | اجرای دوم: `fetched=20, stored=0, duplicates=20`؛ articles بدون تغییر |
| Priority Engine | VERIFIED | **VERIFIED_COMPLETE** | خروجی classification واقعی + banding |
| AI Gateway / Free Policy | FAILED (۹ تست) | **VERIFIED_COMPLETE** | ۱۹۱۲/۱۹۱۳ passed؛ خطای واقعی Provider حفظ می‌شود |
| Analysis Chain (Article→Event→Claim→Evidence→Graph) | IMPLEMENTED_NOT_ACCEPTED | **VERIFIED_COMPLETE (یک trace)** | `PHASE_06_REPORT.md` |
| Provider/Model Provenance | PARTIAL | **VERIFIED_COMPLETE** | `classification_meta` + `article_dispatches.meta` با provider/model/is_mock |
| Backup/Restore | PG-only | **VERIFIED_COMPLETE (SQLite)** | backup/restore/verify واقعی + ۶ تست |
| Retention/Disk Monitoring | IMPLEMENTED | **VERIFIED_COMPLETE (dry-run)** | `/api/retention/dry-run`، `/api/retention/disk` |
| Local Screening (Kev/Laya) | NOT_IMPLEMENTED (active) | **PARTIALLY_VERIFIED** | اعتبارسنجی ۳۸۲ ردیف انجام شد؛ ارزیابی اجرا نشد |
| Telegram/SMTP Delivery | NOT_VERIFIED | **BLOCKED_OWNER_INPUT** | نیازمند تأیید ارسال واقعی |
| Windows 24/7 Runtime | NOT_IMPLEMENTED | **IMPLEMENTED_NOT_ACCEPTED** | اسکریپت + Runbook؛ نصب/soak اجرا نشد |
| CI راه‌دور | NOT_VERIFIED | **NOT_VERIFIED** | بدون push |

درصد پیشرفت همچنان **N/A** است (بدون ماتریس وزن‌دهی مصوب).

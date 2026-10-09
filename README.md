# GlobalIntelligence

> **Self-Hosted, Free-First, Evidence-Driven Global Intelligence & Decision Support Platform**

یک پلتفرم هوش اطلاعاتی، اقتصادی، مالی، ژئوپلیتیکی و پیش‌بینی که جهان را رصد می‌کند، داده را به شواهد ساختاریافته تبدیل می‌کند، وضعیت جهانی را می‌سازد، پیش‌بینی ثبت می‌کند و بعداً نتیجه پیش‌بینی‌ها را با واقعیت مقایسه می‌کند.

---

## وضعیت پروژه

**Phase فعلی: 43 — Alerts**
**Status: DONE**

> ⚠️ Alerts ساخته شد: قواعد آستانه‌ای روی متریک‌های نام‌دار ارزیابی و هشدار با cooldown ثبت می‌شود. مرحله‌ی بعد Security Hardening است.

---

## اصل حاکم

> هرجا امکان استفاده از پروژه متن‌باز، کتابخانه معتبر، دیتای رایگان، استاندارد موجود یا سرویس رایگان وجود دارد، ابتدا از آن استفاده می‌کنیم و فقط چیزی را خودمان می‌سازیم که واقعاً لازم است.

قوانین بنیادین پروژه:

- **Free-First:** هیچ API پولی نباید برای اجرای هسته اجباری باشد.
- **Provider-Agnostic:** وابستگی مستقیم به یک مدل AI ممنوع است؛ همه از طریق AI Gateway.
- **Evidence-Driven:** هر نتیجه باید شواهد موافق/مخالف و Confidence داشته باشد.
- **Explainable / Auditable / Reproducible:** هر تصمیم قابل بازسازی است.
- **Point-in-Time Integrity:** در زمان T از داده‌ای که هنوز منتشر نشده استفاده نمی‌کنیم.
- **No Fake Precision:** عدد بدون منبع، زمان و عدم قطعیت ممنوع.
- در نبود شواهد کافی، **INSUFFICIENT_EVIDENCE** برمی‌گردانیم.

---

## این پروژه چه چیزی نیست

- خبرخوان ساده / چت‌بات ساده
- اتصال مستقیم یک LLM به یک صفحه وب
- داشبورد پر از نمودار بدون موتور تحلیلی
- پیش‌بینی بدون ثبت نتیجه قبلی
- سیستم معامله خودکار با پول واقعی
- مجموعه‌ای از Microserviceها از روز اول

---

## معماری کلان (Logical Pipeline)

```
WORLD
  → DATA COLLECTION
  → NORMALIZATION
  → DEDUPLICATION
  → SOURCE & EVIDENCE ANALYSIS
  → EVENT / CLAIM / ENTITY EXTRACTION
  → CENTRAL DATABASE
  → WORLD STATE
  → MACRO / MARKET / GEOPOLITICAL / SOCIAL ANALYSIS
  → HISTORICAL MEMORY
  → FORECAST ENGINE
  → SCENARIO ENGINE
  → RISK ENGINE
  → DECISION ENGINE
  → RECOMMENDATION
  → ACTUAL OUTCOME
  → EVALUATION
  → MODEL PERFORMANCE
  → SELF-IMPROVEMENT
```

جزئیات کامل معماری در [`ARCHITECTURE.md`](ARCHITECTURE.md) آمده است.

---

## Stack

| لایه | فناوری | وضعیت |
|---|---|---|
| Frontend | React + Vite (RTL، Persian، Dark Mode) | پایه ساخته‌شده |
| Backend | Python + FastAPI | پیاده‌سازی‌شده |
| Orchestration | n8n (pinned 2.42.4) | پیاده‌سازی‌شده |
| Database | PostgreSQL 16 (بعداً TimescaleDB در صورت نیاز) | پیاده‌سازی‌شده |
| Cache/Queue | Redis (فقط در صورت نیاز واقعی) | به تعویق افتاده |
| AI | AI Gateway چند-Provider (Mock-first، Provider-Agnostic) | پیاده‌سازی‌شده |
| Packaging | Docker + docker-compose | پیاده‌سازی‌شده |

---

## شروع سریع

```bash
git clone <repo-url>
cd GlobalIntelligence
cp .env.example .env          # مقادیر محلی را تنظیم کنید (MOCK_MODE=true)

# بررسی محیط (بدون وابستگی خارجی)
python scripts/check_env.py
```

### اجرا با Docker (نیازمند Docker Desktop در حال اجرا)
```bash
docker compose up -d --build
# Backend API:  http://localhost:8000/health
# API docs:     http://localhost:8000/docs
# Frontend:     http://localhost:5173
# n8n:          http://localhost:5678
```

### اجرای محلی بدون Docker
```bash
# Backend
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload

# Frontend
cd apps/web
npm ci          # نصب تمیز و قابل‌بازتولید از روی package-lock
npm run dev
```

> نکته: اگر PostgreSQL در حال اجرا نباشد، `/health/db` وضعیت `degraded` برمی‌گرداند اما سرور کار می‌کند (بدون crash).

### دیتابیس و migration
```bash
# اجرای migration‌ها (در Docker به‌صورت خودکار در entrypoint اجرا می‌شود)
python -m alembic upgrade head

# seed منابع اولیه
docker compose exec backend python -m db.seed.sources
```

### بسته‌ی اشتراکی تمیز (بدون secret)
```bash
# آرشیو قابل‌اشتراک می‌سازد؛ .env محلی شما دست‌نخورده می‌ماند.
# کنارگذاشته‌ها: .env، .git، venvها، node_modules، dist، کش‌ها، logها، داده محلی
# فقط .env.example در بسته می‌ماند + اسکن خودکار secret (بدون چاپ مقدار).
powershell -ExecutionPolicy Bypass -File scripts/build_clean_archive.ps1
```

> ⚠️ اگر `.env` حاوی کلید واقعی را جایی به اشتراک گذاشته‌اید، آن کلیدها را از پنل سرویس باطل و دوباره تولید کنید.

---

## مستندات

| فایل | توضیح |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | معماری فنی، لایه‌ها، موجودیت‌ها |
| [ROADMAP.md](ROADMAP.md) | نقشه راه ۵۲ فاز |
| [TASKS.md](TASKS.md) | کارهای TODO / IN_PROGRESS / DONE / BLOCKED |
| [PROGRESS.md](PROGRESS.md) | گزارش پیشرفت هر مرحله |
| [DECISIONS.md](DECISIONS.md) | ثبت تصمیمات معماری (ADR) |
| [LICENSES.md](LICENSES.md) | پروژه‌های متن‌باز استفاده‌شده |
| [DATA_SOURCES.md](DATA_SOURCES.md) | رجیستری منابع داده |
| [AI_MODELS.md](AI_MODELS.md) | Providerها، مدل‌ها و نقش‌ها |

---

## مجوز

مجوز این پروژه MIT است (فایل [LICENSE](LICENSE)). تصمیم در [DECISIONS.md](DECISIONS.md) (ADR-0006) ثبت شده است. پروژه‌های استفاده‌شده در [LICENSES.md](LICENSES.md) پیگیری می‌شوند.

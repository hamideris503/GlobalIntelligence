# GlobalIntelligence

> **Self-Hosted, Free-First, Evidence-Driven Global Intelligence & Decision Support Platform**

یک پلتفرم هوش اطلاعاتی، اقتصادی، مالی، ژئوپلیتیکی و پیش‌بینی که جهان را رصد می‌کند، داده را به شواهد ساختاریافته تبدیل می‌کند، وضعیت جهانی را می‌سازد، پیش‌بینی ثبت می‌کند و بعداً نتیجه پیش‌بینی‌ها را با واقعیت مقایسه می‌کند.

---

## وضعیت پروژه

**Phase فعلی: 10 — Article Classification**
**Status: DONE**

> ⚠️ طبقه‌بندی مقالات ساخته شد: topics/entities/sentiment/stance و Importance Score ترکیبی (deterministic). مرحله‌ی بعد Event Extraction است.

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
- برو از **INSUFFICIENT_EVIDENCE** برای پرسش‌هایی که شواهد کافی ندارند عقب‌نشینی می‌کنیم.

---

## این پروژه چه چیزی نیست

- خبرخوان ساده / چت‌بات ساده
- اتصال مستقیم یک LLM به یک صفحه وب
- داشبورد پرم از نمودار بدون موتور تحلیلی
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

## Stack اولیه (Phase 2+)

| لایه | فناوری | وضعیت |
|---|---|---|
| Frontend | React + Vite (RTL، Persian، Dark Mode) | برنامه‌ریزی‌شده |
| Backend | Python + FastAPI | برنامه‌ریزی‌شده |
| Orchestration | n8n | برنامه‌ریزی‌شده |
| Database | PostgreSQL (بعداً TimescaleDB در صورت نیاز) | برنامه‌ریزی‌شده |
| Cache/Queue | Redis (فقط در صورت نیاز واقعی) | به تعویق افتاده |
| AI | AI Gateway چند-Provider (Mock-first) | برنامه‌ریزی‌شده |
| Packaging | Docker + docker-compose | برنامه‌ریزی‌شده |

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
npm install
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

مجوز این پروژه در Phase 0 هنوز نهایی نشده است. تصمیم در [`DECISIONS.md`](DECISIONS.md) ثبت میشود. پروژه‌های استفاده‌شده در [`LICENSES.md`](LICENSES.md) پیگیری می‌شوند.

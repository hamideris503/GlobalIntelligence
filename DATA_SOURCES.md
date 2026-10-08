# DATA_SOURCES.md

> رجیستری منابع داده. هر منبع پیش از استفاده باید در جدول `Source` (Phase 7) ثبت و ارزیابی شود.
> اصل: **Free-First** — ابتدا منابع رایگان و معتبر بررسی می‌شوند.

---

## فیلدهای ثبت منبع (Source Registry)

| فیلد | توضیح |
|---|---|
| source_id | شناسه یکتا |
| name | نام منبع |
| domain | دامنه/سازمان |
| country | کشور مبدأ |
| type | rss / api / dataset / official / scrape |
| language | زبان |
| credibility_score | امتیاز اعتبار اولیه |
| historical_accuracy | دقت تاریخی (بعداً از عملکرد واقعی) |
| correction_rate | نرخ اصلاح |
| independence_score | استقلال از سایر منابع |
| primary_source_ratio | نسبت منبع اولیه بودن |
| latency | تأخیر انتشار |
| license | مجوز استفاده از داده |
| terms | شرایط استفاده |
| collection_method | روش جمع‌آوری |
| active | فعال/غیرفعال |
| last_success | آخرین موفقیت |
| last_error | آخرین خطا |

> نکته: **تعداد mention ≠ تعداد تأیید مستقل.** سیستم باید Source Independence را تخمین بزند.

---

## منابع پیاده‌سازی‌شده (Seed — Phase 7)

این منابع در `db/seed/sources.py` ثبت شده‌اند و از طریق `/api/sources` قابل مدیریت‌اند.
مقادیر credibility/independence **اولیه و محافظه‌کارانه** هستند و بعداً از عملکرد واقعی
(بند 56-58) به‌روزرسانی می‌شوند.

| Name | Domain | Country | Type | Language |
|---|---|---|---|---|
| Federal Reserve Press Releases | federalreserve.gov | US | rss | en |
| ECB Press Releases | ecb.europa.eu | — | rss | en |
| Reuters Business (via Google News) | news.google.com | — | rss | en |
| BBC Business | feeds.bbci.co.uk | GB | rss | en |
| Al Jazeera | aljazeera.com | — | rss | en |
| IMF World Economic Outlook | imf.org | — | dataset | en |
| World Bank Open Data | worldbank.org | — | dataset | en |
| US FRED | stlouisfed.org | US | api | en |
| ECB Data Portal | ecb.europa.eu | — | official | en |
| OECD Data | oecd.org | — | dataset | en |
| US BLS | bls.gov | US | official | en |
| Stooq | stooq.com | — | dataset | en |
| Yahoo Finance | finance.yahoo.com | — | api | en |
| World Gold Council | gold.org | — | official | en |
| CoinGecko | coingecko.com | — | api | en |
| GDELT | gdeltproject.org | — | dataset | en |
| ACLED | acleddata.com | — | dataset | en |
| Central Bank of Iran | cbi.ir | IR | official | fa |
| Statistical Center of Iran | amar.org.ir | IR | official | fa |

> ۵ منبع نخست (RSS) فید خبری واقعی دارند (`feed_url`) و منبع Milestone 1 هستند.

### API رجیستری منابع
| متد | مسیر | کار |
|---|---|---|
| GET | `/api/sources` | لیست (فیلتر: active, country, type) |
| POST | `/api/sources` | افزودن منبع |
| GET | `/api/sources/{id}` | جزئیات |
| PATCH | `/api/sources/{id}` | به‌روزرسانی |
| POST | `/api/sources/{id}/health` | ثبت موفقیت/خطا |

---

## منابع کاندید (بررسی‌نشده — Proposed)

### رسمی / بین‌المللی
- IMF (World Economic Outlook, IFS), World Bank Open Data, OECD, BIS, UN Data
- Eurostat, US FRED (St. Louis Fed), ECB, US Federal Reserve
- Bank for International Settlements

### آماری ملی
- Statistical agencies (US BLS, Census; UK ONS; …)

### بازارها (رایگان / محدود)
- Yahoo Finance, Stooq, Alpha Vantage (free tier), FRED series
- CoinGecko (crypto), World Gold Council (gold)

### خبر و رویداد
- RSS خبرگزاری‌های معتبر بین‌المللی
- Reuters / AP / AFP (بررسی terms)
- Official press releases (central banks, governments)

### ژئوپلیتیک / OSINT
- ACLED (conflict data), GDELT (event data)
- Official government statements

### ایران (Iran Intelligence Mode)
- مرکز آمار ایران، بانک مرکزی ایران (CBI)
- بازار طلا/سکه/ارز (بررسی منابع مجاز)
- بورس تهران (TSE)

---

## منابع نیازمند بررسی دقیق Terms
> برخی منابع محدودیت استفاده تجاری/API دارند و پیش از استفاده باید بررسی شوند:
> Reuters/AP/AFP API، Twitter/X، برخی خبرگزاری‌ها.

---

## قواعد جمع‌آوری
1. احترام به `robots.txt` و rate limit (`SOURCE_MIN_INTERVAL_SECONDS`).
2. ثبت `published_at` و `retrieved_at` برای هر datum (Point-in-Time Integrity).
3. ذخیره Raw Document قبل از هر تبدیل (raw layer).
4. هر منبع باید قابل غیرفعال‌سازی سریع باشد (`active=false`) بدون Crash سیستم.
5. ارائه‌ی هر عدد همراه با منبع و زمان الزامی است.

> جدول عملیاتی منابع در Phase 7 به‌عنوان seed در `db/seed/` ساخته می‌شود.

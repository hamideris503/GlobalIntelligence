"""Seed Source Registry (بند 16-17; اصلاح Phase 10).

شامل منابع خبری واقعی با RSS رسمی (برای Milestone 1) و منابع داده‌ی
اقتصادی/بازار (برای فازهای ۱۶ و ۱۷).

آدرس‌های RSS زیر فیدهای عمومی و پایدارند. license/terms هر منبع در همان ردیف
ثبت شده و پیش از استفاده‌ی تجاری باید بازبینی شود.

اجرا:
    python -m db.seed.sources
"""
from __future__ import annotations

from backend.database.enums import SourceType
from backend.database.models import Source
from backend.database.session import get_session_factory

INITIAL_SOURCES: list[dict[str, object]] = [
    # ================= خبری واقعی (RSS) — Milestone 1 =================
    {
        "name": "Federal Reserve Press Releases",
        "domain": "federalreserve.gov", "country": "US", "type": SourceType.rss.value,
        "language": "en", "collection_method": "rss",
        "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "credibility_score": 0.97, "independence_score": 0.95,
        "primary_source_ratio": 0.98, "license": "public domain (US Gov)",
    },
    {
        "name": "ECB Press Releases",
        "domain": "ecb.europa.eu", "country": None, "type": SourceType.rss.value,
        "language": "en", "collection_method": "rss",
        "feed_url": "https://www.ecb.europa.eu/rss/press.html",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.95, "license": "ECB terms",
    },
    {
        "name": "Reuters Business (via Google News)",
        "domain": "news.google.com", "country": None, "type": SourceType.rss.value,
        "language": "en", "collection_method": "rss",
        "feed_url": "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en",
        "credibility_score": 0.7, "independence_score": 0.45,
        "primary_source_ratio": 0.25, "license": "aggregator — review terms",
    },
    {
        "name": "BBC Business",
        "domain": "feeds.bbci.co.uk", "country": "GB", "type": SourceType.rss.value,
        "language": "en", "collection_method": "rss",
        "feed_url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "credibility_score": 0.82, "independence_score": 0.75,
        "primary_source_ratio": 0.55, "license": "BBC terms",
    },
    {
        "name": "Al Jazeera",
        "domain": "aljazeera.com", "country": None, "type": SourceType.rss.value,
        "language": "en", "collection_method": "rss",
        "feed_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "credibility_score": 0.78, "independence_score": 0.65,
        "primary_source_ratio": 0.5, "license": "Al Jazeera terms",
    },
    # ================= داده‌ی اقتصادی / بازار (فازهای ۱۶-۱۷) =================
    {
        "name": "IMF World Economic Outlook",
        "domain": "imf.org", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.95, "license": "IMF terms",
    },
    {
        "name": "World Bank Open Data",
        "domain": "worldbank.org", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.93, "independence_score": 0.9,
        "primary_source_ratio": 0.9, "license": "CC-BY 4.0",
    },
    {
        "name": "US FRED",
        "domain": "stlouisfed.org", "country": "US", "type": SourceType.api.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.9,
    },
    {
        "name": "OECD Data",
        "domain": "oecd.org", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.92, "independence_score": 0.88,
        "primary_source_ratio": 0.9,
    },
    {
        "name": "ECB Data Portal",
        "domain": "ecb.europa.eu", "country": None, "type": SourceType.official.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.95,
    },
    {
        "name": "US BLS",
        "domain": "bls.gov", "country": "US", "type": SourceType.official.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.95,
    },
    {
        "name": "Stooq",
        "domain": "stooq.com", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "scrape",
        "credibility_score": 0.75, "independence_score": 0.55,
        "primary_source_ratio": 0.3,
    },
    {
        "name": "Yahoo Finance",
        "domain": "finance.yahoo.com", "country": None, "type": SourceType.api.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.75, "independence_score": 0.5,
        "primary_source_ratio": 0.25,
    },
    {
        "name": "World Gold Council",
        "domain": "gold.org", "country": None, "type": SourceType.official.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.85, "independence_score": 0.8,
        "primary_source_ratio": 0.7,
    },
    {
        "name": "CoinGecko",
        "domain": "coingecko.com", "country": None, "type": SourceType.api.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.8, "independence_score": 0.7,
        "primary_source_ratio": 0.6,
    },
    {
        "name": "GDELT",
        "domain": "gdeltproject.org", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.7, "independence_score": 0.5,
        "primary_source_ratio": 0.2,
    },
    {
        "name": "ACLED",
        "domain": "acleddata.com", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.85, "independence_score": 0.8,
        "primary_source_ratio": 0.6, "license": "ACLED terms (attribution)",
    },
    # ================= ایران =================
    {
        "name": "Central Bank of Iran",
        "domain": "cbi.ir", "country": "IR", "type": SourceType.official.value,
        "language": "fa", "collection_method": "scrape",
        "credibility_score": 0.8, "independence_score": 0.85,
        "primary_source_ratio": 0.9,
    },
    {
        "name": "Statistical Center of Iran",
        "domain": "amar.org.ir", "country": "IR", "type": SourceType.official.value,
        "language": "fa", "collection_method": "scrape",
        "credibility_score": 0.8, "independence_score": 0.85,
        "primary_source_ratio": 0.9,
    },
]


def seed() -> int:
    """منابع جدید را اضافه و رکوردهای موجود را تکمیل می‌کند."""
    session = get_session_factory()()
    created = 0
    updated = 0
    try:
        for data in INITIAL_SOURCES:
            existing = session.query(Source).filter_by(name=data["name"]).first()
            if existing is None:
                session.add(Source(**data))
                created += 1
                continue
            for key, value in data.items():
                if key == "name":
                    continue
                if getattr(existing, key, None) is None and value is not None:
                    setattr(existing, key, value)
                    updated += 1
        session.commit()
    finally:
        session.close()
    if updated:
        print(f"(enriched {updated} field(s) on existing sources)")
    return created


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} new source(s)")

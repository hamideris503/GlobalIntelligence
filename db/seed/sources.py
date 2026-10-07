"""Seed اولیه‌ی Source Registry (بند 16-17).

منابع رایگان و معتبر. مقادیر credibility/independence **اولیه و محافظه‌کارانه**
هستند و در فازهای بعدی از عملکرد واقعی (بند 56-58) به‌روزرسانی می‌شوند.

اجرا:
    python -m db.seed.sources
"""
from __future__ import annotations

from backend.database.enums import SourceType
from backend.database.models import Source
from backend.database.session import get_session_factory

# نوع به‌صورت رشته ذخیره می‌شود (مدل، String دارد)
INITIAL_SOURCES: list[dict[str, object]] = [
    # --- رسمی / بین‌المللی ---
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
        "name": "ECB Data Portal",
        "domain": "ecb.europa.eu", "country": None, "type": SourceType.official.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.95,
    },
    {
        "name": "OECD Data",
        "domain": "oecd.org", "country": None, "type": SourceType.dataset.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.92, "independence_score": 0.88,
        "primary_source_ratio": 0.9,
    },
    {
        "name": "US BLS",
        "domain": "bls.gov", "country": "US", "type": SourceType.official.value,
        "language": "en", "collection_method": "api",
        "credibility_score": 0.95, "independence_score": 0.9,
        "primary_source_ratio": 0.95,
    },
    # --- بازارها ---
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
    # --- رویداد / OSINT ---
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
    # --- ایران ---
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
    """منابع جدید را اضافه و رکوردهای موجود را تکمیل می‌کند.

    Returns: تعداد منابعی که *تازه ساخته* شدند.
    """
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
            # تکمیل فیلدهای خالی (بدون بازنویسی داده‌ی موجود)
            for key, value in data.items():
                if key in ("name",):
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

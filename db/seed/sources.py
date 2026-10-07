"""Seed اولیه: چند منبع معتبر اولیه (بند 16-17).

اجرا:
    python -m db.seed.sources
"""
from __future__ import annotations

from backend.database.enums import SourceType
from backend.database.models import Source
from backend.database.session import get_session_factory

INITIAL_SOURCES = [
    {
        "name": "IMF World Economic Outlook",
        "domain": "imf.org",
        "country": None,
        "type": SourceType.dataset,
        "language": "en",
        "collection_method": "api",
    },
    {
        "name": "World Bank Open Data",
        "domain": "worldbank.org",
        "country": None,
        "type": SourceType.dataset,
        "language": "en",
        "collection_method": "api",
    },
    {
        "name": "US FRED",
        "domain": "stlouisfed.org",
        "country": "US",
        "type": SourceType.api,
        "language": "en",
        "collection_method": "api",
    },
    {
        "name": "ECB",
        "domain": "ecb.europa.eu",
        "country": None,
        "type": SourceType.official,
        "language": "en",
        "collection_method": "api",
    },
    {
        "name": "Central Bank of Iran",
        "domain": "cbi.ir",
        "country": "IR",
        "type": SourceType.official,
        "language": "fa",
        "collection_method": "scrape",
    },
    {
        "name": "Statistical Center of Iran",
        "domain": "amar.org.ir",
        "country": "IR",
        "type": SourceType.official,
        "language": "fa",
        "collection_method": "scrape",
    },
]


def seed() -> int:
    session = get_session_factory()()
    created = 0
    try:
        for data in INITIAL_SOURCES:
            exists = session.query(Source).filter_by(name=data["name"]).first()
            if exists:
                continue
            session.add(Source(**data))
            created += 1
        session.commit()
    finally:
        session.close()
    return created


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} new source(s)")

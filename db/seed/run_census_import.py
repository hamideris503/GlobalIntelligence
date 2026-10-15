"""Import census seed into sources registry (Step: census).

- upsert بر اساس name: موجودها فقط فیلدهای تهی census را می‌گیرند (داده‌ی کاربر بازنویسی نمی‌شود).
- همه‌ی جدیدها PENDING_VALIDATION و غیرفعال (معیار پذیرش ۳).

اجرا:
    python -m db.seed.run_census_import [--limit 50]
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse

from sqlalchemy import select

from backend.database.models.source import Source
from backend.database.session import get_session_factory
from db.seed.sources_census import ENTRIES

FILL_FIELDS = (
    "homepage_url", "canonical_url", "geography", "category", "subcategory",
    "type", "primary_or_secondary", "official_status", "priority", "access_model",
    "validation_status",
)


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return (urlparse(url).hostname or "").lower() or None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import census sources")
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()

    session = get_session_factory()()
    created = updated = 0
    try:
        for entry in ENTRIES[: args.limit]:
            existing = session.execute(
                select(Source).where(Source.name == entry["name"])
            ).scalar_one_or_none()
            if existing is None:
                session.add(Source(
                    name=entry["name"],
                    domain=_domain(entry.get("homepage_url")),
                    country=entry.get("country"),
                    type=entry.get("type", "other"),
                    language=entry.get("language"),
                    homepage_url=entry.get("homepage_url"),
                    geography=entry.get("geography"),
                    category=entry.get("category"),
                    subcategory=entry.get("subcategory"),
                    primary_or_secondary=entry.get("primary_or_secondary"),
                    official_status=entry.get("official_status"),
                    priority=entry.get("priority"),
                    access_model=entry.get("access_model"),
                    api_url=entry.get("api_url"),
                    api_documentation_url=entry.get("api_documentation_url"),
                    validation_status="PENDING_VALIDATION",
                    active=False,
                ))
                created += 1
            else:
                changed = False
                for field in FILL_FIELDS:
                    if getattr(existing, field, None) in (None, "") and entry.get(field):
                        setattr(existing, field, entry[field])
                        changed = True
                if not existing.domain and entry.get("homepage_url"):
                    existing.domain = _domain(entry["homepage_url"])
                    changed = True
                if changed:
                    updated += 1
            if (created + updated) % 50 == 0:
                session.flush()
        session.commit()
    finally:
        session.close()
    print(json.dumps({"created": created, "updated": updated,
                      "total_seed": len(ENTRIES)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

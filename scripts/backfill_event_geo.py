"""Backfill deterministic event type + location for existing events.

Usage:
    python scripts/backfill_event_geo.py            # dry-run (default)
    python scripts/backfill_event_geo.py --apply    # write changes

Idempotent: only empty fields are filled; existing values are never overwritten.
No AI, no network.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database.models.event import Event
from backend.database.session import get_engine
from domains.events.type_rules import classify_event_type
from domains.geo.gazetteer import geocode_text


def _event_text(event: Event) -> str:
    parts = [event.action or "", event.location or ""]
    for a in getattr(event, "articles", []) or []:
        parts.append(a.title or "")
        parts.append(a.summary or "")
    return " \n ".join(p for p in parts if p)


def _merge_meta(existing: str | None, updates: dict[str, Any]) -> str:
    try:
        meta = json.loads(existing) if existing else {}
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta.update(updates)
    return json.dumps(meta, ensure_ascii=False)


def run_session(session: Session, *, apply: bool, limit: int | None) -> dict[str, Any]:
    counts: dict[str, Any] = {
        "total": 0, "type_assigned": 0, "type_unknown": 0,
        "geo_city": 0, "geo_country": 0, "geo_unresolved": 0,
        "type_reasons": {}, "geo_reasons": {},
    }
    type_reasons: Counter[str] = Counter()
    geo_reasons: Counter[str] = Counter()

    stmt = select(Event).options(selectinload(Event.articles)).order_by(Event.created_at)
    if limit:
        stmt = stmt.limit(limit)
    rows = session.execute(stmt).scalars().all()
    counts["total"] = len(rows)

    for ev in rows:
        text = _event_text(ev)
        updates: dict[str, Any] = {}
        if not ev.event_type or ev.event_type.strip().lower() == "unknown":
            etype, reason, score, matched = classify_event_type(text)
            key = reason.split(" ")[0] if " " in reason else reason
            type_reasons[key] += 1
            if etype != "unknown":
                if apply:
                    ev.event_type = etype
                counts["type_assigned"] += 1
                updates["type_reason"] = reason
                updates["type_score"] = score
                updates["type_keywords"] = matched
            else:
                counts["type_unknown"] += 1
                updates["type_reason"] = reason
                updates["type_score"] = score
        if ev.latitude is None and ev.longitude is None:
            geo = geocode_text(text)
            geo_reasons[geo["location_reason"]] += 1
            if geo["location_status"].startswith("resolved"):
                if apply:
                    ev.location = geo["location"] or ev.location
                    ev.latitude = geo["latitude"]
                    ev.longitude = geo["longitude"]
                    ev.country = geo["country"]
                    ev.location_precision = geo["location_precision"]
                    ev.location_source = geo["location_source"]
                    ev.location_confidence = geo["location_confidence"]
                if geo["location_precision"] == "city":
                    counts["geo_city"] += 1
                else:
                    counts["geo_country"] += 1
                updates["location_reason"] = geo["location_reason"]
            else:
                counts["geo_unresolved"] += 1
                updates["location_reason"] = geo["location_reason"]
        if updates:
            if apply:
                ev.event_metadata = _merge_meta(ev.event_metadata, updates)

    if apply:
        session.commit()
    else:
        session.rollback()

    counts["type_reasons"] = dict(type_reasons)
    counts["geo_reasons"] = dict(geo_reasons)
    print("=== backfill report ===")
    print(f"total events: {counts['total']}")
    print(f"type assigned: {counts['type_assigned']}")
    print(f"type unknown (remaining): {counts['type_unknown']}")
    print(f"geo city: {counts['geo_city']}")
    print(f"geo country: {counts['geo_country']}")
    print(f"geo unresolved: {counts['geo_unresolved']}")
    print(f"mode: {'APPLY' if apply else 'DRY-RUN'}")
    return counts


def run(*, apply: bool, limit: int | None) -> None:
    engine = get_engine()
    session = Session(bind=engine)
    try:
        run_session(session, apply=apply, limit=limit)
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes (default dry-run)")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(apply=args.apply, limit=args.limit)


if __name__ == "__main__":
    main()

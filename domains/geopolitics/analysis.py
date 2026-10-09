"""Geopolitical Engine — تحلیل تنش بازیگران (Phase 22).

مسیر: events (actors + type + surprise) + entity_relationships (sanctions/competes)
      → tension قطعی به تفکیک بازیگر → upsert در `geopolitical_assessments`.

- idempotent بر اساس UniqueConstraint (actor, period)؛ period ماه جاری میلادی.
- تطبیق نام بازیگر با موجودیت‌ها case-insensitive و نرمال‌شده است.
- بدون AI.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.entity import Entity, EntityRelationship
from backend.database.models.event import Event
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from domains.geopolitics.analytics import tension
from domains.worldstate.signals import CONFLICT_TYPES

logger = get_logger(__name__)

TENSION_RELATIONS = frozenset({"sanctions", "competes_with"})


@dataclass
class GeoOutcome:
    actors_analyzed: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "actors_analyzed": self.actors_analyzed,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def normalize_actor(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


def _parse_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []


class GeopoliticalEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _sanction_counts(self) -> Counter:
        """تعداد یال‌های تنش برای هر موجودیت (نام نرمال‌شده)."""
        counts: Counter = Counter()
        entities = {
            e.id: e for e in self.db.execute(select(Entity)).scalars().all()
        }
        stmt = select(EntityRelationship).where(
            EntityRelationship.relation.in_(TENSION_RELATIONS)
        )
        for rel in self.db.execute(stmt).scalars().all():
            seen: set[str] = set()
            for eid in (rel.from_entity_id, rel.to_entity_id):
                ent = entities.get(eid)
                if ent is None:
                    continue
                for raw in filter(None, [ent.canonical_name, ent.display_name]):
                    seen.add(normalize_actor(str(raw)))
            for name in seen:
                counts[name] += 1
        return counts

    def analyze_all(self, *, period: str | None = None) -> GeoOutcome:
        outcome = GeoOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")
        sanction_counts = self._sanction_counts()

        # گروه‌بندی رویدادها بر اساس بازیگر
        by_actor: dict[str, dict] = {}
        events = list(self.db.execute(select(Event)).scalars().all())
        for e in events:
            for raw in _parse_list(e.actors):
                if not isinstance(raw, str) or not raw.strip():
                    continue
                key = normalize_actor(raw)
                bucket = by_actor.setdefault(
                    key, {"display": raw.strip(), "events": []}
                )
                bucket["events"].append(e)

        if not by_actor:
            outcome.skipped += 1
            return outcome

        for key, bucket in sorted(by_actor.items()):
            try:
                evts = bucket["events"]
                surprises = [e.surprise for e in evts if e.surprise is not None]
                avg_surprise = (
                    sum(surprises) / len(surprises) if surprises else None
                )
                n_conflict = sum(
                    1 for e in evts if (e.event_type or "") in CONFLICT_TYPES
                )
                stats = tension(
                    n_events=len(evts),
                    avg_surprise=avg_surprise,
                    conflict_share=n_conflict / len(evts),
                    sanction_links=sanction_counts.get(key, 0),
                )
                if stats is None:
                    outcome.skipped += 1
                    continue
                outcome.actors_analyzed += 1
                type_counts = Counter(
                    (e.event_type or "unknown") for e in evts
                )
                top_types = json.dumps(
                    dict(type_counts.most_common(5)), ensure_ascii=False
                )
                existing = self.db.execute(
                    select(GeopoliticalAssessment).where(
                        GeopoliticalAssessment.actor == bucket["display"],
                        GeopoliticalAssessment.period == period,
                    )
                ).scalar_one_or_none()
                payload = {
                    "tension": stats.tension,
                    "conflict_share": stats.conflict_share,
                    "event_count": stats.event_count,
                    "sanction_links": stats.sanction_links,
                    "top_types": top_types,
                    "method": stats.method,
                    "confidence": stats.confidence,
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        GeopoliticalAssessment(
                            actor=bucket["display"], period=period, **payload
                        )
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("geopolitics analyze failed | actor=%s err=%s", key, exc)
        self.db.commit()
        logger.info("geopolitics analyze done | %s", outcome.as_dict())
        return outcome

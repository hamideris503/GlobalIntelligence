"""Narrative Engine — استخراج روایت‌های غالب از رویدادها (Phase 24).

مسیر: events + مقالات (entities/topics/stance/source) → Union-Find بر پیوند
      موجودیت/موضوع → خوشه = روایت → upsert ماهانه در `narratives`.

- idempotent بر اساس UniqueConstraint (period, signature)؛ signature هش
  شناسه‌های مرتب اعضای خوشه است.
- بدون AI؛ برچسب‌گذاری از عبارت‌های پربسامد.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.logging import get_logger
from backend.database.models.event import Event
from backend.database.models.narrative import Narrative
from domains.narratives.analytics import (
    UnionFind,
    build_title,
    confidence_for,
    linked,
    stance_split,
    strength,
)

logger = get_logger(__name__)


@dataclass
class NarrativeOutcome:
    narratives_built: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "narratives_built": self.narratives_built,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def _parse_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []


def _norm(text: str) -> str:
    return " ".join(text.strip().split()).casefold()


def _event_features(event: Event) -> tuple[frozenset[str], frozenset[str]]:
    """(موجودیت‌های canonical، موضوعات) یک رویداد از مقالاتش."""
    entities: set[str] = set()
    topics: set[str] = set()
    for a in event.articles:
        for e in _parse_list(a.entities):
            if isinstance(e, dict) and e.get("name"):
                entities.add(_norm(str(e["name"])))
        for t in _parse_list(a.topics):
            if isinstance(t, str) and t.strip():
                topics.add(_norm(t))
    for actor in _parse_list(event.actors):
        if isinstance(actor, str) and actor.strip():
            entities.add(_norm(actor))
    return frozenset(entities), frozenset(topics)


class NarrativeEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_all(self, *, period: str | None = None) -> NarrativeOutcome:
        outcome = NarrativeOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")

        events = list(
            self.db.execute(
                select(Event).options(selectinload(Event.articles))
            )
            .scalars()
            .all()
        )
        if not events:
            outcome.skipped += 1
            return outcome

        feats = [_event_features(e) for e in events]
        uf = UnionFind()
        for i in range(len(events)):
            uf.find(i)
            for j in range(i + 1, len(events)):
                if linked(feats[i][0], feats[j][0], feats[i][1], feats[j][1]):
                    uf.union(i, j)

        for members in uf.groups():
            try:
                cluster = [events[i] for i in members]
                ids = sorted(str(e.id) for e in cluster)
                signature = hashlib.sha256("|".join(ids).encode()).hexdigest()[:16]

                terms: Counter = Counter()
                types: Counter = Counter()
                stances: list[str] = []
                sources: set[str] = set()
                stamps: list[datetime] = []
                n_articles = 0
                for e in cluster:
                    if e.event_type:
                        types[e.event_type] += 1
                    for a in e.articles:
                        n_articles += 1
                        for t in _parse_list(a.topics):
                            if isinstance(t, str) and t.strip():
                                terms[_norm(t)] += 1
                        for en in _parse_list(a.entities):
                            if isinstance(en, dict) and en.get("name"):
                                terms[_norm(str(en["name"]))] += 1
                        if a.stance:
                            stances.append(a.stance)
                        if a.source_name:
                            sources.add(a.source_name)
                    for ts in (e.occurred_at, e.created_at):
                        if ts is not None:
                            stamps.append(ts)

                dominant, divergence = stance_split(stances)
                title = build_title(terms, types, len(cluster))
                outcome.narratives_built += 1

                existing = self.db.execute(
                    select(Narrative).where(
                        Narrative.period == period,
                        Narrative.signature == signature,
                    )
                ).scalar_one_or_none()
                payload = {
                    "title": title,
                    "summary": (
                        f"{len(cluster)} events, {n_articles} articles, "
                        f"{len(sources)} sources"
                    ),
                    "event_ids": json.dumps(ids),
                    "event_count": len(cluster),
                    "article_count": n_articles,
                    "source_count": len(sources),
                    "first_seen": min(stamps) if stamps else None,
                    "last_seen": max(stamps) if stamps else None,
                    "dominant_stance": dominant,
                    "stance_divergence": divergence,
                    "strength": strength(len(cluster), len(sources)),
                    "method": "narrative_v1",
                    "confidence": confidence_for(len(cluster)),
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        Narrative(period=period, signature=signature, **payload)
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("narrative build failed | err=%s", exc)
        self.db.commit()
        logger.info("narrative build done | %s", outcome.as_dict())
        return outcome

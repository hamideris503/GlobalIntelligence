"""Iran Mode — بسته‌ی اطلاعاتی ایران (Phase 33).

تجمیع فقط‌خواندنی از خروجی‌های موجود:
- رویدادهای مرتبط (بازیگر/موضوع/کشور مقاله) + ادعاهای آن‌ها
- مشاهدات macro با کشور IRN
- تصمیم‌های اهداف مرتبط (IRN/Iran در target)
- خلاصه‌ی آخرین WorldState به‌عنوان بستر

بدون migration، بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.logging import get_logger
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from backend.database.models.market import MacroObservation
from backend.database.models.recommendation import Recommendation
from backend.database.models.world_state import WorldState
from domains.iran.matching import (
    is_iran_country,
    is_iran_name,
    is_iran_target,
    parse_str_list,
)

logger = get_logger(__name__)


@dataclass
class IranBrief:
    events: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    macro: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    world_state: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "events": self.events,
            "claims": self.claims,
            "macro": self.macro,
            "decisions": self.decisions,
            "world_state": self.world_state,
            "counts": {
                "events": len(self.events),
                "claims": len(self.claims),
                "macro": len(self.macro),
                "decisions": len(self.decisions),
            },
        }


def _event_matches(event: Event) -> bool:
    for actor in parse_str_list(event.actors):
        if is_iran_name(actor):
            return True
    for article in event.articles[:10]:
        if is_iran_country(article.country):
            return True
        for topic in parse_str_list(article.topics):
            if is_iran_name(topic):
                return True
    return False


class IranModeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def iran_events(self, *, limit: int = 100) -> list[Event]:
        stmt = (
            select(Event)
            .options(selectinload(Event.articles))
            .order_by(Event.created_at.desc())
            .limit(limit * 5)
        )
        matched = [e for e in self.db.execute(stmt).scalars().all() if _event_matches(e)]
        return matched[:limit]

    def brief(self, *, limit: int = 100) -> IranBrief:
        events = self.iran_events(limit=limit)
        event_ids = {e.id for e in events}

        claims: list[dict] = []
        if event_ids:
            stmt = (
                select(Claim)
                .where(Claim.event_id.in_(event_ids))
                .order_by(Claim.created_at.desc())
                .limit(limit)
            )
            for c in self.db.execute(stmt).scalars().all():
                claims.append(
                    {
                        "id": str(c.id),
                        "subject": c.subject,
                        "predicate": c.predicate,
                        "object": c.object,
                        "verification_status": c.verification_status,
                    }
                )

        macro: list[dict] = []
        stmt = (
            select(MacroObservation)
            .where(MacroObservation.country == "IRN")
            .order_by(MacroObservation.indicator, MacroObservation.period.desc())
            .limit(limit)
        )
        for m in self.db.execute(stmt).scalars().all():
            macro.append(
                {
                    "indicator": m.indicator,
                    "period": m.period,
                    "value": m.value,
                    "unit": m.unit,
                }
            )

        decisions: list[dict] = []
        stmt = (
            select(Recommendation)
            .order_by(Recommendation.created_at.desc())
            .limit(limit * 2)
        )
        for r in self.db.execute(stmt).scalars().all():
            if is_iran_target(r.asset):
                decisions.append(
                    {
                        "id": str(r.id),
                        "asset": r.asset,
                        "decision": r.decision,
                        "score": r.score,
                        "rank": r.rank,
                    }
                )
                if len(decisions) >= limit:
                    break

        ws: dict = {}
        latest = self.db.execute(
            select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
        ).scalars().first()
        if latest is not None:
            ws = {
                "captured_at": latest.captured_at.isoformat() if latest.captured_at else None,
                "macro_regime": latest.macro_regime,
                "market_regime": latest.market_regime,
                "confidence": latest.confidence,
            }

        brief = IranBrief(
            events=[
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "action": (e.action or "")[:300],
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                }
                for e in events
            ],
            claims=claims,
            macro=macro,
            decisions=decisions,
            world_state=ws,
        )
        logger.info(
            "iran brief | events=%d claims=%d macro=%d decisions=%d",
            len(brief.events), len(brief.claims), len(brief.macro), len(brief.decisions),
        )
        return brief

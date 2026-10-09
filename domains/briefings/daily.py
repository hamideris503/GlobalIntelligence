"""Daily briefing builder — خلاصه‌ی ۲۴ ساعته‌ی قطعی (Phase 41).

بخش‌ها (v1, مستند):
- events: رویدادهای ساخته‌شده در پنجره (نوع + اقدام کوتاه).
- claims: ادعاهای جدید پنجره + وضعیت راستی‌آزمایی.
- movers: ۳ نماد با بیشترین |تغییر٪| بین دو مشاهده‌ی آخر (نیازمند ≥۲ نقطه).
- world_state: آخرین snapshot (رژیم‌ها + اعتماد).
- decisions: تصمیم‌های جدید پنجره.
- risks: ۳ ریسک برتر جاری.
- self_eval: آخرین نمره/grade (اگر هست).

پنجره‌ی پیش‌فرض ۲۴ ساعت اخیر؛ خروجی deterministic و بدون AI.
گزارش تفسیر متنی LLM در آینده (Report role) — نه این فاز.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.briefing import Briefing
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from backend.database.models.market import MarketObservation
from backend.database.models.recommendation import Recommendation
from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.self_evaluation import SelfEvaluation
from backend.database.models.world_state import WorldState

logger = get_logger(__name__)


@dataclass
class DailyOutcome:
    briefing_id: str = ""
    period: str = ""
    stored: int = 0
    duplicates: int = 0
    sections: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "briefing_id": self.briefing_id,
            "period": self.period,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "sections": self.sections,
        }


def _pct_change(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return round((new - old) / abs(old) * 100.0, 2)


def _aware(dt: datetime | None) -> datetime | None:
    """بک‌اندهای naive (SQLite) → UTC فرضی؛ مقایسه‌ی امن زمانی."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class DailyBriefingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _movers(self, *, limit: int = 3) -> list[dict]:
        """۳ حرکت بزرگ بازار از دو مشاهده‌ی آخر هر نماد."""
        stmt = select(MarketObservation.symbol).group_by(MarketObservation.symbol)
        symbols = [s for s in self.db.execute(stmt).scalars().all() if s]
        moves: list[dict] = []
        for symbol in symbols:
            rows = list(
                self.db.execute(
                    select(MarketObservation)
                    .where(
                        MarketObservation.symbol == symbol,
                        MarketObservation.value.is_not(None),
                        MarketObservation.observed_at.is_not(None),
                    )
                    .order_by(MarketObservation.observed_at.desc())
                    .limit(2)
                )
                .scalars()
                .all()
            )
            if len(rows) < 2:
                continue
            pct = _pct_change(rows[0].value, rows[1].value)
            if pct is None:
                continue
            moves.append(
                {
                    "symbol": symbol,
                    "change_pct": pct,
                    "latest": rows[0].value,
                    "observed_at": rows[0].observed_at.isoformat()
                    if rows[0].observed_at
                    else None,
                }
            )
        moves.sort(key=lambda m: abs(m["change_pct"]), reverse=True)
        return moves[:limit]

    def build(self, *, day: str | None = None, window_hours: int = 24) -> DailyOutcome:
        outcome = DailyOutcome()
        now = datetime.now(UTC)
        period = day or now.strftime("%Y-%m-%d")
        outcome.period = period
        cutoff = now - timedelta(hours=window_hours)

        # فیلتر زمانی دقیق در پایتون (مقایسه‌ی naive/aware در DB ناپایدار است)
        events: list[dict] = []
        for e in self.db.execute(
            select(Event).order_by(Event.created_at.desc()).limit(200)
        ).scalars().all():
            if (c := _aware(e.created_at)) is None or c < cutoff:
                continue
            events.append(
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "action": (e.action or "")[:200],
                }
            )
            if len(events) >= 50:
                break

        claims: list[dict] = []
        for c in self.db.execute(
            select(Claim).order_by(Claim.created_at.desc()).limit(200)
        ).scalars().all():
            if (cc := _aware(c.created_at)) is None or cc < cutoff:
                continue
            claims.append(
                {
                    "id": str(c.id),
                    "subject": c.subject,
                    "predicate": c.predicate,
                    "verification_status": c.verification_status,
                }
            )
            if len(claims) >= 50:
                break

        movers = self._movers()

        ws: dict = {}
        latest_state = self.db.execute(
            select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
        ).scalars().first()
        if latest_state is not None:
            ws = {
                "macro_regime": latest_state.macro_regime,
                "market_regime": latest_state.market_regime,
                "confidence": latest_state.confidence,
            }

        decisions: list[dict] = []
        for r in self.db.execute(
            select(Recommendation).order_by(Recommendation.created_at.desc()).limit(100)
        ).scalars().all():
            if (c := _aware(r.created_at)) is None or c < cutoff:
                continue
            decisions.append(
                {"asset": r.asset, "decision": r.decision, "score": r.score}
            )
            if len(decisions) >= 20:
                break

        risks: list[dict] = []
        for r in self.db.execute(
            select(RiskAssessment)
            .order_by(RiskAssessment.score.desc().nullslast())
            .limit(3)
        ).scalars().all():
            risks.append(
                {"category": r.category, "score": r.score, "level": r.level}
            )

        self_eval: dict = {}
        latest_eval = self.db.execute(
            select(SelfEvaluation).order_by(SelfEvaluation.created_at.desc()).limit(1)
        ).scalars().first()
        if latest_eval is not None:
            self_eval = {"score": latest_eval.score, "grade": latest_eval.grade}

        sections = {
            "events": events,
            "claims": claims,
            "movers": movers,
            "world_state": ws,
            "decisions": decisions,
            "risks": risks,
            "self_eval": self_eval,
        }
        outcome.sections = {k: (len(v) if isinstance(v, list) else v) for k, v in sections.items()}

        title = f"Daily intelligence {period}: {len(events)} events, {len(movers)} movers"
        existing = self.db.execute(
            select(Briefing).where(
                Briefing.kind == "daily", Briefing.period == period
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.title = title
            existing.content = json.dumps(sections, ensure_ascii=False)
            outcome.duplicates += 1
            outcome.briefing_id = str(existing.id)
        else:
            record = Briefing(
                kind="daily",
                period=period,
                title=title,
                content=json.dumps(sections, ensure_ascii=False),
                method="daily_v1",
                observed_at=now,
            )
            self.db.add(record)
            self.db.flush()
            outcome.stored += 1
            outcome.briefing_id = str(record.id)
        self.db.commit()
        logger.info("daily briefing done | period=%s %s", period, outcome.as_dict())
        return outcome

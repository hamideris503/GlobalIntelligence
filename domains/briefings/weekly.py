"""Weekly briefing builder — خلاصه‌ی ۷ روزه با مقایسه‌ها (Phase 42).

بخش‌های اضافه نسبت به روزانه (v1, مستند):
- trend: شمار رویداد/ادعا به تفکیک روز هفته.
- movers: تغییر٪ اولین→آخرین مشاهده‌ی هر نماد در پنجره (نیازمند ≥۲ نقطه).
- regime_shift: رژیم اول/آخر snapshotهای پنجره (تغییر یا ثبات).
- risk_deltas: امتیاز جاری هر دسته منهای دوره‌ی قبل (تهی اگر سابقه نیست).
- narratives: روایت‌های ساخته‌شده در پنجره.

idempotent بر هفته‌ی ISO (YYYY-Www). بدون AI.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.briefing import Briefing
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from backend.database.models.market import MarketObservation
from backend.database.models.narrative import Narrative
from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.world_state import WorldState

logger = get_logger(__name__)


@dataclass
class WeeklyOutcome:
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


class WeeklyBriefingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, *, ref: datetime | None = None) -> WeeklyOutcome:
        outcome = WeeklyOutcome()
        now = ref or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        iso_year, iso_week, _ = now.isocalendar()
        period = f"{iso_year}-W{iso_week:02d}"
        outcome.period = period
        start = now - timedelta(days=7)

        # روند روزانه (فیلتر دقیق در پایتون؛ مقایسه‌ی naive/aware در DB ناپایدار است)
        recent_events = list(
            self.db.execute(
                select(Event).order_by(Event.created_at.desc()).limit(500)
            )
            .scalars()
            .all()
        )
        recent_claims = list(
            self.db.execute(
                select(Claim).order_by(Claim.created_at.desc()).limit(500)
            )
            .scalars()
            .all()
        )
        trend: list[dict] = []
        for i in range(7):
            # ۷ روز اخیر منتهی به امروز (شامل امروز)
            day = (now - timedelta(days=6 - i)).date().isoformat()
            day_start = datetime.fromisoformat(day).replace(tzinfo=UTC)
            day_end = day_start + timedelta(days=1)
            n_events = sum(
                1
                for e in recent_events
                if (c := _aware(e.created_at)) is not None
                and day_start <= c < day_end
            )
            n_claims = sum(
                1
                for c in recent_claims
                if (cc := _aware(c.created_at)) is not None
                and day_start <= cc < day_end
            )
            trend.append({"day": day, "events": n_events, "claims": n_claims})

        # حرکت‌های هفته
        movers: list[dict] = []
        symbols = [
            s
            for s in self.db.execute(
                select(MarketObservation.symbol).group_by(MarketObservation.symbol)
            ).scalars().all()
            if s
        ]
        for symbol in symbols:
            rows = [
                r
                for r in self.db.execute(
                    select(MarketObservation)
                    .where(
                        MarketObservation.symbol == symbol,
                        MarketObservation.value.is_not(None),
                        MarketObservation.observed_at.is_not(None),
                    )
                    .order_by(MarketObservation.observed_at.desc())
                    .limit(50)
                )
                .scalars()
                .all()
                if (o := _aware(r.observed_at)) is not None and o >= start
            ]
            rows.sort(
                key=lambda r: _aware(r.observed_at) or datetime.min.replace(tzinfo=UTC)
            )
            if len(rows) < 2:
                continue
            pct = _pct_change(rows[-1].value, rows[0].value)
            if pct is None:
                continue
            movers.append({"symbol": symbol, "change_pct": pct, "latest": rows[-1].value})
        movers.sort(key=lambda m: abs(m["change_pct"]), reverse=True)
        movers = movers[:5]

        # تغییر رژیم در هفته
        snaps = [
            s
            for s in self.db.execute(
                select(WorldState).order_by(WorldState.captured_at.asc()).limit(100)
            )
            .scalars()
            .all()
            if (c := _aware(s.captured_at)) is not None and c >= start
        ]
        regime_shift = {}
        if snaps:
            regime_shift = {
                "from": {
                    "macro": snaps[0].macro_regime,
                    "market": snaps[0].market_regime,
                },
                "to": {
                    "macro": snaps[-1].macro_regime,
                    "market": snaps[-1].market_regime,
                },
                "n_snapshots": len(snaps),
            }

        # دلتای ریسک نسبت به دوره‌ی قبل
        risk_deltas: list[dict] = []
        cats = [
            r
            for r in self.db.execute(
                select(RiskAssessment.category).group_by(RiskAssessment.category)
            ).scalars().all()
            if r
        ]
        for cat in cats:
            rows = list(
                self.db.execute(
                    select(RiskAssessment)
                    .where(RiskAssessment.category == cat)
                    .order_by(RiskAssessment.period.desc())
                    .limit(2)
                )
                .scalars()
                .all()
            )
            if not rows or rows[0].score is None:
                continue
            prev = rows[1].score if len(rows) > 1 and rows[1].score is not None else None
            risk_deltas.append(
                {
                    "category": cat,
                    "score": rows[0].score,
                    "delta": round(rows[0].score - prev, 4) if prev is not None else None,
                }
            )

        # روایت‌های هفته
        narratives: list[dict] = []
        for n in self.db.execute(
            select(Narrative)
            .order_by(Narrative.strength.desc().nullslast())
            .limit(50)
        ).scalars().all():
            if (c := _aware(n.created_at)) is None or c < start:
                continue
            narratives.append(
                {"title": n.title, "strength": n.strength, "event_count": n.event_count}
            )
            if len(narratives) >= 10:
                break

        type_mix = Counter(
            e.event_type
            for e in recent_events
            if (c := _aware(e.created_at)) is not None
            and c >= start
            and e.event_type
        )

        sections = {
            "trend": trend,
            "movers": movers,
            "regime_shift": regime_shift,
            "risk_deltas": risk_deltas,
            "narratives": narratives,
            "event_types": dict(type_mix.most_common(10)),
        }
        outcome.sections = {
            "trend_days": len(trend),
            "movers": len(movers),
            "risk_deltas": len(risk_deltas),
            "narratives": len(narratives),
        }

        title = (
            f"Weekly intelligence {period}: "
            f"{sum(d['events'] for d in trend)} events, {len(movers)} movers"
        )
        existing = self.db.execute(
            select(Briefing).where(
                Briefing.kind == "weekly", Briefing.period == period
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.title = title
            existing.content = json.dumps(sections, ensure_ascii=False)
            outcome.duplicates += 1
            outcome.briefing_id = str(existing.id)
        else:
            record = Briefing(
                kind="weekly",
                period=period,
                title=title,
                content=json.dumps(sections, ensure_ascii=False),
                method="weekly_v1",
                observed_at=now,
            )
            self.db.add(record)
            self.db.flush()
            outcome.stored += 1
            outcome.briefing_id = str(record.id)
        self.db.commit()
        logger.info("weekly briefing done | period=%s", period)
        return outcome

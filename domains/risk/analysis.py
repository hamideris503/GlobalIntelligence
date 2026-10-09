"""Risk Engine — ترکیب ریسک‌ها به assessment دسته‌بندی‌شده (Phase 31).

مسیر: آخرین WorldState (سیگنال‌های معتبر) + تنش بازیگران +
      گستردگی سناریوها → ۸ دسته ریسک → upsert ماهانه.

- سیگنال no_data نادیده گرفته می‌شود (نه 0.5)؛ دسته‌ی بدون ورودی skip.
- idempotent بر اساس UniqueConstraint (category, period).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.world_state import WorldState
from domains.risk.analytics import (
    RiskScore,
    combine,
    growth_risk,
    spread_uncertainty,
)

logger = get_logger(__name__)

SIGNAL_CATEGORIES = {
    "inflation_risk": ["inflation_pressure"],
    "market_risk": ["financial_stress"],
    "energy_risk": ["energy_risk"],
    "trade_risk": ["trade_risk"],
    "social_risk": ["social_pressure"],
}


@dataclass
class RiskOutcome:
    categories_analyzed: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "categories_analyzed": self.categories_analyzed,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def _signal_meta(snapshot: WorldState) -> dict:
    try:
        meta = json.loads(snapshot.value_metadata or "{}")
    except Exception:  # noqa: BLE001
        return {}
    return meta if isinstance(meta, dict) else {}


def _valid_signal(meta: dict, name: str) -> tuple[float, float] | None:
    """(value, confidence) سیگنال معتبر؛ no_data/ناموجود → None."""
    entry = meta.get(name)
    if not isinstance(entry, dict) or entry.get("method") == "no_data":
        return None
    try:
        value = float(entry["value"])
        conf = float(entry.get("confidence", 0.5))
    except (TypeError, ValueError, KeyError):
        return None
    return value, conf


class RiskEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _latest_snapshot(self) -> WorldState | None:
        stmt = select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
        return self.db.execute(stmt).scalars().first()

    def _max_tension(self) -> tuple[float, float] | None:
        """(بیشینه تنش، اعتماد) آخرین دوره‌ی ارزیابی‌شده."""
        stmt = select(GeopoliticalAssessment.period).order_by(
            GeopoliticalAssessment.period.desc()
        ).limit(1)
        period = self.db.execute(stmt).scalars().first()
        if period is None:
            return None
        rows = list(
            self.db.execute(
                select(GeopoliticalAssessment).where(
                    GeopoliticalAssessment.period == period,
                    GeopoliticalAssessment.tension.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return None
        best = max(rows, key=lambda r: r.tension or 0.0)
        return float(best.tension or 0.0), float(best.confidence or 0.5)

    def _scenario_spreads(self) -> list[float]:
        """گستردگی (bull−bear)/|base| برای هر هدف دارای مجموعه‌ی کامل."""
        stmt = (
            select(Forecast)
            .where(Forecast.scenario.is_not(None), Forecast.status == "active")
            .order_by(Forecast.target, Forecast.scenario, Forecast.created_at.desc())
        )
        by_target: dict[str, dict[str, float]] = {}
        for fc in self.db.execute(stmt).scalars().all():
            if fc.target is None or fc.expected_value is None:
                continue
            bucket = by_target.setdefault(fc.target, {})
            if fc.scenario in ("base", "bull", "bear") and fc.scenario not in bucket:
                bucket[fc.scenario] = fc.expected_value
        spreads = []
        for bucket in by_target.values():
            if {"base", "bull", "bear"} <= set(bucket) and bucket["base"]:
                spreads.append(
                    abs(bucket["bull"] - bucket["bear"]) / abs(bucket["base"])
                )
        return spreads

    def analyze_all(self, *, period: str | None = None) -> RiskOutcome:
        outcome = RiskOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")

        snapshot = self._latest_snapshot()
        if snapshot is None:
            outcome.skipped += 1
            return outcome
        meta = _signal_meta(snapshot)

        categories: dict[str, RiskScore | None] = {}
        for category, signals in SIGNAL_CATEGORIES.items():
            parts = []
            for name in signals:
                valid = _valid_signal(meta, name)
                if valid is not None:
                    parts.append((valid[0], valid[1], f"worldstate:{name}"))
            categories[category] = combine(parts)

        growth = _valid_signal(meta, "growth_pressure")
        categories["growth_risk"] = (
            growth_risk(growth[0], growth[1]) if growth else None
        )

        geo_parts = []
        world_geo = _valid_signal(meta, "geopolitical_risk")
        if world_geo is not None:
            geo_parts.append((world_geo[0], world_geo[1], "worldstate:geopolitical"))
        max_tension = self._max_tension()
        if max_tension is not None:
            geo_parts.append((max_tension[0], max_tension[1], "actor_tension_max"))
        categories["geopolitical_risk"] = combine(geo_parts, mode="max")

        categories["uncertainty"] = spread_uncertainty(self._scenario_spreads())

        for category, score in sorted(categories.items()):
            try:
                if score is None:
                    outcome.skipped += 1
                    continue
                outcome.categories_analyzed += 1
                existing = self.db.execute(
                    select(RiskAssessment).where(
                        RiskAssessment.category == category,
                        RiskAssessment.period == period,
                    )
                ).scalar_one_or_none()
                payload = {
                    "score": score.score,
                    "level": score.level,
                    "drivers": json.dumps(score.drivers, ensure_ascii=False),
                    "method": score.method,
                    "confidence": score.confidence,
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        RiskAssessment(
                            category=category, period=period, **payload
                        )
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("risk analyze failed | %s err=%s", category, exc)
        self.db.commit()
        logger.info("risk analyze done | %s", outcome.as_dict())
        return outcome

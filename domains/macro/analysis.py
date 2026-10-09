"""Macro Engine — تحلیل سری‌های اقتصاد کلان (Phase 21).

مسیر: macro_observations (به تفکیک indicator×country، مرتب دوره)
      → analytics قطعی → upsert در `macro_assessments`.

- idempotent بر اساس UniqueConstraint (indicator, country, period).
- بدون AI؛ تفسیر متنی با LLM در فازهای بعد.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.macro_assessment import MacroAssessment
from backend.database.models.market import MacroObservation
from domains.macro.analytics import analyze_series

logger = get_logger(__name__)


@dataclass
class MacroOutcome:
    series_analyzed: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "series_analyzed": self.series_analyzed,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


class MacroEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _series_keys(self) -> list[tuple[str | None, str | None]]:
        stmt = (
            select(MacroObservation.indicator, MacroObservation.country)
            .group_by(MacroObservation.indicator, MacroObservation.country)
            .order_by(MacroObservation.indicator, MacroObservation.country)
        )
        return [(r[0], r[1]) for r in self.db.execute(stmt).all()]

    def _series_values(
        self, indicator: str | None, country: str | None, limit: int = 60
    ) -> tuple[list[float | None], str | None]:
        stmt = (
            select(MacroObservation)
            .where(
                MacroObservation.indicator == indicator,
                MacroObservation.country == country,
            )
            .order_by(MacroObservation.period.desc())
            .limit(limit)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        if not rows:
            return [], None
        return [r.value for r in rows], rows[0].period

    def analyze_all(
        self,
        *,
        indicator: str | None = None,
        country: str | None = None,
    ) -> MacroOutcome:
        outcome = MacroOutcome()
        keys = self._series_keys()
        if indicator:
            keys = [k for k in keys if k[0] == indicator]
        if country:
            keys = [k for k in keys if k[1] == country]
        for ind, cty in keys:
            try:
                values, period = self._series_values(ind, cty)
                if not values or period is None:
                    outcome.skipped += 1
                    continue
                stats = analyze_series(values)
                outcome.series_analyzed += 1
                existing = self.db.execute(
                    select(MacroAssessment).where(
                        MacroAssessment.indicator == ind,
                        MacroAssessment.country == cty,
                        MacroAssessment.period == period,
                    )
                ).scalar_one_or_none()
                payload = {
                    "latest_value": stats.latest,
                    "yoy_change": stats.yoy,
                    "acceleration": stats.acceleration,
                    "z_score": stats.z_score,
                    "momentum": stats.momentum,
                    "momentum_label": stats.momentum_label,
                    "method": stats.method,
                    "confidence": stats.confidence,
                    "inputs": json.dumps(
                        {"n_points": stats.n, "period": period}, ensure_ascii=False
                    ),
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        MacroAssessment(
                            indicator=ind, country=cty, period=period, **payload
                        )
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning(
                    "macro analyze failed | %s/%s err=%s", ind, cty, exc
                )
        self.db.commit()
        logger.info("macro analyze done | %s", outcome.as_dict())
        return outcome

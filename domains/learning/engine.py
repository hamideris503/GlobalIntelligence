"""Learning Engine — استخراج بینش از تاریخچه و ذخیره (Phase 51).

سه یادگیرنده‌ی v1:
1. accuracy_trend: روند MAE هر مدل دارای ≥۳ دوره عملکرد.
2. regime_base_rate: فراوانی رژیم‌های کلان/بازار در تاریخچه‌ی world_states.
3. threshold_p90: پیشنهاد آستانه برای سیگنال‌های انرژی/استرس/ژئوپلیتیک.

- upsert ماهانه در `learning_insights` (idempotent).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.learning_insight import LearningInsight
from backend.database.models.model_performance import ModelPerformance
from backend.database.models.world_state import WorldState
from domains.learning.learners import (
    Insight,
    accuracy_trend,
    base_rates,
    threshold_p90,
)

logger = get_logger(__name__)

THRESHOLD_SIGNALS = ("energy_risk", "financial_stress", "geopolitical_risk")


@dataclass
class LearningOutcome:
    insights_built: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "insights_built": self.insights_built,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


class LearningEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _collect(self, *, period: str) -> list[Insight]:
        insights: list[Insight] = []

        # 1) روند دقت مدل‌ها
        models = [
            m
            for m in self.db.execute(
                select(ModelPerformance.model).group_by(ModelPerformance.model)
            ).scalars().all()
            if m
        ]
        for model in models:
            rows = list(
                self.db.execute(
                    select(ModelPerformance)
                    .where(
                        ModelPerformance.model == model,
                        ModelPerformance.mae.is_not(None),
                    )
                    .order_by(ModelPerformance.period.asc())
                )
                .scalars()
                .all()
            )
            trend = accuracy_trend([r.mae for r in rows])
            if trend is None:
                continue
            insights.append(
                Insight(
                    kind="accuracy_trend",
                    subject=model,
                    value={
                        "direction": trend.direction,
                        "slope": trend.slope,
                        "n_points": trend.n_points,
                        "periods": [r.period for r in rows],
                    },
                    confidence=trend.confidence,
                )
            )

        # 2) نرخ پایه‌ی رژیم‌ها
        states = list(self.db.execute(select(WorldState)).scalars().all())
        macro_rates = base_rates([s.macro_regime for s in states])
        if macro_rates is not None:
            insights.append(
                Insight(
                    kind="regime_base_rate",
                    subject="macro_regime",
                    value={"rates": macro_rates, "n_states": len(states)},
                    confidence=0.6 if len(states) >= 5 else 0.4,
                )
            )
        market_rates = base_rates([s.market_regime for s in states])
        if market_rates is not None:
            insights.append(
                Insight(
                    kind="regime_base_rate",
                    subject="market_regime",
                    value={"rates": market_rates, "n_states": len(states)},
                    confidence=0.6 if len(states) >= 5 else 0.4,
                )
            )

        # 3) آستانه‌های پیشنهادی
        for signal in THRESHOLD_SIGNALS:
            vals = [
                getattr(s, signal)
                for s in states
                if getattr(s, signal, None) is not None
            ]
            p90 = threshold_p90(vals)
            if p90 is None:
                continue
            insights.append(
                Insight(
                    kind="threshold_p90",
                    subject=signal,
                    value={"p90": p90, "n_points": len(vals)},
                    confidence=0.6,
                )
            )
        return insights

    def run(self, *, period: str | None = None) -> LearningOutcome:
        outcome = LearningOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")
        try:
            insights = self._collect(period=period)
        except Exception as exc:  # noqa: BLE001
            outcome.failed += 1
            outcome.errors.append(f"{type(exc).__name__}: {exc}")
            return outcome
        for insight in insights:
            try:
                outcome.insights_built += 1
                existing = self.db.execute(
                    select(LearningInsight).where(
                        LearningInsight.kind == insight.kind,
                        LearningInsight.subject == insight.subject,
                        LearningInsight.period == period,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.value = json.dumps(insight.value, ensure_ascii=False)
                    existing.confidence = insight.confidence
                    existing.method = insight.method
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        LearningInsight(
                            kind=insight.kind,
                            subject=insight.subject,
                            period=period,
                            value=json.dumps(insight.value, ensure_ascii=False),
                            confidence=insight.confidence,
                            method=insight.method,
                            observed_at=datetime.now(UTC),
                        )
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("learning failed | %s/%s err=%s", insight.kind, insight.subject, exc)
        self.db.commit()
        logger.info("learning done | %s", outcome.as_dict())
        return outcome

"""Performance Engine — ثبت دوره‌ای عملکرد مدل‌ها (Phase 36).

مسیر: outcomeهای امتیازدار → تجمیع هر مدل → upsert ماهانه در `model_performance`.

- idempotent بر اساس UniqueConstraint (model, period).
- مدل بدون outcome امتیازدار ثبت نمی‌شود (نه رکورد تهی).
- بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast
from backend.database.models.model_performance import ModelPerformance
from domains.forecast.evaluation import EvaluationEngine

logger = get_logger(__name__)


@dataclass
class PerformanceOutcome:
    models_recorded: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "models_recorded": self.models_recorded,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


class PerformanceEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._eval = EvaluationEngine(db)

    def _models(self) -> list[str]:
        stmt = (
            select(Forecast.model)
            .where(Forecast.model.is_not(None))
            .group_by(Forecast.model)
            .order_by(Forecast.model)
        )
        return [m for m in self.db.execute(stmt).scalars().all() if m]

    def record(self, *, period: str | None = None) -> PerformanceOutcome:
        outcome = PerformanceOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")
        for model in self._models():
            try:
                agg = self._eval.summary(model=model)
                if agg["n"] <= 0:
                    outcome.skipped += 1
                    continue
                outcome.models_recorded += 1
                existing = self.db.execute(
                    select(ModelPerformance).where(
                        ModelPerformance.model == model,
                        ModelPerformance.period == period,
                    )
                ).scalar_one_or_none()
                payload = {
                    "n_scored": agg["n"],
                    "mae": agg["mae"],
                    "rmse": agg["rmse"],
                    "mean_brier": agg["mean_brier"],
                    "mean_log_loss": agg["mean_log_loss"],
                    "method": "performance_v1",
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        ModelPerformance(model=model, period=period, **payload)
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("performance record failed | %s err=%s", model, exc)
        self.db.commit()
        logger.info("performance record done | %s", outcome.as_dict())
        return outcome

"""Evaluation Engine — امتیازدهی outcomeها و تجمیع (Phase 28).

مسیر: ForecastOutcomeهای دارای actual (value یا bool)
      → امتیاز هر outcome (abs/squared/brier/log_loss) → ذخیره روی همان ردیف.

- idempotent: اجرای دوباره امتیازها را بازنویسی می‌کند (همان ردیف، بدون رکورد جدید).
- خلاصه‌ی تجمیعی (MAE/RMSE/میانگین‌ها/کالیبراسیون) ذخیره نمی‌شود؛ live محاسبه می‌شود.
- بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast, ForecastOutcome
from domains.forecast.metrics import (
    aggregate,
    parse_bool,
    prob_scores,
    value_scores,
)

logger = get_logger(__name__)


@dataclass
class EvaluateOutcome:
    scored: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scored": self.scored,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


class EvaluationEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, *, target: str | None = None) -> EvaluateOutcome:
        outcome = EvaluateOutcome()
        stmt = (
            select(Forecast, ForecastOutcome)
            .join(ForecastOutcome, ForecastOutcome.forecast_id == Forecast.id)
            .where(ForecastOutcome.actual_value.is_not(None))
        )
        if target:
            stmt = stmt.where(Forecast.target == target)
        for fc, oc in self.db.execute(stmt).all():
            try:
                if fc.expected_value is None or oc.actual_value is None:
                    outcome.skipped += 1
                    continue
                vs = value_scores(fc.expected_value, oc.actual_value)
                oc.abs_error = vs.abs_error
                oc.squared_error = vs.squared_error
                actual = parse_bool(oc.actual_bool)
                if fc.probability is not None and actual is not None:
                    ps = prob_scores(fc.probability, actual)
                    oc.brier_score = ps.brier_score
                    oc.log_loss = ps.log_loss
                outcome.scored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("evaluate failed | oc=%s err=%s", oc.id, exc)
        self.db.commit()
        logger.info("evaluate done | %s", outcome.as_dict())
        return outcome

    def summary(
        self, *, target: str | None = None, model: str | None = None
    ) -> dict:
        """تجمیع live روی outcomeهای امتیازدار."""
        stmt = (
            select(Forecast, ForecastOutcome)
            .join(ForecastOutcome, ForecastOutcome.forecast_id == Forecast.id)
            .where(ForecastOutcome.actual_value.is_not(None))
        )
        if target:
            stmt = stmt.where(Forecast.target == target)
        if model:
            stmt = stmt.where(Forecast.model == model)
        abs_e, sq_e, briers, loglosses, pairs = [], [], [], [], []
        for fc, oc in self.db.execute(stmt).all():
            # محاسبه‌ی live از مقادیر خام (مستقل از اجرای قبلی run)
            if fc.expected_value is not None and oc.actual_value is not None:
                vs = value_scores(fc.expected_value, oc.actual_value)
                abs_e.append(vs.abs_error)
                sq_e.append(vs.squared_error)
            actual = parse_bool(oc.actual_bool)
            if fc.probability is not None and actual is not None:
                ps = prob_scores(fc.probability, actual)
                briers.append(ps.brier_score)
                loglosses.append(ps.log_loss)
                pairs.append((fc.probability, actual))
        agg = aggregate(abs_e, sq_e, briers, loglosses, pairs)
        return {
            "n": agg.n,
            "mae": agg.mae,
            "rmse": agg.rmse,
            "mean_brier": agg.mean_brier,
            "mean_log_loss": agg.mean_log_loss,
            "calibration": agg.calibration,
        }

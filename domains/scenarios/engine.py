"""Scenario Engine — ساخت ۴ سناریو از baseline (Phase 30).

مسیر: هدف → baseline (روش مشخص) → σ سری → ۴ ردیف Forecast با
scenario=base/bull/bear/tail (Ledger افزودنی، جانشینی خودکار هم‌خانواده).

- اگر σ ناموجود باشد فقط base ثبت می‌شود و بقیه skip (صادقانه).
- بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast
from backend.database.models.market import MacroObservation, MarketObservation
from domains.forecast.engine import HORIZON_DAYS, MODEL_VERSION, ForecastEngine
from domains.forecast.ledger import ACTIVE, supersede_older
from domains.scenarios.analytics import (
    CONFIDENCE_DISCOUNT,
    build_scenarios,
    series_sigma,
)

logger = get_logger(__name__)


@dataclass
class ScenarioOutcome:
    created: int = 0
    skipped: int = 0
    failed: int = 0
    superseded: int = 0
    forecast_ids: list[str] = field(default_factory=list)
    scenarios: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "skipped": self.skipped,
            "failed": self.failed,
            "superseded": self.superseded,
            "forecast_ids": self.forecast_ids,
            "scenarios": self.scenarios,
            "errors": self.errors,
        }


class ScenarioEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _series_values(self, target: str) -> list[float]:
        from domains.forecast.engine import parse_target

        kind, key, country = parse_target(target)
        if kind == "macro":
            assert country is not None
            stmt = (
                select(MacroObservation.value)
                .where(
                    MacroObservation.indicator == key,
                    MacroObservation.country == country,
                    MacroObservation.value.is_not(None),
                )
                .order_by(MacroObservation.period.asc())
            )
        else:
            stmt = (
                select(MarketObservation.value)
                .where(
                    MarketObservation.symbol == key,
                    MarketObservation.value.is_not(None),
                    MarketObservation.observed_at.is_not(None),
                )
                .order_by(MarketObservation.observed_at.asc())
            )
        return [v for v in self.db.execute(stmt).scalars().all() if v is not None]

    def run(
        self,
        *,
        target: str,
        method: str = "naive",
        horizon: str = "short",
    ) -> ScenarioOutcome:
        from domains.forecast.baselines import METHODS

        outcome = ScenarioOutcome()
        if method not in METHODS:
            outcome.failed += 1
            outcome.errors.append(f"unknown method: {method}")
            return outcome
        if horizon not in HORIZON_DAYS:
            outcome.failed += 1
            outcome.errors.append(f"unknown horizon: {horizon}")
            return outcome

        try:
            values = self._series_values(target)
        except ValueError as exc:
            outcome.failed += 1
            outcome.errors.append(str(exc))
            return outcome
        if not values:
            outcome.skipped += 1
            return outcome

        # 1) baseline برای سناریوی base
        base_out = ForecastEngine(self.db).run(
            target=target, method=method, horizon=horizon, scenario="base"
        )
        if not base_out.forecast_ids:
            outcome.skipped += 1
            outcome.errors.extend(base_out.errors)
            return outcome
        base_fc = None
        for _fid in base_out.forecast_ids:
            base_fc = self.db.get(Forecast, UUID(_fid))
            if base_fc is not None:
                break
        if base_fc is None or base_fc.expected_value is None:
            outcome.failed += 1
            outcome.errors.append("baseline forecast missing")
            return outcome

        model = f"baseline_{method}"
        outcome.created += base_out.created
        outcome.superseded += base_out.superseded
        outcome.forecast_ids.append(str(base_fc.id))
        outcome.scenarios["base"] = base_fc.expected_value

        # 2) شوک‌ها
        sigma = series_sigma(values)
        scenario_set = build_scenarios(base_fc.expected_value, sigma)
        if scenario_set is None:
            outcome.skipped += 3  # bull/bear/tail بدون σ ساخته نمی‌شوند
            return outcome

        now = datetime.now(UTC)
        target_date = now + timedelta(days=HORIZON_DAYS[horizon])
        for name in ("bull", "bear", "tail"):
            try:
                fc = Forecast(
                    valid_from=now,
                    target_date=target_date,
                    horizon=horizon,
                    target=target,
                    expected_value=scenario_set.values[name],
                    interval_low=base_fc.interval_low,
                    interval_high=base_fc.interval_high,
                    confidence=round(
                        (base_fc.confidence or 0.5)
                        * CONFIDENCE_DISCOUNT[name],
                        4,
                    ),
                    model=model,
                    model_version=MODEL_VERSION,
                    scenario=name,
                    status=ACTIVE,
                    data_version=base_fc.data_version,
                    evidence=base_fc.evidence,
                    assumptions=(
                        f"scenario v1: {name} = base { {'bull': '+σ', 'bear': '−σ', 'tail': '−2σ'}[name]}"
                        f" with σ={scenario_set.sigma}; interval copied from base"
                    ),
                )
                self.db.add(fc)
                self.db.flush()
                outcome.created += 1
                outcome.forecast_ids.append(str(fc.id))
                outcome.scenarios[name] = scenario_set.values[name]
                outcome.superseded += supersede_older(
                    self.db,
                    target=target,
                    horizon=horizon,
                    model=model,
                    scenario=name,
                    keep_id=fc.id,
                )
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning(
                    "scenario failed | target=%s scenario=%s err=%s",
                    target, name, exc,
                )
        self.db.commit()
        logger.info("scenarios done | %s", outcome.as_dict())
        return outcome

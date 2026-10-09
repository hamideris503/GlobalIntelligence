"""Forecast Engine — پیش‌بینی Baseline و ثبت در Ledger (Phase 25).

مسیر: سری macro/market → baseline قطعی → ردیف `Forecast` (افزودنی، هرگز حذف).

- هدف: `macro:{indicator}:{country}` یا `market:{symbol}`.
- افق: short/medium/long → ‎+30/180/365 روز به target_date (v1 مستند).
- Ledger افزودنی است (by design، بند 40 ARCHITECTURE)؛ اجرای دوباره ردیف
  جدید می‌سازد، نه به‌روزرسانی — پس idempotent نیست.
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast
from backend.database.models.market import MacroObservation, MarketObservation
from domains.forecast.baselines import METHODS

logger = get_logger(__name__)

MODEL_VERSION = "v1"
HORIZON_DAYS = {"short": 30, "medium": 180, "long": 365}
MARKET_LIMIT = 500


@dataclass
class ForecastOutcome:
    created: int = 0
    skipped: int = 0
    failed: int = 0
    forecast_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "skipped": self.skipped,
            "failed": self.failed,
            "forecast_ids": self.forecast_ids,
            "errors": self.errors,
        }


def parse_target(target: str) -> tuple[str, str, str | None]:
    """(kind, key, country)؛ مثال macro:inflation:USA و market:WTI."""
    parts = target.split(":")
    if len(parts) == 3 and parts[0] == "macro" and all(parts):
        return "macro", parts[1], parts[2]
    if len(parts) == 2 and parts[0] == "market" and all(parts):
        return "market", parts[1], None
    raise ValueError(
        f"bad target {target!r}; expected macro:{{indicator}}:{{country}} "
        "or market:{symbol}"
    )


class ForecastEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _macro_series(self, indicator: str, country: str) -> tuple[list[float], str | None]:
        stmt = (
            select(MacroObservation)
            .where(
                MacroObservation.indicator == indicator,
                MacroObservation.country == country,
            )
            .order_by(MacroObservation.period.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        vals = [r.value for r in rows if r.value is not None]
        last_period = rows[-1].period if rows else None
        return vals, last_period

    def _market_series(self, symbol: str) -> tuple[list[float], str | None]:
        stmt = (
            select(MarketObservation)
            .where(
                MarketObservation.symbol == symbol,
                MarketObservation.value.is_not(None),
                MarketObservation.observed_at.is_not(None),
            )
            .order_by(MarketObservation.observed_at.asc())
            .limit(MARKET_LIMIT)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        vals = [r.value for r in rows if r.value is not None]
        last = rows[-1].observed_at.isoformat() if rows else None
        return vals, last

    def run(
        self,
        *,
        target: str,
        method: str = "all",
        horizon: str = "short",
    ) -> ForecastOutcome:
        outcome = ForecastOutcome()
        if horizon not in HORIZON_DAYS:
            outcome.failed += 1
            outcome.errors.append(f"unknown horizon: {horizon}")
            return outcome
        try:
            kind, key, country = parse_target(target)
        except ValueError as exc:
            outcome.failed += 1
            outcome.errors.append(str(exc))
            return outcome

        if kind == "macro":
            assert country is not None
            values, last_ref = self._macro_series(key, country)
        else:
            values, last_ref = self._market_series(key)

        methods = list(METHODS) if method == "all" else [method]
        if method != "all" and method not in METHODS:
            outcome.failed += 1
            outcome.errors.append(f"unknown method: {method}")
            return outcome

        now = datetime.now(UTC)
        target_date = now + timedelta(days=HORIZON_DAYS[horizon])
        for name in methods:
            try:
                fn = METHODS[name]
                kwargs = {"steps": 1} if name == "random_walk" else {}
                result = fn(values, **kwargs)  # type: ignore[call-arg]
                if result is None:
                    outcome.skipped += 1
                    continue
                fc = Forecast(
                    valid_from=now,
                    target_date=target_date,
                    horizon=horizon,
                    target=target,
                    expected_value=result.expected_value,
                    interval_low=result.interval_low,
                    interval_high=result.interval_high,
                    confidence=result.confidence,
                    model=f"baseline_{name}",
                    model_version=MODEL_VERSION,
                    data_version=f"n={len([v for v in values if v is not None])}"
                    f":{last_ref}",
                    evidence=json.dumps(
                        {"n_points": len(values), "last_ref": last_ref},
                        ensure_ascii=False,
                    ),
                    assumptions=(
                        "baseline v1: no seasonality/trend-break handling; "
                        "interval is in-sample 1-step 95% band, not horizon-scaled"
                    ),
                )
                self.db.add(fc)
                self.db.flush()
                outcome.created += 1
                outcome.forecast_ids.append(str(fc.id))
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning(
                    "forecast failed | target=%s method=%s err=%s", target, name, exc
                )
        self.db.commit()
        logger.info("forecast done | %s", outcome.as_dict())
        return outcome

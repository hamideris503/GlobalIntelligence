"""Economic Data Engine (Phase 16).

مسیر: World Bank API (رایگان) → RawSeries → normalize → upsert در `macro_observations`.

- idempotent بر اساس UniqueConstraint (indicator, country, period, source_name)
- در نبود منبع واقعی، MockFetcher با داده‌ی deterministic
- هیچ AI لازم نیست؛ داده‌ها ساختاریافته و عددی هستند.

Deterministic Core بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.market import MacroObservation
from domains.macro.fetchers import RawSeries, build_fetcher

logger = get_logger(__name__)


@dataclass
class EconomicOutcome:
    fetched: int = 0
    stored: int = 0
    duplicates: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "failed": self.failed,
            "errors": self.errors,
        }


class EconomicDataService:
    def __init__(self, db: Session, fetcher_name: str = "world_bank") -> None:
        self.db = db
        self.fetcher = build_fetcher(fetcher_name)

    def _upsert(self, series: RawSeries) -> tuple[bool, bool]:
        """یک مشاهده را upsert می‌کند. خروجی: (created, duplicate)."""
        existing = self.db.execute(
            select(MacroObservation).where(
                MacroObservation.indicator == series.indicator,
                MacroObservation.country == series.country,
                MacroObservation.period == series.period,
                MacroObservation.source_name == series.source_name,
            )
        ).scalar_one_or_none()

        if existing is not None:
            # به‌روزرسانی مقدار و متادیتا (idempotent)
            existing.value = series.value
            existing.unit = series.unit
            existing.frequency = series.frequency
            existing.series_id = series.series_id
            existing.meta = (
                json.dumps(series.metadata, ensure_ascii=False)
                if series.metadata
                else None
            )
            return False, True

        obs = MacroObservation(
            indicator=series.indicator,
            country=series.country,
            period=series.period,
            value=series.value,
            unit=series.unit,
            frequency=series.frequency,
            source_name=series.source_name,
            series_id=series.series_id,
            meta=(
                json.dumps(series.metadata, ensure_ascii=False)
                if series.metadata
                else None
            ),
        )
        self.db.add(obs)
        self.db.flush()
        return True, False

    async def fetch_indicator(
        self, *, indicator: str, country: str, limit: int = 10
    ) -> EconomicOutcome:
        outcome = EconomicOutcome()
        try:
            rows = await self.fetcher.fetch(
                indicator=indicator, country=country, limit=limit
            )
        except Exception as exc:  # noqa: BLE001
            outcome.failed += 1
            outcome.errors.append(f"{type(exc).__name__}: {exc}")
            logger.warning(
                "economic fetch failed | indicator=%s country=%s err=%s",
                indicator,
                country,
                exc,
            )
            return outcome

        outcome.fetched = len(rows)
        for series in rows:
            try:
                created, dup = self._upsert(series)
                if created:
                    outcome.stored += 1
                elif dup:
                    outcome.duplicates += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
        self.db.commit()
        return outcome

    async def run(
        self,
        *,
        indicators: list[str] | None = None,
        countries: list[str] | None = None,
        limit: int = 10,
    ) -> EconomicOutcome:
        total = EconomicOutcome()
        indicators = indicators or [
            "inflation",
            "gdp",
            "unemployment",
            "interest_rate",
            "trade_balance",
            "liquidity",
        ]
        countries = countries or ["USA", "IRN", "DEU", "CHN", "GBR"]
        for indicator in indicators:
            for country in countries:
                try:
                    res = await self.fetch_indicator(
                        indicator=indicator, country=country, limit=limit
                    )
                    total.fetched += res.fetched
                    total.stored += res.stored
                    total.duplicates += res.duplicates
                    total.failed += res.failed
                    total.errors.extend(res.errors)
                except Exception as exc:  # noqa: BLE001
                    total.failed += 1
                    total.errors.append(f"{type(exc).__name__}: {exc}")
                    logger.warning(
                        "economic run failed | indicator=%s country=%s err=%s",
                        indicator,
                        country,
                        exc,
                    )
        logger.info("economic data done | %s", total.as_dict())
        return total

"""Fetchers داده‌ی اقتصادی (Phase 16).

- `WorldBankFetcher`: API رایگان بانک جهانی (بدون کلید) برای شاخص‌های
  inflation/GDP/unemployment/interest_rate/trade_balance/liquidity.
- `MockFetcher`: داده‌ی نمونه برای حالت آفلاین/MOCK_MODE.

هیچ Fetcher نباید مستقیماً DB را بنویسد؛ فقط `RawSeries` برمی‌گرداند.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.core.logging import get_logger

logger = get_logger(__name__)

# نگاشت شاخص‌های بانک جهانی به EconomicIndicator
# https://datahelpdesk.worldbank.org/knowledgebase/articles/2093198-indicator-api-queries
WB_INDICATORS: dict[str, dict[str, str]] = {
    "inflation": {
        "code": "FP.CPI.TOTL.ZG",
        "unit": "percent",
        "frequency": "annual",
    },
    "gdp": {
        "code": "NY.GDP.MKTP.CD",
        "unit": "current_usd",
        "frequency": "annual",
    },
    "unemployment": {
        "code": "SL.UEM.TOTL.ZS",
        "unit": "percent",
        "frequency": "annual",
    },
    "interest_rate": {
        "code": "FR.INR.RINR",
        "unit": "percent",
        "frequency": "annual",
    },
    "trade_balance": {
        "code": "NE.RSB.GNFS.ZS",
        "unit": "percent_of_gdp",
        "frequency": "annual",
    },
    "liquidity": {
        "code": "LTDT.DOMS.CD",
        "unit": "current_usd",
        "frequency": "annual",
    },
}

WB_BASE_URL = "https://api.worldbank.org/v2"


@dataclass
class RawSeries:
    """یک سری زمانی خام دریافتی از منبع."""

    indicator: str
    country: str
    period: str
    value: float | None
    unit: str | None = None
    frequency: str | None = None
    source_name: str | None = None
    series_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseFetcher(ABC):
    """قرارداد دریافت داده‌ی اقتصادی."""

    name: str = "base"

    @abstractmethod
    async def fetch(
        self, *, indicator: str, country: str, limit: int = 10
    ) -> list[RawSeries]:
        raise NotImplementedError


class WorldBankFetcher(BaseFetcher):
    """دریافت از API رایگان بانک جهانی (بدون کلید)."""

    name = "world_bank"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(
        self, *, indicator: str, country: str, limit: int = 10
    ) -> list[RawSeries]:
        info = WB_INDICATORS.get(indicator)
        if info is None:
            logger.warning("worldbank: unknown indicator %s", indicator)
            return []
        code = info["code"]
        url = (
            f"{WB_BASE_URL}/country/{country}/indicator/{code}"
            f"?format=json&per_page={limit * 2}&date=2000:2030"
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
        # ساختار بانک جهانی: [متادیتا, [ردیف‌ها]]
        rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        out: list[RawSeries] = []
        for row in rows:
            value = row.get("value")
            period = row.get("date")
            if value is None or period is None:
                continue
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                continue
            out.append(
                RawSeries(
                    indicator=indicator,
                    country=country,
                    period=str(period),
                    value=value_f,
                    unit=info["unit"],
                    frequency=info["frequency"],
                    source_name=self.name,
                    series_id=f"WB:{code}:{country}",
                    metadata={"indicator_code": code, "source_url": url},
                )
            )
            if len(out) >= limit:
                break
        return out


class MockFetcher(BaseFetcher):
    """داده‌ی نمونه‌ی deterministic برای آفلاین/MOCK_MODE."""

    name = "mock"

    async def fetch(
        self, *, indicator: str, country: str, limit: int = 10
    ) -> list[RawSeries]:
        info = WB_INDICATORS.get(indicator, {"unit": "index", "frequency": "annual"})
        out: list[RawSeries] = []
        for i in range(min(limit, 5)):
            year = 2020 + i
            out.append(
                RawSeries(
                    indicator=indicator,
                    country=country,
                    period=str(year),
                    value=round(1.0 + i * 0.5, 2),
                    unit=info["unit"],
                    frequency=info["frequency"],
                    source_name=self.name,
                    series_id=f"MOCK:{indicator}:{country}",
                    metadata={"mock": True},
                )
            )
        return out


def build_fetcher(name: str) -> BaseFetcher:
    """ساخت Fetcher بر اساس نام."""
    if name == "world_bank":
        return WorldBankFetcher()
    if name == "mock":
        return MockFetcher()
    raise ValueError(f"unknown fetcher: {name}")


__all__ = [
    "BaseFetcher",
    "WorldBankFetcher",
    "MockFetcher",
    "RawSeries",
    "WB_INDICATORS",
    "build_fetcher",
    "json",
]

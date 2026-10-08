"""Fetchers داده‌ی بازار (Phase 17).

منابع رایگان و بدون کلید (Free-First):
- `ErApiFxFetcher`: نرخ‌های FX از open.er-api.com (primary)
- `EcbFxFetcher`: نرخ‌های مرجع بانک مرکزی اروپا XML (fallback رسمی FX)
- `GoldApiFetcher`: قیمت لحظه‌ای طلا/نقره (XAU/XAG)
- `YahooFetcher`: نفت/طلا/سهام/اوراق/کالا از Yahoo Finance v8 chart
- `MockFetcher`: داده‌ی نمونه‌ی deterministic برای آفلاین/MOCK_MODE.

هیچ Fetcher نباید مستقیماً DB را بنویسد؛ فقط `RawQuote` برمی‌گرداند.
"""
from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from backend.core.logging import get_logger

logger = get_logger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (GlobalIntelligence)"}

# کاتالوگ نمادها: symbol -> {asset_class, unit, currency, yahoo}
# Yahoo symbols برای YahooFetcher؛ FX از er-api/ECB می‌آید.
SYMBOLS: dict[str, dict[str, str]] = {
    # FX (er-api / ECB)
    "EURUSD": {"asset_class": "fx", "unit": "ratio", "currency": "USD", "base": "EUR"},
    "GBPUSD": {"asset_class": "fx", "unit": "ratio", "currency": "USD", "base": "GBP"},
    "USDJPY": {"asset_class": "fx", "unit": "ratio", "currency": "JPY", "base": "USD"},
    "USDCHF": {"asset_class": "fx", "unit": "ratio", "currency": "CHF", "base": "USD"},
    # Metals
    "XAUUSD": {"asset_class": "metal", "unit": "usd_per_oz", "currency": "USD", "yahoo": "GC=F", "goldapi": "XAU"},
    "XAGUSD": {"asset_class": "metal", "unit": "usd_per_oz", "currency": "USD", "yahoo": "SI=F", "goldapi": "XAG"},
    # Energy
    "WTI": {"asset_class": "energy", "unit": "usd_per_bbl", "currency": "USD", "yahoo": "CL=F"},
    "BRENT": {"asset_class": "energy", "unit": "usd_per_bbl", "currency": "USD", "yahoo": "BZ=F"},
    "NATGAS": {"asset_class": "energy", "unit": "usd_per_mmbtu", "currency": "USD", "yahoo": "NG=F"},
    # Equities
    "SPX": {"asset_class": "equity_index", "unit": "index", "currency": "USD", "yahoo": "^GSPC"},
    "AAPL": {"asset_class": "equity", "unit": "usd", "currency": "USD", "yahoo": "AAPL"},
    # Bonds (yield)
    "US10Y": {"asset_class": "bond_yield", "unit": "percent", "currency": "USD", "yahoo": "^TNX"},
    # Commodities
    "COPPER": {"asset_class": "commodity", "unit": "usd_per_lb", "currency": "USD", "yahoo": "HG=F"},
}


@dataclass
class RawQuote:
    """یک نقل‌قول خام بازار."""

    symbol: str
    asset_class: str
    value: float | None
    unit: str | None = None
    currency: str | None = None
    source_name: str | None = None
    observed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseFetcher(ABC):
    """قرارداد دریافت داده‌ی بازار."""

    name: str = "base"

    @abstractmethod
    async def fetch(self, *, symbol: str) -> RawQuote | None:
        raise NotImplementedError


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:  # noqa: BLE001
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None


class ErApiFxFetcher(BaseFetcher):
    """نرخ FX از open.er-api.com (رایگان، بدون کلید). base=USD."""

    name = "er_api"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self._cache: dict[str, Any] | None = None

    async def _rates(self) -> dict[str, Any]:
        if self._cache is None:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get("https://open.er-api.com/v6/latest/USD")
                resp.raise_for_status()
                self._cache = resp.json()
        return self._cache

    async def fetch(self, *, symbol: str) -> RawQuote | None:
        info = SYMBOLS.get(symbol)
        if info is None or info["asset_class"] != "fx":
            return None
        data = await self._rates()
        rates = data.get("rates", {})
        base, cur = info["base"], info["currency"]
        # er-api با base=USD است؛ cross برای جفت‌های غیر USD
        usd_base = float(rates.get(base, 1.0))
        usd_cur = float(rates.get(cur, 1.0))
        if not usd_base or not usd_cur:
            return None
        value = usd_cur / usd_base
        return RawQuote(
            symbol=symbol,
            asset_class="fx",
            value=value,
            unit=info["unit"],
            currency=cur,
            source_name=self.name,
            observed_at=_parse_utc(data.get("time_last_update_utc")),
            metadata={"base": base},
        )


class EcbFxFetcher(BaseFetcher):
    """نرخ مرجع روزانه ECB (XML رسمی، fallback FX). base=EUR."""

    name = "ecb"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self._cache: tuple[str | None, dict[str, float]] | None = None

    async def _rates(self) -> tuple[str | None, dict[str, float]]:
        if self._cache is None:
            url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
            ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
            day, out = None, {"EUR": 1.0}
            for cube in root.findall(".//e:Cube[@time]", ns):
                day = cube.get("time")
                for rate in cube.findall("e:Cube", ns):
                    try:
                        out[rate.get("currency", "")] = float(rate.get("rate", "0"))
                    except (TypeError, ValueError):
                        continue
                break
            self._cache = (day, out)
        return self._cache

    async def fetch(self, *, symbol: str) -> RawQuote | None:
        info = SYMBOLS.get(symbol)
        if info is None or info["asset_class"] != "fx":
            return None
        day, rates = await self._rates()
        base, cur = info["base"], info["currency"]
        if base not in rates or cur not in rates or not rates[base]:
            return None
        value = rates[cur] / rates[base]
        observed = None
        if day:
            try:
                observed = datetime.fromisoformat(day).replace(tzinfo=UTC)
            except ValueError:
                observed = None
        return RawQuote(
            symbol=symbol,
            asset_class="fx",
            value=value,
            unit=info["unit"],
            currency=cur,
            source_name=self.name,
            observed_at=observed,
            metadata={"base": base, "reference_day": day},
        )


class GoldApiFetcher(BaseFetcher):
    """قیمت لحظه‌ای طلا/نقره از gold-api.com (رایگان، بدون کلید)."""

    name = "gold_api"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    async def fetch(self, *, symbol: str) -> RawQuote | None:
        info = SYMBOLS.get(symbol)
        code = (info or {}).get("goldapi")
        if not code:
            return None
        url = f"https://api.gold-api.com/price/{code}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        try:
            value = float(data["price"])
        except (KeyError, TypeError, ValueError):
            logger.warning("gold-api: bad payload for %s", symbol)
            return None
        return RawQuote(
            symbol=symbol,
            asset_class="metal",
            value=value,
            unit=info["unit"],
            currency="USD",
            source_name=self.name,
            observed_at=_parse_utc(data.get("updatedAt")),
            metadata={"goldapi_symbol": code},
        )


class YahooFetcher(BaseFetcher):
    """آخرین close از Yahoo Finance v8 chart (رایگان، بدون کلید)."""

    name = "yahoo"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    async def fetch(self, *, symbol: str) -> RawQuote | None:
        info = SYMBOLS.get(symbol)
        yahoo = (info or {}).get("yahoo")
        if not yahoo:
            return None
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}?interval=1d&range=5d"
        async with httpx.AsyncClient(timeout=self.timeout, headers=UA) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        try:
            result = data["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            stamps = result["timestamp"]
            # آخرین close غیرتهی
            value, ts = None, None
            for c, t in zip(reversed(closes), reversed(stamps), strict=False):
                if c is not None:
                    value, ts = float(c), t
                    break
            if value is None:
                return None
            observed = datetime.fromtimestamp(ts, tz=UTC) if ts else None
        except (KeyError, IndexError, TypeError, ValueError):
            logger.warning("yahoo: bad payload for %s", symbol)
            return None
        return RawQuote(
            symbol=symbol,
            asset_class=info["asset_class"],
            value=value,
            unit=info["unit"],
            currency=info.get("currency", "USD"),
            source_name=self.name,
            observed_at=observed,
            metadata={"yahoo_symbol": yahoo},
        )


class MockFetcher(BaseFetcher):
    """نقل‌قول نمونه‌ی deterministic برای آفلاین/MOCK_MODE."""

    name = "mock"

    async def fetch(self, *, symbol: str) -> RawQuote | None:
        info = SYMBOLS.get(symbol)
        if info is None:
            return None
        seed = sum(ord(c) for c in symbol) % 100
        return RawQuote(
            symbol=symbol,
            asset_class=info["asset_class"],
            value=round(100.0 + seed, 2),
            unit=info["unit"],
            currency=info.get("currency", "USD"),
            source_name=self.name,
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            metadata={"mock": True},
        )


def build_fetcher(name: str) -> BaseFetcher:
    """ساخت Fetcher بر اساس نام."""
    mapping = {
        "er_api": ErApiFxFetcher,
        "ecb": EcbFxFetcher,
        "gold_api": GoldApiFetcher,
        "yahoo": YahooFetcher,
        "mock": MockFetcher,
    }
    cls = mapping.get(name)
    if cls is None:
        raise ValueError(f"unknown fetcher: {name}")
    return cls()


def _parse_csv_rows(text: str) -> list[dict[str, str]]:
    """پارس CSV generیک (برای استفاده‌ی آتی/تست)."""
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


__all__ = [
    "BaseFetcher",
    "EcbFxFetcher",
    "ErApiFxFetcher",
    "GoldApiFetcher",
    "MockFetcher",
    "RawQuote",
    "SYMBOLS",
    "YahooFetcher",
    "build_fetcher",
]

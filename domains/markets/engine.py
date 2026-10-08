"""Market Data Engine (Phase 17).

مسیر: منابع رایگان (er-api/ECB/Yahoo/gold-api) → RawQuote → upsert در `market_observations`.

- idempotent بر اساس UniqueConstraint (symbol, observed_at, source_name)
- برای FX: تلاش er-api و fallback به ECB
- خطای هر نماد ایزوله است (failed/errors) و بقیه ادامه می‌یابند.

Deterministic Core بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.market import MarketObservation
from domains.markets.fetchers import (
    SYMBOLS,
    EcbFxFetcher,
    ErApiFxFetcher,
    GoldApiFetcher,
    RawQuote,
    YahooFetcher,
    build_fetcher,
)

logger = get_logger(__name__)


@dataclass
class MarketOutcome:
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


class MarketDataService:
    def __init__(self, db: Session, fetcher_name: str = "auto") -> None:
        self.db = db
        self.fetcher_name = fetcher_name

    def _fetchers_for(self, symbol: str) -> list:
        """زنجیره‌ی fetcher مناسب هر نماد (primary → fallback)."""
        info = SYMBOLS.get(symbol, {})
        asset = info.get("asset_class")
        if self.fetcher_name == "mock":
            return [build_fetcher("mock")]
        if self.fetcher_name != "auto":
            return [build_fetcher(self.fetcher_name)]
        if asset == "fx":
            return [ErApiFxFetcher(), EcbFxFetcher()]
        if asset == "metal":
            return [GoldApiFetcher(), YahooFetcher()]
        return [YahooFetcher()]

    def _upsert(self, quote: RawQuote) -> tuple[bool, bool]:
        """یک مشاهده را upsert می‌کند. خروجی: (created, duplicate)."""
        observed = quote.observed_at or datetime.now(UTC)
        existing = self.db.execute(
            select(MarketObservation).where(
                MarketObservation.symbol == quote.symbol,
                MarketObservation.observed_at == observed,
                MarketObservation.source_name == quote.source_name,
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.value = quote.value
            existing.unit = quote.unit
            existing.currency = quote.currency
            existing.asset_class = quote.asset_class
            existing.raw = json.dumps(quote.metadata, ensure_ascii=False) or None
            return False, True

        obs = MarketObservation(
            symbol=quote.symbol,
            asset_class=quote.asset_class,
            value=quote.value,
            unit=quote.unit,
            currency=quote.currency,
            source_name=quote.source_name,
            raw=json.dumps(quote.metadata, ensure_ascii=False) or None,
            observed_at=observed,
            retrieved_at=datetime.now(UTC),
            available_at=datetime.now(UTC),
        )
        self.db.add(obs)
        self.db.flush()
        return True, False

    async def fetch_symbol(self, *, symbol: str) -> MarketOutcome:
        outcome = MarketOutcome()
        if symbol not in SYMBOLS:
            outcome.failed += 1
            outcome.errors.append(f"unknown symbol: {symbol}")
            return outcome
        quote: RawQuote | None = None
        last_err = ""
        for fetcher in self._fetchers_for(symbol):
            try:
                quote = await fetcher.fetch(symbol=symbol)
                if quote is not None and quote.value is not None:
                    break
            except Exception as exc:  # noqa: BLE001
                last_err = f"{fetcher.name}: {type(exc).__name__}"
                logger.warning(
                    "market fetch failed | symbol=%s fetcher=%s err=%s",
                    symbol, fetcher.name, exc,
                )
                continue
        if quote is None or quote.value is None:
            outcome.failed += 1
            outcome.errors.append(last_err or f"no quote for {symbol}")
            return outcome
        outcome.fetched = 1
        try:
            created, dup = self._upsert(quote)
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
        self, *, symbols: list[str] | None = None, asset_class: str | None = None
    ) -> MarketOutcome:
        total = MarketOutcome()
        targets = symbols or [
            s for s, info in SYMBOLS.items()
            if asset_class is None or info["asset_class"] == asset_class
        ]
        for symbol in targets:
            try:
                res = await self.fetch_symbol(symbol=symbol)
                total.fetched += res.fetched
                total.stored += res.stored
                total.duplicates += res.duplicates
                total.failed += res.failed
                total.errors.extend(res.errors)
            except Exception as exc:  # noqa: BLE001
                total.failed += 1
                total.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("market run failed | symbol=%s err=%s", symbol, exc)
        logger.info("market data done | %s", total.as_dict())
        return total

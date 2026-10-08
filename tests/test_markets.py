"""Tests for Market Data engine & API (Phase 17)."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.database.models.market import MarketObservation
from domains.markets.engine import MarketDataService
from domains.markets.fetchers import SYMBOLS, MockFetcher, build_fetcher
from tests.conftest import TestingSession


def test_symbols_catalog_covers_roadmap() -> None:
    """کاتالوگ باید هر ۶ گروه ROADMAP را پوشش دهد."""
    classes = {info["asset_class"] for info in SYMBOLS.values()}
    assert "fx" in classes
    assert "metal" in classes  # Gold
    assert "energy" in classes  # Oil
    assert "equity" in classes or "equity_index" in classes  # Stocks
    assert "bond_yield" in classes  # Bonds
    assert "commodity" in classes  # Commodities


def test_build_fetcher_unknown() -> None:
    try:
        build_fetcher("nope")
    except ValueError as exc:
        assert "unknown fetcher" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_mock_fetcher_is_deterministic() -> None:
    """MockFetcher باید مقدار ثابت و تکرارپذیر بدهد."""
    fetcher = MockFetcher()
    q1 = asyncio.run(fetcher.fetch(symbol="XAUUSD"))
    q2 = asyncio.run(fetcher.fetch(symbol="XAUUSD"))
    assert q1 is not None and q2 is not None
    assert q1.value == q2.value
    assert q1.symbol == "XAUUSD"


def test_mock_fetcher_unknown_symbol() -> None:
    fetcher = MockFetcher()
    assert asyncio.run(fetcher.fetch(symbol="NOPE")) is None


def test_fetch_symbol_stores_quote() -> None:
    session = TestingSession()
    try:
        service = MarketDataService(session, fetcher_name="mock")
        outcome = asyncio.run(service.fetch_symbol(symbol="WTI"))
        assert outcome.stored == 1
        assert outcome.fetched == 1
        obs = session.query(MarketObservation).one()
        assert obs.symbol == "WTI"
        assert obs.asset_class == "energy"
        assert obs.value is not None
    finally:
        session.close()


def test_fetch_symbol_unknown() -> None:
    session = TestingSession()
    try:
        service = MarketDataService(session, fetcher_name="mock")
        outcome = asyncio.run(service.fetch_symbol(symbol="NOPE"))
        assert outcome.failed == 1
        assert outcome.stored == 0
    finally:
        session.close()


def test_upsert_is_idempotent() -> None:
    """اجرای دوباره با همان observed_at باید duplicate شود."""
    session = TestingSession()
    try:
        service = MarketDataService(session, fetcher_name="mock")
        first = asyncio.run(service.fetch_symbol(symbol="EURUSD"))
        assert first.stored == 1
        second = asyncio.run(service.fetch_symbol(symbol="EURUSD"))
        assert second.stored == 0
        assert second.duplicates == 1
        assert session.query(MarketObservation).count() == 1
    finally:
        session.close()


def test_run_asset_class_filter() -> None:
    session = TestingSession()
    try:
        service = MarketDataService(session, fetcher_name="mock")
        outcome = asyncio.run(service.run(asset_class="energy"))
        expected = sum(1 for i in SYMBOLS.values() if i["asset_class"] == "energy")
        assert outcome.stored == expected
        assert outcome.failed == 0
    finally:
        session.close()


def test_markets_api_fetch(client: TestClient) -> None:
    res = client.post("/api/markets/fetch?symbol=XAUUSD&fetcher=mock")
    assert res.status_code == 200
    body = res.json()
    assert body["stored"] == 1

    obs = client.get("/api/markets/observations?symbol=XAUUSD")
    assert obs.status_code == 200
    assert len(obs.json()) == 1
    assert obs.json()[0]["asset_class"] == "metal"


def test_markets_api_symbols(client: TestClient) -> None:
    res = client.get("/api/markets/symbols")
    assert res.status_code == 200
    assert "WTI" in res.json()
    assert "US10Y" in res.json()


def test_markets_api_latest(client: TestClient) -> None:
    client.post("/api/markets/fetch?symbol=WTI&fetcher=mock")
    client.post("/api/markets/fetch?symbol=BRENT&fetcher=mock")
    res = client.get("/api/markets/latest?asset_class=energy")
    assert res.status_code == 200
    symbols = {o["symbol"] for o in res.json()}
    assert {"WTI", "BRENT"} <= symbols

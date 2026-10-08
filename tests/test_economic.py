"""Tests for Economic Data engine & API (Phase 16)."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend.database.models.market import MacroObservation
from domains.macro.engine import EconomicDataService
from domains.macro.fetchers import WB_INDICATORS, MockFetcher
from tests.conftest import TestingSession


def test_wb_indicators_mapping() -> None:
    """شاخص‌های پشتیبانی‌شده بانک جهانی معتبر باشند."""
    assert "inflation" in WB_INDICATORS
    assert WB_INDICATORS["inflation"]["code"] == "FP.CPI.TOTL.ZG"
    assert WB_INDICATORS["gdp"]["code"] == "NY.GDP.MKTP.CD"
    assert WB_INDICATORS["unemployment"]["code"] == "SL.UEM.TOTL.ZS"


def test_mock_fetcher_returns_series() -> None:
    """MockFetcher باید سری deterministic برگرداند."""
    fetcher = MockFetcher()
    rows = asyncio.run(fetcher.fetch(indicator="inflation", country="USA", limit=5))
    assert len(rows) == 5
    assert rows[0].indicator == "inflation"
    assert rows[0].country == "USA"
    assert rows[0].value is not None
    assert rows[0].series_id == "MOCK:inflation:USA"


def test_upsert_creates_observation() -> None:
    """EconomicDataService باید مشاهده بسازد."""
    session = TestingSession()
    try:
        service = EconomicDataService(session, fetcher_name="mock")
        outcome = asyncio.run(
            service.fetch_indicator(indicator="inflation", country="USA", limit=5)
        )
        assert outcome.stored == 5
        assert session.query(MacroObservation).count() == 5
    finally:
        session.close()


def test_upsert_is_idempotent() -> None:
    """اجرای دوباره باید duplicate شمارش کند، نه رکورد جدید."""
    session = TestingSession()
    try:
        service = EconomicDataService(session, fetcher_name="mock")
        first = asyncio.run(
            service.fetch_indicator(indicator="inflation", country="USA", limit=5)
        )
        assert first.stored == 5
        second = asyncio.run(
            service.fetch_indicator(indicator="inflation", country="USA", limit=5)
        )
        assert second.stored == 0
        assert second.duplicates == 5
        assert session.query(MacroObservation).count() == 5
    finally:
        session.close()


def test_series_id_and_metadata_stored() -> None:
    """series_id و metadata باید ذخیره شوند."""
    session = TestingSession()
    try:
        service = EconomicDataService(session, fetcher_name="mock")
        asyncio.run(
            service.fetch_indicator(indicator="gdp", country="IRN", limit=3)
        )
        obs = session.query(MacroObservation).first()
        assert obs.series_id == "MOCK:gdp:IRN"
        meta = json.loads(obs.meta or "{}")
        assert meta.get("mock") is True
    finally:
        session.close()


def test_run_multiple_indicators() -> None:
    """run باید چند شاخص و کشور را پردازش کند."""
    session = TestingSession()
    try:
        service = EconomicDataService(session, fetcher_name="mock")
        outcome = asyncio.run(
            service.run(
                indicators=["inflation", "gdp"],
                countries=["USA", "IRN"],
                limit=3,
            )
        )
        assert outcome.stored == 12  # 2 indicators × 2 countries × 3 years
        assert session.query(MacroObservation).count() == 12
    finally:
        session.close()


def test_economic_api_fetch(client: TestClient) -> None:
    """API fetch باید مشاهده بسازد."""
    res = client.post("/api/economic/fetch?indicator=inflation&country=USA&limit=5&fetcher=mock")
    assert res.status_code == 200
    body = res.json()
    assert body["stored"] == 5

    obs = client.get("/api/economic/observations?indicator=inflation")
    assert obs.status_code == 200
    assert len(obs.json()) == 5


def test_economic_api_indicators(client: TestClient) -> None:
    """API indicators باید لیست شاخص‌ها را برگرداند."""
    res = client.get("/api/economic/indicators")
    assert res.status_code == 200
    body = res.json()
    assert "inflation" in body
    assert body["inflation"]["code"] == "FP.CPI.TOTL.ZG"


def test_economic_api_latest(client: TestClient) -> None:
    """API latest باید آخرین مشاهدات را برگرداند."""
    client.post("/api/economic/fetch?indicator=inflation&country=USA&limit=5&fetcher=mock")
    res = client.get("/api/economic/latest?indicator=inflation")
    assert res.status_code == 200
    body = res.json()
    assert len(body) > 0
    # آخرین period باید بالاترین سال باشد
    periods = [o["period"] for o in body]
    assert "2024" in periods

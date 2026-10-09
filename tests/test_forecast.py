"""Tests for Forecast Engine baselines, service & API (Phase 25)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast
from backend.database.models.market import MacroObservation, MarketObservation
from domains.forecast import baselines as bl
from domains.forecast.engine import ForecastEngine, parse_target
from tests.conftest import TestingSession


def _seed_macro(indicator: str, country: str, rows: list[tuple[str, float]]) -> None:
    session = TestingSession()
    try:
        for period, value in rows:
            session.add(
                MacroObservation(
                    indicator=indicator,
                    country=country,
                    period=period,
                    value=value,
                    source_name="test",
                )
            )
        session.commit()
    finally:
        session.close()


def _seed_market(symbol: str, values: list[float]) -> None:
    session = TestingSession()
    try:
        base = datetime.now(UTC) - timedelta(days=len(values))
        for i, value in enumerate(values):
            session.add(
                MarketObservation(
                    symbol=symbol,
                    asset_class="test",
                    value=value,
                    source_name="test",
                    observed_at=base + timedelta(days=i),
                )
            )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_naive_mapping() -> None:
    r = bl.naive([1.0, 2.0, 4.0])
    assert r is not None
    assert r.expected_value == 4.0
    assert r.interval_low is not None and r.interval_high is not None
    assert bl.naive([]) is None
    # تک‌نقطه و تفاضل ثابت: بازه None (نه جعلی)
    r1 = bl.naive([5.0])
    assert r1 is not None and r1.interval_low is None
    r2 = bl.naive([1.0, 2.0, 3.0])
    assert r2 is not None and r2.interval_low is None


def test_historical_mean_mapping() -> None:
    r = bl.historical_mean([1.0, 2.0, 3.0])
    assert r is not None and r.expected_value == 2.0
    assert bl.historical_mean([1.0]) is None


def test_random_walk_mapping() -> None:
    r = bl.random_walk([100.0, 102.0, 104.0])
    assert r is not None
    assert r.expected_value == 106.0  # رانش ۲
    assert bl.random_walk([100.0]) is None


def test_flat_series_no_interval() -> None:
    r = bl.naive([5.0, 5.0, 5.0])
    assert r is not None and r.interval_low is None  # واریانس صفر


def test_parse_target() -> None:
    assert parse_target("macro:inflation:USA") == ("macro", "inflation", "USA")
    assert parse_target("market:WTI") == ("market", "WTI", None)
    try:
        parse_target("bad")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


# --- engine tests ---
def test_engine_runs_all_methods() -> None:
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        outcome = ForecastEngine(session).run(target="macro:inflation:USA")
        assert outcome.created == 3
        assert session.query(Forecast).count() == 3
        naive_fc = (
            session.query(Forecast).filter_by(model="baseline_naive").one()
        )
        assert naive_fc.expected_value == 2.95
        assert naive_fc.data_version.startswith("n=3:")
    finally:
        session.close()


def test_engine_single_method_market() -> None:
    _seed_market("WTI", [90.0, 91.0, 92.0])
    session = TestingSession()
    try:
        outcome = ForecastEngine(session).run(target="market:WTI", method="naive")
        assert outcome.created == 1
    finally:
        session.close()


def test_engine_skips_empty_series() -> None:
    session = TestingSession()
    try:
        outcome = ForecastEngine(session).run(target="macro:gdp:XXX")
        assert outcome.created == 0
        assert outcome.skipped == 3
    finally:
        session.close()


def test_engine_bad_inputs() -> None:
    session = TestingSession()
    try:
        bad_target = ForecastEngine(session).run(target="nope")
        assert bad_target.failed == 1
        bad_method = ForecastEngine(session).run(
            target="market:WTI", method="arima"
        )
        assert bad_method.failed == 1
        bad_horizon = ForecastEngine(session).run(
            target="market:WTI", horizon="decade"
        )
        assert bad_horizon.failed == 1
    finally:
        session.close()


def test_ledger_is_append_only() -> None:
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        ForecastEngine(session).run(target="macro:gdp:USA", method="naive")
        ForecastEngine(session).run(target="macro:gdp:USA", method="naive")
        assert session.query(Forecast).count() == 2
    finally:
        session.close()


# --- API tests ---
def test_forecasts_api(client: TestClient) -> None:
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    res = client.post("/api/forecasts/run?target=macro:inflation:USA&method=naive")
    assert res.status_code == 200
    assert res.json()["created"] == 1
    fid = res.json()["forecast_ids"][0]

    lst = client.get("/api/forecasts?target=macro:inflation:USA")
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    one = client.get(f"/api/forecasts/{fid}")
    assert one.status_code == 200
    assert one.json()["expected_value"] == 2.95

    missing = client.get("/api/forecasts/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404

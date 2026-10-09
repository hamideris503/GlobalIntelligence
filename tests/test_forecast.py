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


# --- Phase 26: Ledger tests ---
def test_auto_supersede_on_rerun() -> None:
    """ثبت جدید هم‌خانواده، قبلی active را superseded می‌کند (بدون حذف)."""
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        first = ForecastEngine(session).run(target="macro:gdp:USA", method="naive")
        assert first.created == 1 and first.superseded == 0
        second = ForecastEngine(session).run(target="macro:gdp:USA", method="naive")
        assert second.created == 1 and second.superseded == 1
        rows = session.query(Forecast).order_by(Forecast.created_at).all()
        assert len(rows) == 2  # Ledger افزودنی: هیچ حذفی نیست
        assert rows[0].status == "superseded"
        assert rows[1].status == "active"
        assert rows[1].scenario == "base"
    finally:
        session.close()


def test_different_scenario_not_superseded() -> None:
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        ForecastEngine(session).run(
            target="macro:gdp:USA", method="naive", scenario="base"
        )
        out = ForecastEngine(session).run(
            target="macro:gdp:USA", method="naive", scenario="bull"
        )
        assert out.superseded == 0
        assert session.query(Forecast).count() == 2
    finally:
        session.close()


def test_manual_supersede() -> None:
    from domains.forecast.ledger import mark_superseded

    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        out = ForecastEngine(session).run(target="macro:gdp:USA", method="naive")
        fid = out.forecast_ids[0]
        import uuid as _uuid

        fc = mark_superseded(session, _uuid.UUID(fid))
        assert fc is not None and fc.status == "superseded"
        assert mark_superseded(session, _uuid.UUID(int=0)) is None
    finally:
        session.close()


def test_active_as_of() -> None:
    from datetime import timedelta

    from domains.forecast.ledger import active_as_of

    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        ForecastEngine(session).run(
            target="macro:gdp:USA", method="naive", horizon="short"
        )
        now = datetime.now(UTC)
        assert len(active_as_of(session, as_of=now)) == 1
        # بعد از target_date (۳۰ روز) دیگر فعال نیست
        later = now + timedelta(days=60)
        assert active_as_of(session, as_of=later) == []
    finally:
        session.close()


def test_ledger_api(client: TestClient) -> None:
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    r1 = client.post("/api/forecasts/run?target=macro:inflation:USA&method=naive")
    assert r1.status_code == 200
    fid1 = r1.json()["forecast_ids"][0]
    r2 = client.post("/api/forecasts/run?target=macro:inflation:USA&method=naive")
    assert r2.json()["superseded"] == 1

    # ابطال دستی
    sup = client.post(f"/api/forecasts/{r2.json()['forecast_ids'][0]}/supersede")
    assert sup.status_code == 200
    assert sup.json()["status"] == "superseded"

    # active خالی است (هر دو باطل شدند)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    act = client.get(f"/api/forecasts/ledger/active?as_of={now}")
    assert act.status_code == 200
    assert act.json() == []

    # رکورد اول هنوز در Ledger است (بدون حذف)
    one = client.get(f"/api/forecasts/{fid1}")
    assert one.status_code == 200
    assert one.json()["status"] == "superseded"

    # naive-aware رد می‌شود
    bad = client.get("/api/forecasts/ledger/active?as_of=2026-10-09T00:00:00")
    assert bad.status_code == 422

    missing = client.post(
        "/api/forecasts/00000000-0000-0000-0000-000000000000/supersede"
    )
    assert missing.status_code == 404

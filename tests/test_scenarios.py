"""Tests for Scenario Engine math, service & API (Phase 30)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast
from backend.database.models.market import MacroObservation
from domains.scenarios import analytics as an
from domains.scenarios.engine import ScenarioEngine
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


# --- pure tests ---
def test_series_sigma() -> None:
    assert an.series_sigma([1.0, 2.0]) is None
    assert an.series_sigma([5.0, 5.0, 5.0]) is None
    assert abs((an.series_sigma([1.0, 2.0, 3.0]) or 0.0) - 0.816497) < 1e-4


def test_build_scenarios_mapping() -> None:
    s = an.build_scenarios(10.0, 2.0)
    assert s is not None
    assert s.values == {"base": 10.0, "bull": 12.0, "bear": 8.0, "tail": 6.0}
    assert an.build_scenarios(10.0, None) is None


def test_confidence_discounts() -> None:
    assert an.CONFIDENCE_DISCOUNT["base"] == 1.0
    assert an.CONFIDENCE_DISCOUNT["tail"] == 0.7


# --- engine tests ---
def test_engine_builds_four_scenarios() -> None:
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        outcome = ScenarioEngine(session).run(target="macro:inflation:USA")
        assert outcome.created == 4
        assert set(outcome.scenarios) == {"base", "bull", "bear", "tail"}
        assert outcome.scenarios["bull"] > outcome.scenarios["base"]
        assert outcome.scenarios["tail"] < outcome.scenarios["bear"]
        rows = session.query(Forecast).all()
        assert {r.scenario for r in rows} == {"base", "bull", "bear", "tail"}
        assert all(r.status == "active" for r in rows)
    finally:
        session.close()


def test_scenario_interval_recentered_on_shifted_point() -> None:
    """AUDIT-REPAIR: بازه باید دور expected جدید باشد، نه کپی base."""
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        ScenarioEngine(session).run(target="macro:inflation:USA")
        rows = {r.scenario: r for r in session.query(Forecast).all()}
        base, bull = rows["base"], rows["bull"]
        assert base.interval_low is not None and base.interval_high is not None
        width = base.interval_high - base.interval_low
        assert abs((bull.interval_high - bull.interval_low) - width) < 1e-6
        mid = (bull.interval_low + bull.interval_high) / 2
        assert abs(mid - bull.expected_value) < 1e-6
        assert "recentered" in (bull.assumptions or "")
    finally:
        session.close()


def test_engine_no_sigma_only_base() -> None:
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])  # فقط ۲ نقطه
    session = TestingSession()
    try:
        outcome = ScenarioEngine(session).run(target="macro:gdp:USA")
        assert outcome.created == 1
        assert set(outcome.scenarios) == {"base"}
        assert outcome.skipped == 3
    finally:
        session.close()


def test_engine_bad_inputs() -> None:
    session = TestingSession()
    try:
        bad_target = ScenarioEngine(session).run(target="nope")
        assert bad_target.failed == 1
        bad_method = ScenarioEngine(session).run(
            target="macro:inflation:USA", method="arima"
        )
        assert bad_method.failed == 1
        empty = ScenarioEngine(session).run(target="macro:gdp:XXX")
        assert empty.skipped == 1
    finally:
        session.close()


def test_engine_rerun_supersedes() -> None:
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        ScenarioEngine(session).run(target="macro:inflation:USA")
        second = ScenarioEngine(session).run(target="macro:inflation:USA")
        assert second.created == 4
        assert second.superseded == 4
        assert session.query(Forecast).count() == 8
    finally:
        session.close()


# --- API tests ---
def test_scenarios_api(client: TestClient) -> None:
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    res = client.post("/api/scenarios/run?target=macro:inflation:USA")
    assert res.status_code == 200
    assert res.json()["created"] == 4

    lst = client.get("/api/scenarios?target=macro:inflation:USA")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert set(lst.json()[0]["scenarios"]) == {"base", "bull", "bear", "tail"}

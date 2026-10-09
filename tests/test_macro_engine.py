"""Tests for Macro Engine analytics, service & API (Phase 21)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.macro_assessment import MacroAssessment
from backend.database.models.market import MacroObservation
from domains.macro import analytics as an
from domains.macro.analysis import MacroEngine
from tests.conftest import TestingSession


def _seed_obs(indicator: str, country: str, rows: list[tuple[str, float]]) -> None:
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


# --- pure analytics tests ---
def test_yoy_mapping() -> None:
    assert an.yoy([103.0, 100.0]) == 0.03
    assert an.yoy([100.0]) is None
    assert an.yoy([None, 100.0]) is None
    assert an.yoy([]) is None


def test_acceleration_mapping() -> None:
    # yoy: 3٪ سپس 2٪ → شتاب ‎-1٪
    assert abs(an.acceleration([103.0, 100.0, 98.0]) - (0.03 - 0.020408)) < 1e-6
    assert an.acceleration([103.0, 100.0]) is None


def test_z_score_needs_history() -> None:
    assert an.z_score([1.0, 2.0]) is None
    assert an.z_score([5.0, 5.0, 5.0]) is None  # واریانس صفر → None
    z = an.z_score([10.0, 0.0, 0.0])
    assert z is not None and z > 1.0


def test_momentum_labels() -> None:
    assert an.momentum_label(1.5) == "accelerating"
    assert an.momentum_label(-1.5) == "decelerating"
    assert an.momentum_label(0.2) == "stable"
    assert an.momentum_label(None) == "unknown"


def test_confidence_by_n() -> None:
    assert an.confidence_for(1) == 0.1
    assert an.confidence_for(2) == 0.4
    assert an.confidence_for(4) == 0.6
    assert an.confidence_for(6) == 0.8


def test_analyze_series_empty() -> None:
    s = an.analyze_series([])
    assert s.n == 0 and s.momentum_label == "unknown" and s.confidence == 0.1


# --- engine tests ---
def test_engine_stores_assessment() -> None:
    _seed_obs("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        outcome = MacroEngine(session).analyze_all()
        assert outcome.series_analyzed == 1
        assert outcome.stored == 1
        a = session.query(MacroAssessment).one()
        assert a.indicator == "inflation" and a.country == "USA"
        assert a.period == "2024"
        assert a.latest_value == 2.95
        assert a.momentum_label in {"accelerating", "stable", "decelerating"}
        assert a.method == "series_stats_v1"
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_obs("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        first = MacroEngine(session).analyze_all()
        assert first.stored == 1
        second = MacroEngine(session).analyze_all()
        assert second.stored == 0
        assert second.duplicates == 1
        assert session.query(MacroAssessment).count() == 1
    finally:
        session.close()


def test_engine_filters() -> None:
    _seed_obs("inflation", "USA", [("2023", 4.0), ("2024", 3.0)])
    _seed_obs("gdp", "IRN", [("2023", 100.0), ("2024", 110.0)])
    session = TestingSession()
    try:
        outcome = MacroEngine(session).analyze_all(country="IRN")
        assert outcome.series_analyzed == 1
        assert session.query(MacroAssessment).one().country == "IRN"
    finally:
        session.close()


# --- API tests ---
def test_macro_api_analyze_assessments_overview(client: TestClient) -> None:
    _seed_obs("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    res = client.post("/api/macro/analyze")
    assert res.status_code == 200
    assert res.json()["stored"] == 1

    lst = client.get("/api/macro/assessments?country=USA")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["momentum_label"] in {
        "accelerating", "stable", "decelerating", "unknown",
    }

    ov = client.get("/api/macro/overview?country=USA")
    assert ov.status_code == 200
    assert len(ov.json()) == 1

    ov_empty = client.get("/api/macro/overview?country=XXX")
    assert ov_empty.status_code == 200
    assert ov_empty.json() == []

"""Tests for Model Performance engine & API (Phase 36)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.model_performance import ModelPerformance
from domains.forecast.performance import PerformanceEngine
from tests.conftest import TestingSession


def _seed_scored(model: str, expected: float, actual: float) -> None:
    session = TestingSession()
    try:
        fc = Forecast(
            valid_from=datetime(2023, 1, 1, tzinfo=UTC),
            target_date=datetime(2023, 6, 1, tzinfo=UTC),
            horizon="short",
            target="macro:inflation:USA",
            expected_value=expected,
            probability=None,
            model=model,
            model_version="v1",
            scenario="base",
            status="resolved",
        )
        session.add(fc)
        session.flush()
        oc = ForecastOutcome(forecast_id=fc.id, actual_value=actual)
        oc.abs_error = abs(expected - actual)
        oc.squared_error = (expected - actual) ** 2
        session.add(oc)
        session.commit()
    finally:
        session.close()


# --- engine tests ---
def test_engine_records_per_model() -> None:
    _seed_scored("baseline_naive", 3.0, 2.95)
    _seed_scored("baseline_historical_mean", 5.0, 2.95)
    session = TestingSession()
    try:
        outcome = PerformanceEngine(session).record(period="2026-10")
        assert outcome.models_recorded == 2
        assert outcome.stored == 2
        rows = {r.model: r for r in session.query(ModelPerformance).all()}
        assert rows["baseline_naive"].mae == 0.05
        assert rows["baseline_historical_mean"].mae == 2.05
    finally:
        session.close()


def test_engine_skips_model_without_scores() -> None:
    session = TestingSession()
    try:
        session.add(
            Forecast(
                target="market:WTI",
                expected_value=90.0,
                model="baseline_naive",
                model_version="v1",
                scenario="base",
                status="active",
            )
        )
        session.commit()
        outcome = PerformanceEngine(session).record(period="2026-10")
        assert outcome.skipped == 1
        assert outcome.stored == 0
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_scored("baseline_naive", 3.0, 2.95)
    session = TestingSession()
    try:
        assert PerformanceEngine(session).record(period="2026-10").stored == 1
        second = PerformanceEngine(session).record(period="2026-10")
        assert second.stored == 0 and second.duplicates == 1
    finally:
        session.close()


# --- API tests ---
def test_performance_api(client: TestClient) -> None:
    _seed_scored("baseline_naive", 3.0, 2.95)
    _seed_scored("baseline_historical_mean", 5.0, 2.95)
    res = client.post("/api/performance/record?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] == 2

    board = client.get("/api/performance")
    assert board.status_code == 200
    assert len(board.json()) == 2
    assert board.json()[0]["model"] == "baseline_naive"  # MAE کمتر اول

    hist = client.get("/api/performance/history?model=baseline_naive")
    assert hist.status_code == 200
    assert len(hist.json()) == 1

    empty = client.get("/api/performance/history?model=nope")
    assert empty.json() == []

"""Tests for Long-Term Learning learners, engine & API (Phase 51)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.learning_insight import LearningInsight
from backend.database.models.model_performance import ModelPerformance
from backend.database.models.world_state import WorldState
from domains.learning import learners as ln
from domains.learning.engine import LearningEngine
from tests.conftest import TestingSession


def _seed_perf(model: str, maes: list[float]) -> None:
    session = TestingSession()
    try:
        for i, mae in enumerate(maes):
            session.add(
                ModelPerformance(
                    model=model,
                    period=f"2026-0{i + 1}",
                    n_scored=2,
                    mae=mae,
                    method="performance_v1",
                    observed_at=datetime.now(UTC),
                )
            )
        session.commit()
    finally:
        session.close()


def _seed_states(regimes: list[str]) -> None:
    session = TestingSession()
    try:
        for i, regime in enumerate(regimes):
            session.add(
                WorldState(
                    captured_at=datetime(2026, 1, 1 + i, tzinfo=UTC),
                    granularity="daily",
                    macro_regime=regime,
                    market_regime="neutral",
                    energy_risk=0.1 * (i + 1),
                    confidence=0.5,
                )
            )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_accuracy_trend() -> None:
    assert ln.accuracy_trend([3.0, 2.0]) is None  # کمبود نقطه
    down = ln.accuracy_trend([3.0, 2.0, 1.0])
    assert down is not None and down.direction == "improving"
    up = ln.accuracy_trend([1.0, 2.0, 3.0])
    assert up is not None and up.direction == "degrading"
    flat = ln.accuracy_trend([2.0, 2.0, 2.0])
    assert flat is not None and flat.direction == "stable"


def test_base_rates() -> None:
    assert ln.base_rates([]) is None
    assert ln.base_rates([None, None]) is None
    rates = ln.base_rates(["a", "a", "b", None])
    assert rates is not None
    assert abs(rates["a"] - 0.6667) < 1e-4
    assert abs(sum(rates.values()) - 1.0) < 1e-4


def test_threshold_p90() -> None:
    assert ln.threshold_p90([1.0, 2.0]) is None
    assert ln.threshold_p90([1.0, 2.0, 3.0, 4.0, 5.0]) == 4.6


def test_least_squares_slope() -> None:
    assert ln.least_squares_slope([0.0], [1.0]) is None
    assert ln.least_squares_slope([1.0, 1.0], [1.0, 2.0]) is None
    assert ln.least_squares_slope([0.0, 1.0, 2.0], [0.0, 2.0, 4.0]) == 2.0


# --- engine tests ---
def test_engine_learns_all_kinds() -> None:
    _seed_perf("baseline_naive", [3.0, 2.0, 1.0])
    _seed_states(["expansion", "expansion", "slowdown", "slowdown", "slowdown"])
    session = TestingSession()
    try:
        LearningEngine(session).run(period="2026-10")
        kinds = {
            r.kind
            for r in session.query(LearningInsight).all()
        }
        assert {"accuracy_trend", "regime_base_rate", "threshold_p90"} <= kinds
        trend = (
            session.query(LearningInsight)
            .filter_by(kind="accuracy_trend", subject="baseline_naive")
            .one()
        )
        assert json.loads(trend.value or "{}")["direction"] == "improving"
    finally:
        session.close()


def test_engine_skips_thin_history() -> None:
    _seed_perf("baseline_naive", [3.0, 2.0])  # فقط ۲ نقطه
    session = TestingSession()
    try:
        outcome = LearningEngine(session).run(period="2026-10")
        assert outcome.insights_built == 0
        assert session.query(LearningInsight).count() == 0
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_perf("baseline_naive", [3.0, 2.0, 1.0])
    session = TestingSession()
    try:
        assert LearningEngine(session).run(period="2026-10").stored == 1
        second = LearningEngine(session).run(period="2026-10")
        assert second.stored == 0 and second.duplicates == 1
    finally:
        session.close()


# --- API tests ---
def test_learning_api(client: TestClient) -> None:
    _seed_perf("baseline_naive", [3.0, 2.0, 1.0])
    res = client.post("/api/learning/run?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] == 1

    lst = client.get("/api/learning/insights?kind=accuracy_trend")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["value"]["direction"] == "improving"

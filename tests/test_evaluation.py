"""Tests for Forecast Evaluation metrics, engine & API (Phase 28)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast, ForecastOutcome
from domains.forecast import metrics as m
from domains.forecast.evaluation import EvaluationEngine
from tests.conftest import TestingSession


def _seed_resolved(
    target: str = "macro:inflation:USA",
    expected: float = 5.0,
    actual: float = 2.95,
    probability: float | None = None,
    actual_bool: str | None = None,
    model: str = "baseline_naive",
) -> str:
    session = TestingSession()
    try:
        fc = Forecast(
            valid_from=datetime(2023, 1, 1, tzinfo=UTC),
            target_date=datetime(2023, 6, 1, tzinfo=UTC),
            horizon="short",
            target=target,
            expected_value=expected,
            probability=probability,
            model=model,
            model_version="v1",
            scenario="base",
            status="resolved",
        )
        session.add(fc)
        session.flush()
        session.add(
            ForecastOutcome(
                forecast_id=fc.id,
                actual_value=actual,
                actual_bool=actual_bool,
                resolved_at=datetime.now(UTC),
            )
        )
        session.commit()
        return str(fc.id)
    finally:
        session.close()


# --- pure tests ---
def test_value_scores() -> None:
    s = m.value_scores(5.0, 2.95)
    assert s.abs_error == 2.05
    assert abs(s.squared_error - 4.2025) < 1e-6


def test_prob_scores() -> None:
    s = m.prob_scores(0.8, True)
    assert s.brier_score == 0.04
    assert abs(s.log_loss - 0.223144) < 1e-4
    # clip حدی: احتمال ۱ با نتیجه‌ی مخالف نباید inf شود
    s2 = m.prob_scores(1.0, False)
    assert s2.log_loss < 20.0


def test_parse_bool() -> None:
    assert m.parse_bool("true") is True
    assert m.parse_bool("FALSE") is False
    assert m.parse_bool("maybe") is None
    assert m.parse_bool(None) is None


def test_aggregate_empty() -> None:
    agg = m.aggregate([], [], [], [], [])
    assert agg.n == 0 and agg.mae is None and agg.calibration == []


def test_calibrate_bins() -> None:
    pairs = [(0.9, True), (0.8, True), (0.1, False), (0.2, False)]
    cal = m.calibrate(pairs, n_bins=10)
    assert len(cal) == 4
    hi = [b for b in cal if b["bin"].startswith("0.9")][0]
    assert hi["observed_freq"] == 1.0 and hi["n"] == 1


# --- engine tests ---
def test_engine_scores_value_outcome() -> None:
    _seed_resolved(expected=5.0, actual=2.95)
    session = TestingSession()
    try:
        outcome = EvaluationEngine(session).run()
        assert outcome.scored == 1
        oc = session.query(ForecastOutcome).one()
        assert oc.abs_error == 2.05
        assert oc.brier_score is None  # بدون probability
    finally:
        session.close()


def test_engine_scores_probability_outcome() -> None:
    _seed_resolved(expected=1.0, actual=1.0, probability=0.8, actual_bool="true")
    session = TestingSession()
    try:
        EvaluationEngine(session).run()
        oc = session.query(ForecastOutcome).one()
        assert oc.brier_score == 0.04
        assert oc.log_loss is not None
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_resolved()
    session = TestingSession()
    try:
        assert EvaluationEngine(session).run().scored == 1
        assert EvaluationEngine(session).run().scored == 1
        assert session.query(ForecastOutcome).count() == 1
    finally:
        session.close()


def test_engine_summary() -> None:
    _seed_resolved(model="baseline_naive", expected=5.0, actual=3.0)
    _seed_resolved(model="baseline_naive", expected=4.0, actual=3.0)
    session = TestingSession()
    try:
        s = EvaluationEngine(session).summary(model="baseline_naive")
        assert s["n"] == 2
        assert s["mae"] == 1.5
        assert abs(s["rmse"] - 1.581139) < 1e-4
        assert s["mean_brier"] is None
    finally:
        session.close()


# --- API tests ---
def test_evaluation_api(client: TestClient) -> None:
    _seed_resolved(expected=5.0, actual=2.95)
    res = client.post("/api/evaluation/run")
    assert res.status_code == 200
    assert res.json()["scored"] == 1

    scores = client.get("/api/evaluation/scores")
    assert scores.status_code == 200
    assert len(scores.json()) == 1
    assert scores.json()[0]["abs_error"] == 2.05

    summ = client.get("/api/evaluation/summary")
    assert summ.status_code == 200
    assert summ.json()["n"] == 1
    assert summ.json()["mae"] == 2.05

    empty = client.get("/api/evaluation/summary?model=nope")
    assert empty.json()["n"] == 0

"""Tests for Forecast Tournament engine & API (Phase 29)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.market import MacroObservation
from backend.database.models.tournament import Tournament
from domains.forecast.tournament import TournamentEngine, rank_key
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


def _seed_resolved(
    target: str, model: str, expected: float, actual: float
) -> None:
    """پیش‌بینی گذشته‌ی حل‌شده (برای امتیاز تورنمنت)."""
    session = TestingSession()
    try:
        fc = Forecast(
            valid_from=datetime(2023, 1, 1, tzinfo=UTC),
            target_date=datetime(2023, 6, 1, tzinfo=UTC),
            horizon="short",
            target=target,
            expected_value=expected,
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
                resolved_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_rank_key_prefers_mae() -> None:
    rows = [
        {"model": "b", "mae": None, "mean_brier": 0.1, "n_scored": 5},
        {"model": "a", "mae": 1.0, "mean_brier": None, "n_scored": 1},
        {"model": "c", "mae": None, "mean_brier": None, "n_scored": 9},
    ]
    assert [r["model"] for r in sorted(rows, key=rank_key)] == ["a", "b", "c"]


def test_rank_key_tiebreak_count() -> None:
    rows = [
        {"model": "a", "mae": 1.0, "mean_brier": None, "n_scored": 1},
        {"model": "b", "mae": 1.0, "mean_brier": None, "n_scored": 4},
    ]
    assert [r["model"] for r in sorted(rows, key=rank_key)] == ["b", "a"]


# --- engine tests ---
def test_tournament_picks_winner() -> None:
    target = "macro:inflation:USA"
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    _seed_resolved(target, "baseline_naive", expected=3.0, actual=2.95)  # خطا 0.05
    _seed_resolved(target, "baseline_historical_mean", expected=5.0, actual=2.95)
    session = TestingSession()
    try:
        out = TournamentEngine(session).run(
            targets=[target],
            methods=["naive", "historical_mean"],
            name="t1",
        )
        assert out.winner_model == "baseline_naive"
        assert out.board[0]["model"] == "baseline_naive"
        assert out.n_forecasts == 2  # پیش‌بینی‌های جدید آینده‌دار
        rec = session.query(Tournament).one()
        assert rec.winner_model == "baseline_naive"
    finally:
        session.close()


def test_tournament_no_scores_no_winner() -> None:
    session = TestingSession()
    try:
        out = TournamentEngine(session).run(
            targets=["macro:gdp:XXX"], methods=["naive"], name="t-empty"
        )
        assert out.winner_model is None
        assert out.board[0]["mae"] is None
        assert out.n_forecasts == 0
    finally:
        session.close()


def test_tournament_empty_targets_rejected() -> None:
    session = TestingSession()
    try:
        out = TournamentEngine(session).run(targets=[], methods=["naive"])
        assert out.board[0]["n_scored"] == 0
    finally:
        session.close()


# --- API tests ---
def test_tournaments_api(client: TestClient) -> None:
    target = "macro:inflation:USA"
    _seed_macro("inflation", "USA", [("2022", 8.0), ("2023", 4.12), ("2024", 2.95)])
    _seed_resolved(target, "baseline_naive", expected=3.0, actual=2.95)
    res = client.post(
        "/api/tournaments/run",
        json={"targets": [target], "methods": ["naive"], "name": "api-t"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["winner_model"] == "baseline_naive"

    lst = client.get("/api/tournaments")
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    one = client.get(f"/api/tournaments/{body['tournament_id']}")
    assert one.status_code == 200
    assert one.json()["name"] == "api-t"

    assert (
        client.get("/api/tournaments/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )
    assert client.post("/api/tournaments/run", json={"targets": []}).status_code == 422

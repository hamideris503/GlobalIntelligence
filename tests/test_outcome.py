"""Tests for Outcome Engine (Phase 27)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.market import MacroObservation, MarketObservation
from domains.forecast.outcome import OutcomeEngine, period_start
from tests.conftest import TestingSession


def _seed_forecast(
    target: str, target_date: datetime, expected: float = 1.0
) -> str:
    session = TestingSession()
    try:
        fc = Forecast(
            valid_from=target_date - timedelta(days=30),
            target_date=target_date,
            horizon="short",
            target=target,
            expected_value=expected,
            model="baseline_naive",
            model_version="v1",
            scenario="base",
            status="active",
        )
        session.add(fc)
        session.commit()
        return str(fc.id)
    finally:
        session.close()


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
def test_period_start_mapping() -> None:
    assert period_start("2024") == datetime(2024, 1, 1, tzinfo=UTC)
    assert period_start("2026-Q1") == datetime(2026, 1, 1, tzinfo=UTC)
    assert period_start("2026-Q4") == datetime(2026, 10, 1, tzinfo=UTC)
    assert period_start("2026-07") == datetime(2026, 7, 1, tzinfo=UTC)
    assert period_start("junk") is None
    assert period_start(None) is None
    assert period_start("2026-13") is None
    assert period_start("2026-Q5") is None


# --- engine tests ---
def test_resolve_macro_outcome() -> None:
    _seed_macro("inflation", "USA", [("2023", 4.12), ("2024", 2.95)])
    fid = _seed_forecast(
        "macro:inflation:USA", datetime(2023, 6, 1, tzinfo=UTC), expected=5.0
    )
    session = TestingSession()
    try:
        outcome = OutcomeEngine(session).resolve_all()
        assert outcome.resolved == 1
        oc = session.query(ForecastOutcome).one()
        # دوره‌ی 2023 کل سال را پوشش می‌دهد و بعد از ژوئن شناخته می‌شود
        # (look-ahead نیست) → اولین دوره‌ی ≥ target یعنی 2024
        assert oc.actual_value == 2.95
        assert session.get(Forecast, UUID(fid)).status == "resolved"
    finally:
        session.close()


def test_future_forecast_untouched() -> None:
    _seed_macro("inflation", "USA", [("2024", 2.95)])
    _seed_forecast(
        "macro:inflation:USA", datetime.now(UTC) + timedelta(days=30)
    )
    session = TestingSession()
    try:
        outcome = OutcomeEngine(session).resolve_all()
        assert outcome.resolved == 0
        assert session.query(ForecastOutcome).count() == 0
    finally:
        session.close()


def test_no_actual_skips() -> None:
    _seed_forecast(
        "macro:gdp:XXX", datetime(2020, 1, 1, tzinfo=UTC)
    )
    session = TestingSession()
    try:
        outcome = OutcomeEngine(session).resolve_all()
        assert outcome.skipped == 1
        assert outcome.resolved == 0
    finally:
        session.close()


def test_resolve_is_idempotent() -> None:
    _seed_macro("inflation", "USA", [("2024", 2.95)])
    _seed_forecast("macro:inflation:USA", datetime(2023, 1, 1, tzinfo=UTC))
    session = TestingSession()
    try:
        assert OutcomeEngine(session).resolve_all().resolved == 1
        second = OutcomeEngine(session).resolve_all()
        assert second.resolved == 0 and second.skipped == 0
        assert session.query(ForecastOutcome).count() == 1
    finally:
        session.close()


def test_resolve_market_outcome() -> None:
    session = TestingSession()
    try:
        base = datetime(2026, 1, 10, tzinfo=UTC)
        session.add(
            MarketObservation(
                symbol="WTI",
                asset_class="energy",
                value=91.0,
                source_name="test",
                observed_at=base,
            )
        )
        session.commit()
    finally:
        session.close()
    _seed_forecast("market:WTI", datetime(2026, 1, 1, tzinfo=UTC), expected=80.0)
    session = TestingSession()
    try:
        outcome = OutcomeEngine(session).resolve_all(target="market:WTI")
        assert outcome.resolved == 1
        assert session.query(ForecastOutcome).one().actual_value == 91.0
    finally:
        session.close()


def test_pending_lists_only_unresolved() -> None:
    _seed_macro("inflation", "USA", [("2024", 2.95)])
    _seed_forecast("macro:inflation:USA", datetime(2023, 1, 1, tzinfo=UTC))
    session = TestingSession()
    try:
        assert len(OutcomeEngine(session).pending()) == 1
        OutcomeEngine(session).resolve_all()
        assert OutcomeEngine(session).pending() == []
    finally:
        session.close()


# --- API tests ---
def test_outcomes_api(client: TestClient) -> None:
    _seed_macro("inflation", "USA", [("2024", 2.95)])
    _seed_forecast("macro:inflation:USA", datetime(2023, 1, 1, tzinfo=UTC))

    pend = client.get("/api/outcomes/pending")
    assert pend.status_code == 200
    assert len(pend.json()) == 1

    res = client.post("/api/outcomes/resolve")
    assert res.status_code == 200
    assert res.json()["resolved"] == 1

    lst = client.get("/api/outcomes?target=macro:inflation:USA")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["actual_value"] == 2.95

    assert client.get("/api/outcomes/pending").json() == []

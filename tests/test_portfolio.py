"""Tests for Portfolio analytics, engine & API (Phase 35)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast
from backend.database.models.portfolio import Portfolio, PortfolioSnapshot
from domains.portfolio import analytics as an
from domains.portfolio.engine import PortfolioEngine
from tests.conftest import TestingSession


def _seed_scenarios(target: str, base: float, bull: float, bear: float) -> None:
    session = TestingSession()
    try:
        for name, value in [("base", base), ("bull", bull), ("bear", bear)]:
            session.add(
                Forecast(
                    valid_from=datetime.now(UTC),
                    target_date=datetime(2027, 1, 1, tzinfo=UTC),
                    horizon="short",
                    target=target,
                    expected_value=value,
                    model="baseline_naive",
                    model_version="v1",
                    scenario=name,
                    status="active",
                )
            )
        session.commit()
    finally:
        session.close()


def _seed_portfolio(name: str, positions: dict) -> str:
    import json

    session = TestingSession()
    try:
        p = Portfolio(name=name, positions=json.dumps(positions))
        session.add(p)
        session.commit()
        return str(p.id)
    finally:
        session.close()


# --- pure tests ---
def test_normalize_weights() -> None:
    assert an.normalize_weights({"a": 2.0, "b": 2.0}) == {"a": 0.5, "b": 0.5}
    try:
        an.normalize_weights({})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
    try:
        an.normalize_weights({"a": 0.0})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_spread_of() -> None:
    assert an.spread_of(100.0, 110.0, 90.0) == 0.2
    assert an.spread_of(0.0, 1.0, -1.0) is None
    assert an.spread_of(None, 1.0, 2.0) is None


def test_analyze_positions() -> None:
    stats = an.analyze_positions(
        {"a": 0.5, "b": 0.5},
        {"a": {"base": 10.0, "bull": 12.0, "bear": 8.0}},
    )
    assert stats is not None
    assert stats.expected_return == 10.0  # نرمال‌شده بر پوشش (۰.۵×۱۰/۰.۵)
    assert stats.coverage == 0.5
    assert stats.concentration == 0.5
    assert stats.diversification == 0.5
    assert an.analyze_positions({"a": 1.0}, {}) is None


# --- engine tests ---
def test_engine_snapshot() -> None:
    _seed_scenarios("market:WTI", 90.0, 100.0, 85.0)
    pid = _seed_portfolio("p1", {"market:WTI": 1.0})
    session = TestingSession()
    try:
        outcome = PortfolioEngine(session).snapshot(portfolio_id=pid, period="2026-10")
        assert outcome.stored == 1
        snap = session.query(PortfolioSnapshot).one()
        assert snap.expected_return == 90.0
        assert snap.coverage == 1.0
        assert snap.concentration == 1.0  # تک‌موقعیتی
    finally:
        session.close()


def test_engine_skips_uncovered() -> None:
    pid = _seed_portfolio("p2", {"market:XXX": 1.0})
    session = TestingSession()
    try:
        outcome = PortfolioEngine(session).snapshot(portfolio_id=pid, period="2026-10")
        assert outcome.skipped == 1
        assert outcome.stored == 0
    finally:
        session.close()


def test_engine_missing_portfolio() -> None:
    session = TestingSession()
    try:
        outcome = PortfolioEngine(session).snapshot(
            portfolio_id="00000000-0000-0000-0000-000000000000"
        )
        assert outcome.failed == 1
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_scenarios("market:WTI", 90.0, 100.0, 85.0)
    pid = _seed_portfolio("p3", {"market:WTI": 1.0})
    session = TestingSession()
    try:
        assert PortfolioEngine(session).snapshot(portfolio_id=pid).stored == 1
        second = PortfolioEngine(session).snapshot(portfolio_id=pid)
        assert second.stored == 0 and second.duplicates == 1
    finally:
        session.close()


# --- API tests ---
def test_portfolios_api(client: TestClient) -> None:
    _seed_scenarios("market:WTI", 90.0, 100.0, 85.0)
    res = client.post(
        "/api/portfolios",
        json={"positions": {"market:WTI": 2.0}, "name": "api-p"},
    )
    assert res.status_code == 200
    pid = res.json()["id"]

    dup = client.post(
        "/api/portfolios",
        json={"positions": {"market:WTI": 1.0}, "name": "api-p"},
    )
    assert dup.status_code == 409

    snap = client.post(f"/api/portfolios/{pid}/snapshot?period=2026-10")
    assert snap.status_code == 200
    assert snap.json()["stored"] == 1

    lst = client.get(f"/api/portfolios/{pid}/snapshots")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["expected_return"] == 90.0

    assert client.get("/api/portfolios").status_code == 200

    delete = client.delete(f"/api/portfolios/{pid}")
    assert delete.status_code == 200
    assert delete.json() == {"deleted": True}
    assert client.get(f"/api/portfolios/{pid}").status_code == 404

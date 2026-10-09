"""Tests for Daily briefing service & API (Phase 41)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.briefing import Briefing
from backend.database.models.event import Event
from backend.database.models.market import MarketObservation
from domains.briefings.daily import DailyBriefingService
from tests.conftest import TestingSession


def _seed_event(days_ago: float = 0.0) -> str:
    session = TestingSession()
    try:
        e = Event(event_type="market", action="rally")
        session.add(e)
        session.commit()
        return str(e.id)
    finally:
        session.close()


def _seed_market(symbol: str, values: list[tuple[float, float]]) -> None:
    session = TestingSession()
    try:
        now = datetime.now(UTC)
        for value, days_ago in values:
            session.add(
                MarketObservation(
                    symbol=symbol,
                    asset_class="test",
                    value=value,
                    source_name="test",
                    observed_at=now - timedelta(days=days_ago),
                )
            )
        session.commit()
    finally:
        session.close()


# --- service tests ---
def test_build_collects_sections() -> None:
    _seed_event()
    _seed_market("WTI", [(91.0, 0.0), (90.0, 1.0)])
    _seed_market("GOLD", [(100.0, 0.0)])  # تک‌نقطه → نادیده
    session = TestingSession()
    try:
        outcome = DailyBriefingService(session).build()
        assert outcome.stored == 1
        assert outcome.sections["events"] == 1
        assert outcome.sections["movers"] == 1
        rec = session.query(Briefing).one()
        assert rec.kind == "daily"
    finally:
        session.close()


def test_build_is_idempotent() -> None:
    session = TestingSession()
    try:
        first = DailyBriefingService(session).build(day="2026-10-01")
        assert first.stored == 1
        second = DailyBriefingService(session).build(day="2026-10-01")
        assert second.stored == 0 and second.duplicates == 1
        assert session.query(Briefing).count() == 1
    finally:
        session.close()


def test_movers_ranking() -> None:
    _seed_market("A", [(110.0, 0.0), (100.0, 1.0)])  # ‎+10٪
    _seed_market("B", [(101.0, 0.0), (100.0, 1.0)])  # ‎+1٪
    session = TestingSession()
    try:
        DailyBriefingService(session).build(day="2026-10-02")
        rec = session.query(Briefing).filter_by(period="2026-10-02").one()
        import json

        content = json.loads(rec.content or "{}")
        assert content["movers"][0]["symbol"] == "A"
        assert content["movers"][0]["change_pct"] == 10.0
    finally:
        session.close()


def test_empty_window_builds_anyway() -> None:
    session = TestingSession()
    try:
        outcome = DailyBriefingService(session).build(
            day="2020-01-01", window_hours=1
        )
        assert outcome.stored == 1
        assert outcome.sections["events"] == 0
    finally:
        session.close()


# --- API tests ---
def test_briefings_api(client: TestClient) -> None:
    _seed_event()
    res = client.post("/api/briefings/daily")
    assert res.status_code == 200
    assert res.json()["stored"] == 1
    bid = res.json()["briefing_id"]

    lst = client.get("/api/briefings?kind=daily")
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    one = client.get(f"/api/briefings/{bid}")
    assert one.status_code == 200
    assert "events" in one.json()["content"]

    assert (
        client.get("/api/briefings/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )

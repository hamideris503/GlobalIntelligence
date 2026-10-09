"""Tests for Weekly briefing service & API (Phase 42)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.briefing import Briefing
from backend.database.models.event import Event
from backend.database.models.market import MarketObservation
from backend.database.models.risk_assessment import RiskAssessment
from domains.briefings.weekly import WeeklyBriefingService
from tests.conftest import TestingSession


def _seed_event() -> str:
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


def _seed_risks() -> None:
    session = TestingSession()
    try:
        for period, score in [("2026-09", 0.3), ("2026-10", 0.5)]:
            session.add(
                RiskAssessment(
                    category="energy_risk",
                    period=period,
                    score=score,
                    level="medium",
                    method="risk_v1",
                    confidence=0.6,
                    observed_at=datetime.now(UTC),
                )
            )
        session.commit()
    finally:
        session.close()


# --- service tests ---
def test_weekly_collects_sections() -> None:
    _seed_event()
    _seed_market("WTI", [(100.0, 0.0), (90.0, 3.0)])
    _seed_risks()
    session = TestingSession()
    try:
        outcome = WeeklyBriefingService(session).build()
        assert outcome.stored == 1
        assert outcome.period.startswith("20")
        assert outcome.sections["trend_days"] == 7
        assert outcome.sections["movers"] == 1
        rec = session.query(Briefing).filter_by(kind="weekly").one()
        content = json.loads(rec.content or "{}")
        assert content["movers"][0]["symbol"] == "WTI"
        assert abs(content["movers"][0]["change_pct"] - 11.11) < 0.01
        assert content["risk_deltas"][0]["delta"] == 0.2
        assert sum(d["events"] for d in content["trend"]) >= 1
    finally:
        session.close()


def test_weekly_is_idempotent() -> None:
    session = TestingSession()
    try:
        first = WeeklyBriefingService(session).build()
        assert first.stored == 1
        second = WeeklyBriefingService(session).build()
        assert second.stored == 0 and second.duplicates == 1
        assert session.query(Briefing).filter_by(kind="weekly").count() == 1
    finally:
        session.close()


def test_weekly_empty_db() -> None:
    session = TestingSession()
    try:
        outcome = WeeklyBriefingService(session).build()
        assert outcome.stored == 1
        assert outcome.sections["movers"] == 0
    finally:
        session.close()


# --- API tests ---
def test_weekly_api(client: TestClient) -> None:
    _seed_event()
    res = client.post("/api/briefings/weekly")
    assert res.status_code == 200
    assert res.json()["stored"] == 1

    lst = client.get("/api/briefings?kind=weekly")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert "trend" in lst.json()[0]["content"]

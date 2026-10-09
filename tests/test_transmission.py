"""Tests for Iran Transmission analytics, service & API (Phase 34)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.market import MarketObservation
from backend.database.models.transmission_assessment import TransmissionAssessment
from backend.database.models.world_state import WorldState
from domains.iran import transmission_analytics as an
from domains.iran.transmission import TransmissionEngine
from tests.conftest import TestingSession


def _seed_market(symbol: str, value: float, days_ago: float = 0.0) -> None:
    session = TestingSession()
    try:
        session.add(
            MarketObservation(
                symbol=symbol,
                asset_class="test",
                value=value,
                source_name="test",
                observed_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_snapshot_geo(value: float, method: str = "dispute_surprise_mix") -> None:
    session = TestingSession()
    try:
        meta = {
            "geopolitical_risk": {
                "value": value, "method": method, "confidence": 0.6
            }
        }
        session.add(
            WorldState(
                captured_at=datetime.now(UTC),
                granularity="daily",
                geopolitical_risk=value,
                value_metadata=json.dumps(meta),
                confidence=0.5,
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_iran_tension(tension: float) -> None:
    session = TestingSession()
    try:
        session.add(
            GeopoliticalAssessment(
                actor="Iran",
                period="2026-10",
                tension=tension,
                confidence=0.7,
                observed_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_exposures_documented() -> None:
    assert an.EXPOSURES == {
        "energy": 0.9, "rates": 0.6, "geopolitical": 0.8, "market": 0.5,
    }


def test_transmit_mapping() -> None:
    t = an.transmit("energy", 0.5, "test")
    assert t is not None
    assert t.impact == 0.45
    assert t.exposure == 0.9
    assert an.transmit("energy", None, "test") is None
    assert an.transmit("unknown", 0.5, "test") is None


# --- engine tests ---
def test_engine_all_channels() -> None:
    _seed_market("WTI", 100.0)
    _seed_market("BRENT", 100.0)
    _seed_market("US10Y", 5.0)
    _seed_market("SPX", 5000.0, days_ago=100.0)
    _seed_market("SPX", 4500.0, days_ago=0.0)
    _seed_snapshot_geo(0.4)
    session = TestingSession()
    try:
        outcome = TransmissionEngine(session).analyze_all(period="2026-10")
        assert outcome.channels_analyzed == 4
        assert outcome.stored == 4
        rows = {r.channel: r for r in session.query(TransmissionAssessment).all()}
        assert abs(rows["energy"].impact - 0.5 * 0.9) < 1e-6
        assert abs(rows["rates"].impact - 0.5 * 0.6) < 1e-6
        assert rows["geopolitical"].impact == round(0.4 * 0.8, 4)
        assert abs(rows["market"].impact - 0.1 * 0.5) < 1e-6
    finally:
        session.close()


def test_engine_prefers_iran_tension() -> None:
    _seed_snapshot_geo(0.2)
    _seed_iran_tension(0.9)
    session = TestingSession()
    try:
        TransmissionEngine(session).analyze_all(period="2026-10")
        row = (
            session.query(TransmissionAssessment)
            .filter_by(channel="geopolitical")
            .one()
        )
        assert row.impact == round(0.9 * 0.8, 4)
    finally:
        session.close()


def test_engine_skips_without_inputs() -> None:
    session = TestingSession()
    try:
        outcome = TransmissionEngine(session).analyze_all(period="2026-10")
        assert outcome.channels_analyzed == 0
        assert outcome.skipped == 4
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_market("WTI", 100.0)
    session = TestingSession()
    try:
        first = TransmissionEngine(session).analyze_all(period="2026-10")
        assert first.stored == 1
        second = TransmissionEngine(session).analyze_all(period="2026-10")
        assert second.stored == 0
        assert second.duplicates == 1
    finally:
        session.close()


# --- API tests ---
def test_transmission_api(client: TestClient) -> None:
    _seed_market("WTI", 100.0)
    res = client.post("/api/iran/transmission/analyze?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] == 1

    lst = client.get("/api/iran/transmission?period=2026-10")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["channel"] == "energy"

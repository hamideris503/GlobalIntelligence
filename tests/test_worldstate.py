"""Tests for World State builder & API (Phase 18)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.event import Event
from backend.database.models.market import MacroObservation, MarketObservation
from backend.database.models.world_state import WorldState
from domains.worldstate import signals as sig
from domains.worldstate.builder import WorldStateBuilder
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


def _seed_market(symbol: str, asset_class: str, value: float) -> None:
    session = TestingSession()
    try:
        session.add(
            MarketObservation(
                symbol=symbol,
                asset_class=asset_class,
                value=value,
                source_name="test",
                observed_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_event(event_type: str = "conflict", surprise: float = 0.8) -> None:
    session = TestingSession()
    try:
        session.add(Event(event_type=event_type, action="test", surprise=surprise))
        session.commit()
    finally:
        session.close()


# --- pure signal tests ---
def test_growth_pressure_mapping() -> None:
    assert sig.growth_pressure(0.05).value == 1.0
    assert sig.growth_pressure(-0.05).value == 0.0
    assert sig.growth_pressure(0.0).value == 0.5
    assert sig.growth_pressure(None).method == "no_data"


def test_inflation_pressure_mapping() -> None:
    assert sig.inflation_pressure(10.0).value == 1.0
    assert sig.inflation_pressure(0.0).value == 0.0
    assert abs(sig.inflation_pressure(2.95).value - 0.295) < 1e-9


def test_energy_risk_mapping() -> None:
    assert sig.energy_risk(50.0, 50.0).value == 0.0
    assert sig.energy_risk(150.0, 150.0).value == 1.0
    assert sig.energy_risk(None, None).method == "no_data"
    assert sig.energy_risk(100.0, None).confidence == 0.5


def test_regimes() -> None:
    assert sig.macro_regime(0.8, 0.8) == "overheating"
    assert sig.macro_regime(0.8, 0.2) == "expansion"
    assert sig.macro_regime(0.2, 0.8) == "stagflation"
    assert sig.macro_regime(0.2, 0.2) == "slowdown"
    assert sig.market_regime(0.8, 0.5) == "stress"
    assert sig.market_regime(0.2, 0.8) == "risk_on"
    assert sig.market_regime(0.5, 0.2) == "tight"
    assert sig.market_regime(0.5, 0.5) == "neutral"


# --- builder tests ---
def test_build_with_no_data_creates_neutral_snapshot() -> None:
    session = TestingSession()
    try:
        outcome = WorldStateBuilder(session).build()
        assert outcome.macro_regime in {"expansion", "slowdown", "overheating", "stagflation"}
        assert outcome.confidence < 0.3  # همه no_data
        assert session.query(WorldState).count() == 1
    finally:
        session.close()


def test_build_uses_real_inputs() -> None:
    _seed_macro("inflation", "USA", [("2023", 4.12), ("2024", 2.95)])
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    _seed_market("WTI", "energy", 91.19)
    _seed_market("BRENT", "energy", 103.97)
    _seed_event("conflict", 0.8)
    session = TestingSession()
    try:
        outcome = WorldStateBuilder(session).build()
        snap = session.query(WorldState).one()
        # تورم 2.95 → 0.295
        assert abs(snap.inflation_pressure - 0.295) < 1e-6
        # رشد 3٪ → (0.03+0.05)/0.10 = 0.8
        assert abs(snap.growth_pressure - 0.8) < 1e-6
        # انرژی: میانگین (91.19-50)/100 و (103.97-50)/100
        expected_energy = ((91.19 - 50.0) / 100.0 + (103.97 - 50.0) / 100.0) / 2
        assert abs(snap.energy_risk - expected_energy) < 1e-6
        assert outcome.macro_regime == "expansion"
        # value_metadata کامل است
        meta = json.loads(snap.value_metadata or "{}")
        assert set(meta) == {
            "growth_pressure", "inflation_pressure", "liquidity",
            "financial_stress", "geopolitical_risk", "energy_risk",
            "trade_risk", "political_risk", "social_pressure",
        }
        assert meta["inflation_pressure"]["method"] == "cpi_over_10"
    finally:
        session.close()


def test_build_uses_single_country_series() -> None:
    """YoY نباید دو کشور مختلف را با هم ترکیب کند (USA ترجیح داده می‌شود)."""
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    _seed_macro("gdp", "IRN", [("2024", 900.0)])
    session = TestingSession()
    try:
        WorldStateBuilder(session).build()
        snap = session.query(WorldState).one()
        # فقط سری USA: رشد ۳٪ → 0.8 (نه ترکیب با IRN)
        assert abs(snap.growth_pressure - 0.8) < 1e-6
    finally:
        session.close()


def test_build_appends_history() -> None:
    session = TestingSession()
    try:
        WorldStateBuilder(session).build()
        WorldStateBuilder(session).build()
        assert session.query(WorldState).count() == 2
    finally:
        session.close()


# --- API tests ---
def test_worldstate_api_build_current_history(client: TestClient) -> None:
    res = client.post("/api/world-state/build")
    assert res.status_code == 200
    body = res.json()
    assert body["snapshot_id"]
    assert body["macro_regime"]
    assert body["market_regime"]
    assert len(body["signals"]) == 9

    cur = client.get("/api/world-state/current")
    assert cur.status_code == 200
    assert cur.json()["id"] == body["snapshot_id"]

    hist = client.get("/api/world-state/history?limit=10")
    assert hist.status_code == 200
    assert len(hist.json()) == 1


def test_worldstate_api_current_404(client: TestClient) -> None:
    res = client.get("/api/world-state/current")
    assert res.status_code == 404

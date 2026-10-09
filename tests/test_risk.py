"""Tests for Risk Engine analytics, service & API (Phase 31)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.world_state import WorldState
from domains.risk import analytics as an
from domains.risk.analysis import RiskEngine
from tests.conftest import TestingSession


def _meta(signals: dict[str, tuple[float, str, float]]) -> str:
    return json.dumps(
        {
            name: {"value": v, "method": m, "confidence": c}
            for name, (v, m, c) in signals.items()
        }
    )


def _seed_snapshot(signals: dict[str, tuple[float, str, float]]) -> str:
    session = TestingSession()
    try:
        s = WorldState(
            captured_at=datetime.now(UTC),
            granularity="daily",
            value_metadata=_meta(signals),
            confidence=0.5,
        )
        for name, (v, _, _) in signals.items():
            setattr(s, name, v)
        session.add(s)
        session.commit()
        return str(s.id)
    finally:
        session.close()


def _seed_tension(actor: str, tension: float, period: str = "2026-10") -> None:
    session = TestingSession()
    try:
        session.add(
            GeopoliticalAssessment(
                actor=actor,
                period=period,
                tension=tension,
                confidence=0.7,
                observed_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_scenarios(target: str = "macro:inflation:USA") -> None:
    session = TestingSession()
    try:
        for scenario, value in [("base", 3.0), ("bull", 4.0), ("bear", 2.0)]:
            session.add(
                Forecast(
                    valid_from=datetime.now(UTC),
                    target_date=datetime(2027, 1, 1, tzinfo=UTC),
                    horizon="short",
                    target=target,
                    expected_value=value,
                    model="baseline_naive",
                    model_version="v1",
                    scenario=scenario,
                    status="active",
                )
            )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_level_for() -> None:
    assert an.level_for(0.1) == "low"
    assert an.level_for(0.3) == "medium"
    assert an.level_for(0.6) == "high"
    assert an.level_for(0.9) == "critical"


def test_combine_modes() -> None:
    assert an.combine([]) is None
    mean = an.combine([(0.2, 0.5, "a"), (0.6, 0.5, "b")])
    assert mean is not None and mean.score == 0.4 and mean.level == "medium"
    mx = an.combine([(0.2, 0.5, "a"), (0.6, 0.5, "b")], mode="max")
    assert mx is not None and mx.score == 0.6 and mx.drivers == ["b"]


def test_growth_risk_both_tails() -> None:
    assert an.growth_risk(0.5).score == 0.0  # خنثی → بی‌ریسک
    assert an.growth_risk(0.0).score == 1.0  # رکود کامل
    assert an.growth_risk(1.0).score == 1.0  # overheat کامل
    assert an.growth_risk(None) is None


def test_spread_uncertainty() -> None:
    assert an.spread_uncertainty([]) is None
    s = an.spread_uncertainty([(4.0 - 2.0) / 3.0])
    assert s is not None and abs(s.score - 0.6667) < 1e-4


# --- engine tests ---
def test_engine_builds_categories() -> None:
    _seed_snapshot(
        {
            "inflation_pressure": (0.8, "cpi_over_10", 0.7),
            "growth_pressure": (0.5, "gdp_yoy_linear", 0.7),
            "financial_stress": (0.2, "yield_drawdown_mean", 0.6),
            "energy_risk": (0.6, "oil_band_50_150", 0.7),
            "geopolitical_risk": (0.3, "dispute_surprise_mix", 0.6),
            "trade_risk": (0.5, "no_data", 0.1),  # نامعتبر → skip
            "social_pressure": (0.2, "event_share", 0.5),
            "liquidity": (0.5, "no_data", 0.1),
        }
    )
    _seed_tension("Iran", 0.9)
    _seed_scenarios()
    session = TestingSession()
    try:
        outcome = RiskEngine(session).analyze_all(period="2026-10")
        # ۷ دسته با ورودی + trade بدون ورودی skip می‌شود
        assert outcome.categories_analyzed == 7
        assert outcome.skipped == 1
        rows = {r.category: r for r in session.query(RiskAssessment).all()}
        assert rows["inflation_risk"].score == 0.8
        assert rows["inflation_risk"].level == "critical"
        assert rows["growth_risk"].score == 0.0
        assert rows["geopolitical_risk"].score == 0.9  # max(0.3 جهان، 0.9 بازیگر)
        assert abs(rows["uncertainty"].score - 0.6667) < 1e-4
    finally:
        session.close()


def test_engine_no_snapshot_skips() -> None:
    session = TestingSession()
    try:
        outcome = RiskEngine(session).analyze_all(period="2026-10")
        assert outcome.skipped == 1
        assert outcome.categories_analyzed == 0
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_snapshot({"inflation_pressure": (0.8, "cpi_over_10", 0.7)})
    session = TestingSession()
    try:
        first = RiskEngine(session).analyze_all(period="2026-10")
        assert first.stored >= 1
        second = RiskEngine(session).analyze_all(period="2026-10")
        assert second.stored == 0
        assert second.duplicates == first.stored
    finally:
        session.close()


# --- API tests ---
def test_risk_api(client: TestClient) -> None:
    _seed_snapshot({"inflation_pressure": (0.8, "cpi_over_10", 0.7)})
    res = client.post("/api/risk/analyze?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] >= 1

    lst = client.get("/api/risk/assessments?period=2026-10")
    assert lst.status_code == 200
    assert len(lst.json()) >= 1

    ov = client.get("/api/risk/overview")
    assert ov.status_code == 200
    assert ov.json()[0]["category"] == "inflation_risk"  # پرخطرترین اول

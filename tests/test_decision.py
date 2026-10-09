"""Tests for Decision Engine analytics, service & API (Phase 32)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast
from backend.database.models.recommendation import Recommendation
from backend.database.models.risk_assessment import RiskAssessment
from domains.decision import analytics as an
from domains.decision.engine import DecisionEngine
from tests.conftest import TestingSession


def _seed_scenarios(
    target: str, base: float, bull: float, bear: float, tail: float | None = None
) -> None:
    session = TestingSession()
    try:
        scenarios = {"base": base, "bull": bull, "bear": bear}
        if tail is not None:
            scenarios["tail"] = tail
        for name, value in scenarios.items():
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


def _seed_risk(category: str, score: float, period: str = "2026-10") -> None:
    session = TestingSession()
    try:
        session.add(
            RiskAssessment(
                category=category,
                period=period,
                score=score,
                level="high",
                method="risk_v1",
                confidence=0.7,
                observed_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_directional_bias() -> None:
    assert an.directional_bias(100.0, 110.0, 90.0) == 0.0  # متقارن
    assert an.directional_bias(100.0, 120.0, 90.0) == 0.1
    assert an.directional_bias(0.0, 1.0, -1.0) == 0.0  # مخرج امن


def test_decide_branches() -> None:
    acc = an.decide(base=100.0, bull=140.0, bear=90.0, risks=[])
    assert acc.decision == "accumulate" and acc.direction == "up"
    red = an.decide(base=100.0, bull=110.0, bear=60.0, risks=[])
    assert red.decision == "reduce" and red.direction == "down"
    hold = an.decide(base=100.0, bull=105.0, bear=95.0, risks=[])
    assert hold.decision == "hold"
    avoid = an.decide(
        base=100.0, bull=200.0, bear=90.0, risks=[("market_risk", 0.9)]
    )
    assert avoid.decision == "avoid"  # ریسک حاکم است
    assert avoid.confidence == 0.8
    assert an.decide(base=100.0, bull=105.0, bear=95.0, risks=[]).confidence == 0.5


# --- engine tests ---
def test_engine_decides_with_risks() -> None:
    _seed_scenarios("market:WTI", 90.0, 100.0, 85.0, tail=70.0)
    _seed_risk("market_risk", 0.2)
    session = TestingSession()
    try:
        outcome = DecisionEngine(session).run(targets=["market:WTI"])
        assert outcome.decided == 1
        rec = session.query(Recommendation).one()
        assert rec.asset == "market:WTI"
        assert rec.decision in {"accumulate", "hold", "reduce", "avoid"}
        assert rec.model == "decision_v1"
        assert rec.rank == 1
    finally:
        session.close()


def test_engine_skips_without_scenarios() -> None:
    session = TestingSession()
    try:
        outcome = DecisionEngine(session).run(targets=["market:XXX"])
        assert outcome.decided == 0
        assert outcome.skipped == 1
    finally:
        session.close()


def test_engine_appends_history() -> None:
    _seed_scenarios("market:WTI", 90.0, 100.0, 85.0)
    session = TestingSession()
    try:
        DecisionEngine(session).run(targets=["market:WTI"])
        DecisionEngine(session).run(targets=["market:WTI"])
        assert session.query(Recommendation).count() == 2  # افزودنی by design
    finally:
        session.close()


# --- API tests ---
def test_decisions_api(client: TestClient) -> None:
    _seed_scenarios("macro:inflation:USA", 3.0, 4.0, 2.0)
    res = client.post("/api/decisions/run?targets=macro:inflation:USA")
    assert res.status_code == 200
    assert res.json()["decided"] == 1
    did = res.json()["decision_ids"][0]

    lst = client.get("/api/decisions?asset=macro:inflation:USA")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["model"] == "decision_v1"

    one = client.get(f"/api/decisions/{did}")
    assert one.status_code == 200

    assert (
        client.get("/api/decisions/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )

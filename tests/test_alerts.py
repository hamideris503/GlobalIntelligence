"""Tests for Alert metrics, engine & API (Phase 43)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.alert import Alert, AlertRule
from backend.database.models.risk_assessment import RiskAssessment
from domains.alerts import metrics as m
from domains.alerts.engine import AlertEngine
from tests.conftest import TestingSession


def _seed_risk(category: str, score: float) -> None:
    session = TestingSession()
    try:
        session.add(
            RiskAssessment(
                category=category,
                period="2026-10",
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


def _seed_rule(
    name: str = "r1",
    metric: str = "risk:energy_risk",
    operator: str = "gt",
    threshold: float = 0.5,
    cooldown: int = 24,
) -> str:
    session = TestingSession()
    try:
        rule = AlertRule(
            name=name,
            metric=metric,
            operator=operator,
            threshold=threshold,
            severity="warning",
            cooldown_hours=cooldown,
            active=True,
        )
        session.add(rule)
        session.commit()
        return str(rule.id)
    finally:
        session.close()


# --- pure tests ---
def test_breached() -> None:
    assert m.breached(0.6, "gt", 0.5) is True
    assert m.breached(0.4, "gt", 0.5) is False
    assert m.breached(0.4, "lt", 0.5) is True
    assert m.breached(None, "gt", 0.5) is False
    assert m.breached(0.6, "xx", 0.5) is False


def test_resolve_metric_unknown() -> None:
    session = TestingSession()
    try:
        assert m.resolve_metric(session, "nope") is None
        assert m.resolve_metric(session, "risk:missing") is None
        assert m.resolve_metric(session, "") is None
    finally:
        session.close()


def test_resolve_metric_risk() -> None:
    _seed_risk("energy_risk", 0.8)
    session = TestingSession()
    try:
        assert m.resolve_metric(session, "risk:energy_risk") == 0.8
    finally:
        session.close()


# --- engine tests ---
def test_engine_triggers_and_cooldown() -> None:
    _seed_risk("energy_risk", 0.8)
    _seed_rule()
    session = TestingSession()
    try:
        first = AlertEngine(session).evaluate()
        assert first.triggered == 1
        second = AlertEngine(session).evaluate()
        assert second.triggered == 0  # cooldown
        assert session.query(Alert).count() == 1
    finally:
        session.close()


def test_engine_no_breach_no_alert() -> None:
    _seed_risk("energy_risk", 0.2)
    _seed_rule()
    session = TestingSession()
    try:
        outcome = AlertEngine(session).evaluate()
        assert outcome.triggered == 0
        assert session.query(Alert).count() == 0
    finally:
        session.close()


def test_engine_unknown_metric_skips() -> None:
    _seed_rule(name="r2", metric="risk:missing")
    session = TestingSession()
    try:
        outcome = AlertEngine(session).evaluate()
        assert outcome.skipped == 1
    finally:
        session.close()


def test_ack_resolve_flow() -> None:
    from uuid import UUID

    _seed_risk("energy_risk", 0.8)
    _seed_rule()
    session = TestingSession()
    try:
        AlertEngine(session).evaluate()
        alert = session.query(Alert).one()
        engine = AlertEngine(session)
        assert engine.acknowledge(UUID(str(alert.id))).status == "acknowledged"
        assert engine.resolve(UUID(str(alert.id))).status == "resolved"
        assert engine.acknowledge(UUID(int=0)) is None
    finally:
        session.close()


# --- API tests ---
def test_alerts_api(client: TestClient) -> None:
    _seed_risk("energy_risk", 0.8)
    res = client.post(
        "/api/alerts/rules",
        json={"name": "api-r1", "metric": "risk:energy_risk",
              "operator": "gt", "threshold": 0.5},
    )
    assert res.status_code == 200

    dup = client.post(
        "/api/alerts/rules",
        json={"name": "api-r1", "metric": "risk:energy_risk",
              "operator": "gt", "threshold": 0.5},
    )
    assert dup.status_code == 409

    bad = client.post(
        "/api/alerts/rules",
        json={"name": "api-r2", "metric": "x", "operator": "xx", "threshold": 1},
    )
    assert bad.status_code == 422

    ev = client.post("/api/alerts/evaluate")
    assert ev.status_code == 200
    assert ev.json()["triggered"] == 1

    lst = client.get("/api/alerts?status=active")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    aid = lst.json()[0]["id"]

    ack = client.post(f"/api/alerts/{aid}/ack")
    assert ack.json()["status"] == "acknowledged"

    done = client.post(f"/api/alerts/{aid}/resolve")
    assert done.json()["status"] == "resolved"

    assert (
        client.get("/api/alerts/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )

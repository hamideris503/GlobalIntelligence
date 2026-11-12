"""مرحلهٔ ۶الف: ریسک، پیش‌بینی، تصمیم."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.database.models.forecast import Forecast
from backend.database.models.recommendation import Recommendation
from backend.database.models.risk_assessment import RiskAssessment
from backend.main import app
from tests.conftest import TestingSession


def _risk(category, *, probability=None, impact=None, score=0.6, period="2026-11"):
    s = TestingSession()
    r = RiskAssessment(category=category, period=period, score=score, level="medium",
                       probability=probability, impact=impact, observed_at=datetime.now(UTC))
    s.add(r)
    s.commit()
    rid = r.id
    s.close()
    return rid


def _forecast(target="X", *, scenario=None, expected=1.0, low=0.5, high=1.5):
    s = TestingSession()
    f = Forecast(target=target, horizon="short", expected_value=expected,
                 interval_low=low, interval_high=high, scenario=scenario,
                 status="active", model="baseline", data_version="v1",
                 target_date=datetime.now(UTC))
    s.add(f)
    s.commit()
    s.close()


class _Role:
    def __init__(self, role):
        self.role = role

    def __enter__(self):
        app.dependency_overrides[require_user] = lambda: CurrentUser(
            username=self.role, role=self.role, via="session")
        return self

    def __exit__(self, *a):
        app.dependency_overrides.pop(require_user, None)


def test_matrix_excludes_rows_without_probability_impact(client: TestClient) -> None:
    _risk("with", probability=0.7, impact=0.8)
    _risk("without")
    body = client.get("/api/risk/matrix").json()
    assert body["with_probability_impact"] == 1
    assert "without" in body["without_probability_impact"]
    assert sum(sum(row) for row in body["cells"]) == 1


def test_matrix_empty_ok(client: TestClient) -> None:
    body = client.get("/api/risk/matrix").json()
    assert body["cells"] == [[0] * 5 for _ in range(5)]
    assert body["total"] == 0


def test_risk_assessment_exposes_probability_impact(client: TestClient) -> None:
    _risk("c1", probability=0.3, impact=0.9)
    rows = client.get("/api/risk/assessments").json()
    row = next(r for r in rows if r["category"] == "c1")
    assert row["probability"] == 0.3
    assert row["impact"] == 0.9


def test_outlook_empty_when_no_forecasts(client: TestClient) -> None:
    body = client.get("/api/forecasts/outlook?target=none&horizon=short").json()
    assert body["series"] == []
    assert body["scenarios"] == []
    assert body["calibration"] is None


def test_outlook_series_from_active_forecast(client: TestClient) -> None:
    _forecast("targetA", expected=10.0)
    body = client.get("/api/forecasts/outlook?target=targetA&horizon=short").json()
    assert len(body["series"]) == 1
    assert body["series"][0]["p50"] == 10.0


def test_outlook_scenarios_probability_null_when_absent(client: TestClient) -> None:
    _forecast("targetB", scenario="bull", expected=2.0)
    body = client.get("/api/forecasts/outlook?target=targetB&horizon=short").json()
    assert body["scenarios"][0]["name"] == "bull"
    assert body["scenarios"][0]["probability"] is None


def _decision(asset="ACME"):
    s = TestingSession()
    r = Recommendation(asset=asset, decision="buy", score=0.8)
    s.add(r)
    s.commit()
    rid = r.id
    s.close()
    return rid


def test_decision_has_evidence_support(client: TestClient) -> None:
    rid = _decision("ACME")
    body = client.get(f"/api/decisions/{rid}").json()
    assert "evidence_support" in body
    assert set(body["evidence_support"]) >= {"for", "against", "independent_sources"}


def test_decision_review_requires_analyst(client: TestClient) -> None:
    rid = _decision("B")
    with _Role("viewer"):
        res = client.post(f"/api/decisions/{rid}/review", json={"decision": "approve"})
    assert res.status_code == 403


def test_decision_review_recorded(client: TestClient) -> None:
    rid = _decision("C")
    before = TestingSession().get(Recommendation, rid).decision
    with _Role("analyst"):
        res = client.post(f"/api/decisions/{rid}/review",
                          json={"decision": "request_evidence", "note": "need more"})
    assert res.status_code == 200
    assert res.json()["decision"]["action"] == "request_evidence"
    # machine output untouched
    assert TestingSession().get(Recommendation, rid).decision == before
    hist = client.get(f"/api/decisions/{rid}/reviews").json()
    assert len(hist["items"]) == 1


def test_decision_review_unknown_404(client: TestClient) -> None:
    with _Role("analyst"):
        res = client.post(f"/api/decisions/{uuid.uuid4()}/review", json={"decision": "approve"})
    assert res.status_code == 404


def test_decision_review_invalid_action_422(client: TestClient) -> None:
    rid = _decision("D")
    with _Role("analyst"):
        res = client.post(f"/api/decisions/{rid}/review", json={"decision": "nope"})
    assert res.status_code == 422

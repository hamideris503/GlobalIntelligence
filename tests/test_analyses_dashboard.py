"""مرحلهٔ ۶A: تحلیل‌ها و داشبورد."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.database.models.claim import Claim, Evidence
from backend.database.models.debate import DebateRun
from backend.database.models.event import Event
from backend.database.models.forecast import Forecast, Recommendation
from backend.main import app
from tests.conftest import TestingSession


class _Role:
    def __init__(self, role):
        self.role = role

    def __enter__(self):
        app.dependency_overrides[require_user] = lambda: CurrentUser(
            username=self.role, role=self.role, via="session")
        return self

    def __exit__(self, *a):
        app.dependency_overrides.pop(require_user, None)


def _rec(asset="ACME", decision="buy", confidence=0.8):
    s = TestingSession()
    r = Recommendation(asset=asset, decision=decision, confidence=confidence, model="dec_v1")
    s.add(r)
    s.commit()
    rid = str(r.id)
    s.close()
    return rid


def _forecast(target="market:X", status="active"):
    s = TestingSession()
    f = Forecast(target=target, horizon="short", status=status, confidence=0.6, model="baseline")
    s.add(f)
    s.commit()
    fid = str(f.id)
    s.close()
    return fid


def _debate(target="X", consensus=None, status="done"):
    s = TestingSession()
    d = DebateRun(target=target, status=status, consensus_probability=consensus, disagreement=0.2)
    s.add(d)
    s.commit()
    did = str(d.id)
    s.close()
    return did


# --- analyses list -----------------------------------------------------------

def test_analyses_empty(client: TestClient) -> None:
    body = client.get("/api/analyses").json()
    assert body["items"] == []
    assert body["total"] == 0


def test_analyses_aggregates_three_kinds(client: TestClient) -> None:
    _rec()
    _forecast()
    _debate()
    body = client.get("/api/analyses").json()
    kinds = {i["kind"] for i in body["items"]}
    assert kinds == {"recommendation", "forecast", "debate"}
    assert all(i["id"].startswith(("recommendation:", "forecast:", "debate:")) for i in body["items"])


def test_analyses_filter_domain_and_search(client: TestClient) -> None:
    _rec(asset="ZEDCORP")
    _forecast(target="market:AAA")
    assert client.get("/api/analyses?domain=market").json()["total"] == 1
    body = client.get("/api/analyses?q=zed").json()
    assert body["total"] == 1


def test_analyses_invalid_sort_422(client: TestClient) -> None:
    res = client.get("/api/analyses?sort=nope")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_analyses_pagination(client: TestClient) -> None:
    for i in range(3):
        _rec(asset=f"A{i}")
    body = client.get("/api/analyses?page=1&page_size=2").json()
    assert set(body) >= {"items", "total", "page", "page_size", "has_more"}
    assert len(body["items"]) == 2


def test_analysis_trace_full_and_missing(client: TestClient) -> None:
    rid = _rec()
    s = TestingSession()
    ev = Event(event_type="attack", action="x")
    s.add(ev)
    s.flush()
    s.add(Claim(event_id=ev.id, subject="a", predicate="b", object="c", verification_status="unverified"))
    s.commit()
    s.close()
    body = client.get(f"/api/analyses/recommendation:{rid}/trace").json()
    stages = {st["stage"]: st["status"] for st in body["steps"]}
    assert stages["claim"] == "AVAILABLE"
    assert stages["evidence"] == "INSUFFICIENT_EVIDENCE"
    assert client.get("/api/analyses/nonexistent/trace").status_code == 404


def test_analysis_trace_evidence_available(client: TestClient) -> None:
    rid = _rec()
    s = TestingSession()
    c = Claim(subject="a", predicate="b", object="c", verification_status="unverified")
    s.add(c)
    s.flush()
    s.add(Evidence(claim_id=c.id, direction="supports", summary="e"))
    s.commit()
    s.close()
    body = client.get(f"/api/analyses/recommendation:{rid}/trace").json()
    stages = {st["stage"]: st["status"] for st in body["steps"]}
    assert stages["evidence"] == "AVAILABLE"


def test_analysis_request_requires_analyst(client: TestClient) -> None:
    with _Role("viewer"):
        res = client.post("/api/analyses/request", json={"task": "claim_extraction"})
    assert res.status_code == 403


def test_analysis_request_ok(client: TestClient) -> None:
    with _Role("analyst"):
        res = client.post("/api/analyses/request", json={"task": "claim_extraction", "limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert "outcome" in body
    assert body["processed"] >= 0


# --- dashboard ---------------------------------------------------------------

def test_dashboard_shape(client: TestClient) -> None:
    body = client.get("/api/dashboard/overview").json()
    assert set(body) >= {"last_analysis", "kpis", "model_consensus", "evidence_chain",
                         "latest_outputs", "priority_suggestions", "risk_series"}
    assert all("definition" in k and "status" in k for k in body["kpis"])


def test_dashboard_kpis_from_real_counts(client: TestClient) -> None:
    s = TestingSession()
    s.add(Event(event_type="attack"))
    s.commit()
    s.close()
    body = client.get("/api/dashboard/overview").json()
    events_kpi = next(k for k in body["kpis"] if k["key"] == "events")
    assert events_kpi["value"] == 1


def test_dashboard_consensus_unavailable_without_debate(client: TestClient) -> None:
    body = client.get("/api/dashboard/overview").json()
    assert body["model_consensus"]["status"] in ("UNAVAILABLE", "INSUFFICIENT_EVIDENCE")


def test_dashboard_no_provider_secrets(client: TestClient) -> None:
    body = json.dumps(client.get("/api/dashboard/overview").json())
    assert "api_key" not in body.lower()
    assert "secret" not in body.lower()


def test_dashboard_viewer_allowed(client: TestClient) -> None:
    with _Role("viewer"):
        assert client.get("/api/dashboard/overview").status_code == 200


def test_analyses_viewer_allowed(client: TestClient) -> None:
    with _Role("viewer"):
        assert client.get("/api/analyses").status_code == 200

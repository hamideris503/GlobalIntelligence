"""Tests for Self Evaluation checks, service & API (Phase 39)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.self_evaluation import SelfEvaluation
from domains.selfeval import checks as ck
from domains.selfeval.service import SelfEvaluationService
from tests.conftest import TestingSession


# --- pure tests ---
def test_check_thresholds() -> None:
    assert ck.classification_check(95, 100).status == "pass"
    assert ck.classification_check(60, 100).status == "warn"
    assert ck.classification_check(10, 100).status == "fail"
    assert ck.classification_check(0, 0).status == "warn"
    assert ck.evidence_check(9, 10).status == "pass"
    assert ck.forecast_check(2).status == "pass"
    assert ck.forecast_check(0).status == "warn"
    assert ck.freshness_check(10.0).status == "pass"
    assert ck.freshness_check(100.0).status == "warn"
    assert ck.freshness_check(200.0).status == "fail"
    assert ck.freshness_check(None).status == "warn"
    assert ck.memory_check({"raw", "event", "state"}).status == "pass"
    assert ck.memory_check({"raw"}).status == "warn"
    assert ck.graph_check(5).status == "pass"
    assert ck.graph_check(0).status == "warn"


def test_grade_and_overall() -> None:
    assert ck.grade_for(0.95) == "A"
    assert ck.grade_for(0.75) == "B"
    assert ck.grade_for(0.5) == "C"
    assert ck.grade_for(0.1) == "D"
    score, grade = ck.overall(
        [
            ck.classification_check(100, 100),
            ck.forecast_check(0),
        ]
    )
    assert score == 0.75 and grade == "B"
    assert ck.overall([]) == (0.0, "D")


# --- service tests ---
def test_service_runs_and_stores() -> None:
    session = TestingSession()
    try:
        outcome = SelfEvaluationService(session).run()
        assert outcome.evaluation_id
        assert outcome.grade in {"A", "B", "C", "D"}
        assert len(outcome.checks) == 6
        assert session.query(SelfEvaluation).count() == 1
    finally:
        session.close()


def test_service_appends_history() -> None:
    session = TestingSession()
    try:
        SelfEvaluationService(session).run()
        SelfEvaluationService(session).run()
        assert session.query(SelfEvaluation).count() == 2
    finally:
        session.close()


# --- API tests ---
def test_selfeval_api(client: TestClient) -> None:
    assert client.get("/api/self-eval/latest").status_code == 404
    res = client.post("/api/self-eval/run")
    assert res.status_code == 200
    body = res.json()
    assert body["grade"] in {"A", "B", "C", "D"}
    assert len(body["checks"]) == 6

    latest = client.get("/api/self-eval/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == body["evaluation_id"]

    hist = client.get("/api/self-eval/history")
    assert hist.status_code == 200
    assert len(hist.json()) == 1

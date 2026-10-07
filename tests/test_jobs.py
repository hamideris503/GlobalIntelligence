"""Tests for the jobs API (Phase 4)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database import models as _models
from tests.conftest import TestingSession


def test_trigger_and_list_job(client: TestClient) -> None:
    res = client.post(
        "/api/jobs/trigger",
        json={"job_name": "test_job", "source": "pytest", "payload": {"k": "v"}},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "accepted"
    assert body["job_run"]["job_name"] == "test_job"
    assert body["job_run"]["source"] == "pytest"

    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    assert any(j["job_name"] == "test_job" for j in listing.json())


def test_trigger_requires_job_name(client: TestClient) -> None:
    res = client.post("/api/jobs/trigger", json={"source": "pytest"})
    assert res.status_code == 422


def test_jobs_persist(client: TestClient) -> None:
    client.post("/api/jobs/trigger", json={"job_name": "persist_check"})
    session = TestingSession()
    try:
        assert session.query(_models.JobRun).filter_by(job_name="persist_check").count() == 1
    finally:
        session.close()

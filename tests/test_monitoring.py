"""Tests for Production Monitoring checks, service & API (Phase 50)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.job import JobRun
from domains.ops import monitoring as mon
from domains.ops.service import MonitoringService
from tests.conftest import TestingSession


# --- pure tests ---
def test_check_bands() -> None:
    assert mon.pipeline_lag_check(10.0).status == "pass"
    assert mon.pipeline_lag_check(50.0).status == "warn"
    assert mon.pipeline_lag_check(100.0).status == "fail"
    assert mon.pipeline_lag_check(None).status == "warn"
    assert mon.backlog_check(10).status == "pass"
    assert mon.backlog_check(100).status == "warn"
    assert mon.backlog_check(500).status == "fail"
    assert mon.unprocessed_check("x", 5).status == "pass"
    assert mon.error_rate_check(1, 10).status == "pass"
    assert mon.error_rate_check(3, 10).status == "warn"
    assert mon.error_rate_check(6, 10).status == "fail"
    assert mon.error_rate_check(0, 0).status == "warn"
    assert mon.active_alerts_info(3).status == "pass"
    assert mon.db_check(True).status == "pass"
    assert mon.db_check(False).status == "fail"


def test_overall_status() -> None:
    assert mon.overall_status([]) == "fail"
    assert (
        mon.overall_status([mon.db_check(True), mon.backlog_check(1)]) == "pass"
    )
    assert (
        mon.overall_status([mon.db_check(True), mon.backlog_check(100)]) == "warn"
    )
    assert (
        mon.overall_status([mon.db_check(False), mon.backlog_check(1)]) == "fail"
    )


# --- service tests ---
def test_service_report_shape() -> None:
    session = TestingSession()
    try:
        outcome = MonitoringService(session).report()
        assert outcome.status in {"pass", "warn", "fail"}
        names = {c["name"] for c in outcome.checks}
        assert names == {
            "database", "pipeline_lag", "classify_backlog",
            "unprocessed_events", "unprocessed_claims", "error_rate",
            "active_alerts",
        }
    finally:
        session.close()


def test_service_counts_failed_jobs() -> None:
    session = TestingSession()
    try:
        for i in range(4):
            session.add(
                JobRun(job_name=f"j{i}", source="test",
                       status="failed" if i < 3 else "ok")
            )
        session.commit()
        outcome = MonitoringService(session).report()
        err = next(c for c in outcome.checks if c["name"] == "error_rate")
        assert err["status"] == "fail"  # 3/4
        assert err["value"] == 0.75
    finally:
        session.close()


def test_prometheus_format() -> None:
    session = TestingSession()
    try:
        text = MonitoringService(session).prometheus()
        assert "gi_monitor_status" in text
        assert "gi_articles_total" in text
        assert text.endswith("\n")
        for line in text.splitlines():
            assert not line.startswith(" "), line
    finally:
        session.close()


# --- API tests ---
def test_monitoring_api(client: TestClient) -> None:
    res = client.get("/api/ops/monitoring")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in {"pass", "warn", "fail"}
    assert len(body["checks"]) == 7

    metrics = client.get("/api/ops/metrics")
    assert metrics.status_code == 200
    assert "gi_monitor_status" in metrics.text
    assert "text/plain" in metrics.headers["content-type"]

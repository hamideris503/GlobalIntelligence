"""Tests for Production Monitoring checks, service & API (Phase 50)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.ai.local_screening import get_screening_stats
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
    assert mon.market_staleness_check(10.0, "XAUUSD").status == "pass"
    assert mon.market_staleness_check(100.0, "XAUUSD").status == "warn"
    assert mon.market_staleness_check(200.0, "XAUUSD").status == "fail"
    assert mon.market_staleness_check(None).status == "warn"


def test_count_query_failure_is_fail_not_pass() -> None:
    """AUDIT-REPAIR: خطای شمارش نباید healthy گزارش شود (قبلاً ۱- → pass)."""
    failed = mon.count_check("classify_backlog", None, 50.0, 200.0, "pending")
    assert failed.status == "fail"
    assert failed.value is None
    assert "query failed" in failed.detail


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
            "active_alerts", "market_staleness",
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


def test_service_market_staleness() -> None:
    """چک تازگی قیمت: بدون ردیف warn؛ نقل‌قول کهنه fail با نام نماد."""
    from datetime import UTC, datetime, timedelta

    from backend.database.models.market import MarketObservation

    session = TestingSession()
    try:
        outcome = MonitoringService(session).report()
        stale = next(c for c in outcome.checks if c["name"] == "market_staleness")
        assert stale["status"] == "warn"  # no data
        assert stale["value"] is None

        session.add(MarketObservation(
            symbol="XAUUSD", asset_class="metal", value=4000.0,
            unit="usd_per_oz", currency="USD", source_name="test",
            observed_at=datetime.now(UTC) - timedelta(hours=200),
        ))
        session.commit()
        outcome = MonitoringService(session).report()
        stale = next(c for c in outcome.checks if c["name"] == "market_staleness")
        assert stale["status"] == "fail"
        assert "XAUUSD" in stale["detail"]
    finally:
        session.close()


def test_prometheus_format() -> None:
    session = TestingSession()
    try:
        text = MonitoringService(session).prometheus()
        assert "gi_monitor_status" in text
        assert "gi_articles_total" in text
        assert "gi_local_screening_screens_total" in text
        assert text.endswith("\n")
        for line in text.splitlines():
            assert not line.startswith(" "), line
    finally:
        session.close()


def test_local_screening_metrics_separate_success_timeout_and_abstention(
    client: TestClient,
) -> None:
    stats = get_screening_stats()
    stats.reset()
    stats.record_screen()
    stats.record_attempt("kev", "ok", 12.0)
    stats.record_result("decided", "kev")
    stats.record_screen()
    stats.record_attempt("laya", "unavailable", 20.0, "timeout")
    stats.record_attempt("laya", "unavailable", 30.0, "connection")
    stats.record_attempt("laya", "invalid", 5.0, "invalid_output")
    stats.record_result("unavailable", None)

    metrics = client.get("/api/ops/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "gi_local_screening_screens_total 2" in text
    assert "gi_local_screening_calls_total 4" in text
    assert "gi_local_screening_success_total 1" in text
    assert "gi_local_screening_errors_total 3" in text
    assert "gi_local_screening_timeouts_total 1" in text
    assert "gi_local_screening_connection_errors_total 1" in text
    assert "gi_local_screening_invalid_total 1" in text
    assert "gi_local_screening_decided_total 1" in text
    assert "gi_local_screening_abstained_total 1" in text
    assert 'gi_local_screening_provider_calls_total{provider="kev"} 1' in text
    assert 'gi_local_screening_provider_calls_total{provider="laya"} 3' in text
    assert 'gi_local_screening_provider_timeouts_total{provider="laya"} 1' in text
    assert 'gi_local_screening_provider_connection_errors_total{provider="laya"} 1' in text
    assert 'gi_local_screening_provider_invalid_total{provider="laya"} 1' in text


# --- API tests ---
def test_monitoring_api(client: TestClient) -> None:
    res = client.get("/api/ops/monitoring")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in {"pass", "warn", "fail"}
    assert len(body["checks"]) == 8

    metrics = client.get("/api/ops/metrics")
    assert metrics.status_code == 200
    assert "gi_monitor_status" in metrics.text
    assert "text/plain" in metrics.headers["content-type"]

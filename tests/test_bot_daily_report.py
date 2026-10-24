"""گزارش روزانهٔ هر منبع + شمارنده‌های تفکیکی — sqlite ایزوله، بدون شبکه/AI/DB واقعی."""
from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, datetime

import pytest

from backend.database.models.job import JobRun
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot import jobs as jobs_module
from source_bot.report import build_daily_report, job_records, range_bounds
from tests.conftest import TestingSession

DAY = "2026-10-18"


def _mk_source(name: str) -> None:
    db = TestingSession()
    try:
        db.add(Source(name=name, collection_method="rss", type="rss",
                      feed_url=f"https://{name}.test/rss"))
        db.commit()
    finally:
        db.close()


def _job(*, at: str, status: str = "completed", result: dict | None = None,
         message: str | None = None, raw_payload: str | None = None) -> None:
    db = TestingSession()
    try:
        payload = raw_payload or json.dumps({"spec": {}, "result": result}, ensure_ascii=False)
        when = datetime.fromisoformat(at).replace(tzinfo=UTC)
        db.add(JobRun(job_name="ingest", source="api", status=status, payload=payload,
                      message=message, started_at=when, finished_at=when))
        db.commit()
    finally:
        db.close()


def _alpha(**over: object) -> dict:
    stats = {"ok": True, "fetch_ok": True, "fetch_attempts": 1, "fetched": 3, "stored": 2,
             "duplicates": 1, "rejected_keyless": 0, "by_priority": {"P0": 1, "P2": 1},
             "ai_used": 1, "ai_fallback": 0, "pending": 1, "duration_ms": 120}
    stats.update(over)
    return stats


def _records_for_day() -> list[dict]:
    """fixture شناخته‌شده: A/B موفق، C خارج از بازه، D اجرای ناموفق، E قدیمی، F payload خراب."""
    _job(at="2026-10-18T10:00:00", result={
        "sources_checked": 2, "sources_ok": 1, "sources_failed": {"beta": "RuntimeError: source down"},
        "fetched": 3, "stored": 2, "duplicates": 1, "by_priority": {"P0": 1, "P2": 1},
        "ai_used": 1, "ai_fallback": 0,
        "by_source": {
            "alpha": _alpha(),
            "beta": {"ok": False, "fetch_ok": False, "fetch_attempts": 2, "fetched": 0, "stored": 0,
                     "duplicates": 0, "rejected_keyless": 0, "by_priority": {}, "ai_used": 0,
                     "ai_fallback": 0, "pending": 0, "duration_ms": 80},
        }})
    _job(at="2026-10-18T11:00:00", result={
        "sources_checked": 1, "sources_ok": 1, "sources_failed": {},
        "by_source": {"alpha": _alpha(fetched=2, stored=1, duplicates=1, rejected_keyless=1,
                                      by_priority={"P4": 1}, ai_used=0, ai_fallback=2,
                                      pending=0, duration_ms=100)}})
    _job(at="2026-10-19T09:00:00", result={"sources_failed": {}, "by_source": {"alpha": _alpha()}})
    _job(at="2026-10-18T12:00:00", status="failed", message="priority configuration invalid: x")
    _job(at="2026-10-18T13:00:00", result={
        "sources_checked": 1, "sources_ok": 1, "sources_failed": {}, "fetched": 5, "stored": 5,
        "duplicates": 0, "by_priority": {"P1": 5}, "ai_used": 0, "ai_fallback": 0})
    _job(at="2026-10-18T14:00:00", raw_payload="{not json")
    db = TestingSession()
    try:
        start, end, _ = range_bounds(day=DAY)
        return job_records(db, start=start, end=end)
    finally:
        db.close()


def _row(report: dict, name: str) -> dict:
    return next(row for row in report["sources"] if row["name"] == name)


# --- ۱ تا ۴: مقادیر دقیق، تفکیک منبع، سطوح اولویت، بدون دوباره‌شماری ---

def test_daily_report_exact_values_per_source() -> None:
    report = build_daily_report(_records_for_day(), day=DAY)

    assert report["timezone"] == "UTC" and report["day"] == DAY
    assert report["runs"] == {"total": 5, "with_result": 3, "failed_without_result": 2,
                              "without_per_source": 1}
    assert report["history_gap"]["runs_without_per_source"] == 1

    alpha = _row(report, "alpha")
    assert (alpha["runs"], alpha["ok_runs"], alpha["failed_runs"]) == (2, 2, 0)
    assert (alpha["fetched"], alpha["stored"]) == (5, 3)
    assert (alpha["duplicates"], alpha["rejected_keyless"]) == (2, 1)  # جدا، بدون دوباره‌شماری
    assert (alpha["fetch_attempts"], alpha["retries"], alpha["no_fetch_runs"]) == (2, 0, 0)
    assert alpha["by_priority"] == {"P0": 1, "P1": 0, "P2": 1, "P3": 0, "P4": 1}
    assert sum(alpha["by_priority"].values()) == alpha["stored"]  # ناوردایی: هر ذخیره یک سطح
    assert (alpha["pending"], alpha["ai_used"], alpha["ai_fallback"]) == (1, 1, 2)
    assert alpha["duration_ms_total"] == 220 and alpha["duration_ms_runs"] == 2
    assert alpha["duration_ms_avg"] == 110
    assert alpha["last_success_at"] == "2026-10-18T11:00:00+00:00"
    assert alpha["errors"] == []

    beta = _row(report, "beta")
    assert (beta["runs"], beta["ok_runs"], beta["failed_runs"]) == (1, 0, 1)
    assert (beta["fetch_attempts"], beta["retries"]) == (2, 1)  # retry از attempts مشتق می‌شود
    assert (beta["fetched"], beta["stored"], beta["duration_ms_avg"]) == (0, 0, 80)
    assert beta["last_success_at"] is None and beta["errors"] == ["RuntimeError: source down"]
    assert set(beta["by_priority"]) == {"P0", "P1", "P2", "P3", "P4"}


def test_report_does_not_invent_sources_or_numbers() -> None:
    """اجرای قدیمی بدون by_source (E) و payload خراب (F) هیچ عدد جعلی/منبع جعلی نمی‌سازند."""
    report = build_daily_report(_records_for_day(), day=DAY)
    assert {row["name"] for row in report["sources"]} == {"alpha", "beta"}
    # P1×5 گزارش قدیمی (E) به هیچ منبعی نسبت داده نشده است
    assert all(row["by_priority"]["P1"] == 0 for row in report["sources"])


def test_unavailable_fields_are_explicit_not_zero() -> None:
    report = build_daily_report([])
    assert "ai_cost_usd" in report["unavailable_fields"]
    assert "ai_http_attempts" in report["unavailable_fields"]
    # توکن‌ها از مرحلهٔ ۱۶ اندازه‌گیری می‌شوند؛ دیگر «ناموجود» اعلام نمی‌شوند.
    assert "ai_tokens" not in report["unavailable_fields"]
    assert report["ai_usage"]["status"] == "not_instrumented"
    assert report["ai_usage"]["tokens_total"] is None
    assert report["runs"]["total"] == 0 and report["sources"] == []
    assert report["generated_from"].startswith("job_runs")


def test_errors_deduped_but_runs_counted() -> None:
    """پیام تکراری یک‌بار گزارش می‌شود ولی هر اجرا یک‌بار شمرده می‌شود."""
    _job(at="2026-10-18T10:00:00", result={"sources_failed": {"beta": "RuntimeError: down"},
                                            "by_source": {"beta": {"fetch_attempts": 1}}})
    _job(at="2026-10-18T11:00:00", result={"sources_failed": {"beta": "RuntimeError: down"},
                                            "by_source": {"beta": {"fetch_attempts": 1}}})
    db = TestingSession()
    try:
        rows = job_records(db, start=range_bounds(day=DAY)[0], end=range_bounds(day=DAY)[1])
    finally:
        db.close()
    beta = _row(build_daily_report(rows), "beta")
    assert beta["runs"] == 2 and beta["failed_runs"] == 2 and beta["errors"] == ["RuntimeError: down"]


def test_error_message_truncated_and_no_raw_text() -> None:
    long_error = "E" * 400
    _job(at="2026-10-18T10:00:00", result={"sources_failed": {"beta": long_error},
                                            "by_source": {"beta": {"fetch_attempts": 1}}})
    db = TestingSession()
    try:
        rows = job_records(db, start=range_bounds(day=DAY)[0], end=range_bounds(day=DAY)[1])
    finally:
        db.close()
    assert _row(build_daily_report(rows), "beta")["errors"] == ["E" * 200]


# --- ۵ تا ۷: بازه، idempotency و رفتار گزارش خالی ---

def test_range_bounds_and_repeated_run_is_idempotent() -> None:
    today = datetime(2026, 10, 19, tzinfo=UTC)
    start, end, day = range_bounds(days=2, now=today)
    assert (start.isoformat(), end.isoformat(), day) == (
        "2026-10-18T00:00:00+00:00", "2026-10-20T00:00:00+00:00", None)

    records = _records_for_day()
    before = copy.deepcopy(records)
    first = build_daily_report(records, day=DAY)
    second = build_daily_report(records, day=DAY)
    assert first == second                 # اجرای تکراری، دوباره‌شماری نمی‌کند
    assert records == before               # ورودی دست‌نخورده می‌ماند
    assert _row(first, "alpha")["stored"] == 3

    # بازهٔ دو روزه (۱۰-۱۸ و ۱۰-۱۹): اجرای C هم اضافه می‌شود، بدون دوباره‌شماری A/B
    db = TestingSession()
    try:
        window = job_records(db, start=start, end=end)
    finally:
        db.close()
    wide = build_daily_report(window)
    assert wide["runs"]["total"] == 6
    assert _row(wide, "alpha")["runs"] == 3 and _row(wide, "alpha")["stored"] == 5


def test_days_must_be_positive() -> None:
    with pytest.raises(ValueError):
        range_bounds(days=0)


def test_empty_day_is_explicit() -> None:
    db = TestingSession()
    try:
        rows = job_records(db, start=range_bounds(day="2020-01-01")[0],
                           end=range_bounds(day="2020-01-01")[1])
    finally:
        db.close()
    report = build_daily_report(rows, day="2020-01-01")
    assert report["runs"]["total"] == 0 and report["sources"] == []
    assert report["history_gap"]["runs_without_per_source"] == 0


# --- شمارنده‌های تفکیکی در خود runner + جداسازی خطای منبع ---

def _wire_fetch(monkeypatch) -> list:
    from source_bot import runner as runner_module

    calls: list = []
    monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "0")
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")
    monkeypatch.setattr(jobs_module, "get_session_factory", lambda: TestingSession)

    async def _fake(plan, settings):
        calls.append(plan.url)
        if "bad" in (plan.url or ""):
            raise RuntimeError("source down")
        return ([RawItem(title="Triage dispatch", url=f"{plan.url}/1",
                         raw_text="ward logistics update " * 20)], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", _fake)
    return calls


def test_runner_records_per_source_and_isolates_failure(monkeypatch) -> None:
    from source_bot.runner import run_once

    _mk_source("bad-src")
    _mk_source("ok-src")
    calls = _wire_fetch(monkeypatch)

    metrics = asyncio.run(run_once(limit_sources=5, db=TestingSession()))

    assert sorted(metrics.by_source) == ["bad-src", "ok-src"]
    bad = metrics.by_source["bad-src"]
    assert (bad.fetch_attempts, bad.fetch_ok, bad.ok, bad.stored) == (1, False, False, 0)
    ok = metrics.by_source["ok-src"]
    assert (ok.fetch_attempts, ok.fetch_ok, ok.ok, ok.stored) == (1, True, True, 1)
    assert ok.fetched == 1 and sum(ok.by_priority.values()) == ok.stored
    assert isinstance(ok.duration_ms, int) and ok.duration_ms >= 0
    assert metrics.sources_ok == 1 and list(metrics.sources_failed) == ["bad-src"]
    assert len(calls) == 2  # منبع خراب، اجرای منبع سالم را متوقف نکرد


def test_second_run_blocked_by_lock(tmp_path, monkeypatch) -> None:
    from source_bot import runner as runner_module

    monkeypatch.setattr(runner_module, "LOCK_PATH", str(tmp_path / "bot.lock"))
    calls = _wire_fetch(monkeypatch)
    assert runner_module._acquire_lock() is True
    try:
        with pytest.raises(RuntimeError):
            asyncio.run(runner_module.run_once(source_name="ok-src"))
    finally:
        runner_module._release_lock()
    assert calls == []  # اجرای دوم حتی fetch نکرد

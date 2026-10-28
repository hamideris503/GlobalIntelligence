"""اجرای کنترل‌شدهٔ Source Bot — سقف آیتم، منبع غیرفعال، توقف با آمار جزئی، سقف retry.

همهٔ تست‌ها آفلاین‌اند: fetch/HTTP با fake جایگزین می‌شود، AI خاموش است،
مسیر فایل stop به tmp_path منتقل می‌شود و هیچ DNS/HTTP/provider واقعی صدا زده نمی‌شود.
"""
from __future__ import annotations

import asyncio
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem, RSSFetcher
from source_bot import jobs as jobs_module
from source_bot import runner as runner_module
from source_bot.metrics import BotMetrics
from tests.conftest import TestingSession

LEVELS = ("P0", "P1", "P2", "P3", "P4")


@pytest.fixture(autouse=True)
def _isolated_stop(tmp_path, monkeypatch):
    """مسیر stop واقعی سیستم لمس نمی‌شود؛ تست‌ها روی فایل موقت کار می‌کنند."""
    monkeypatch.setattr(runner_module, "STOP_PATH", str(tmp_path / "source_bot.stop"))
    assert runner_module.should_stop() is False


@pytest.fixture(autouse=True)
def _offline_dns(monkeypatch):
    """هیچ resolve واقعی: host_is_private هر دو ماژول ثابت و عمومی می‌شود."""
    from domains.news import source_verify
    from source_bot import security

    monkeypatch.setattr(source_verify, "host_is_private", lambda host: False)
    monkeypatch.setattr(security, "host_is_private", lambda host: False)


def _source(db, name: str, *, active: bool = True) -> Source:
    src = Source(name=name, collection_method="rss", type="rss",
                 feed_url=f"https://{name}.test/rss", active=active)
    db.add(src)
    db.commit()
    return src


def _items(name: str, count: int) -> list[RawItem]:
    return [
        RawItem(title=f"{name} item {i}", url=f"https://{name}.test/{i}",
                raw_text=f"body text number {i} " * 10,
                raw_payload=f'{{"title": "{name} item {i}"}}')
        for i in range(count)
    ]


def _wire(monkeypatch, items: list[RawItem], calls: list[str] | None = None,
          *, retries: int = 0) -> None:
    async def fake_fetch(plan, settings):  # noqa: ANN001
        if calls is not None:
            calls.append(plan.url or "")
        return (list(items), "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", str(retries))
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")


def _stop_now() -> None:
    with open(runner_module.STOP_PATH, "w", encoding="utf-8") as fh:
        fh.write("stop")


def _clear_stop() -> None:
    if os.path.exists(runner_module.STOP_PATH):
        os.remove(runner_module.STOP_PATH)


def _run(**kwargs) -> BotMetrics:
    return asyncio.run(runner_module.run_once(**kwargs))


# --- بخش اول: سقف آیتم ---

def test_items_cap_limits_processing_but_not_fetch(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "cap-src")
        calls: list[str] = []
        _wire(monkeypatch, _items("cap-src", 5), calls)

        metrics = _run(source_name="cap-src", max_items_per_source=3, db=db)
        sm = metrics.by_source["cap-src"]

        assert len(calls) == 1                       # fetch یک‌بار انجام شد
        assert metrics.fetched == 5 and sm.fetched == 5
        assert sm.items_skipped_limit == 2 and metrics.items_skipped_limit == 2
        assert sm.stored == 3 and metrics.stored == 3
        assert sum(sm.by_priority.values()) == 3
        assert sm.duplicates == 0 and sm.rejected_keyless == 0  # سقف ≠ duplicate/خطا
        assert db.query(Document).count() == 3
        assert metrics.stopped is False
        assert sm.duration_ms is not None
    finally:
        db.close()


def test_missing_cap_keeps_previous_behavior(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "nocap-src")
        _wire(monkeypatch, _items("nocap-src", 5))
        metrics = _run(source_name="nocap-src", db=db)
        assert metrics.stored == 5 and metrics.items_skipped_limit == 0
        assert metrics.by_source["nocap-src"].items_skipped_limit == 0
        assert db.query(Document).count() == 5
    finally:
        db.close()


def test_upper_bound_cap_is_accepted(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "bound-src")
        _wire(monkeypatch, _items("bound-src", 2))
        metrics = _run(source_name="bound-src", max_items_per_source=200, db=db)
        assert metrics.stored == 2 and metrics.stopped is False
    finally:
        db.close()


@pytest.mark.parametrize("bad", [0, -1, 201, True, "3", 3.5])
def test_invalid_cap_rejected_before_fetch(monkeypatch, bad) -> None:
    db = TestingSession()
    try:
        _source(db, "badcap-src")
        calls: list[str] = []
        _wire(monkeypatch, _items("badcap-src", 3), calls)
        with pytest.raises(ValueError, match="max_items_per_source"):
            _run(source_name="badcap-src", max_items_per_source=bad, db=db)
        assert calls == []
        assert db.query(Document).count() == 0
    finally:
        db.close()


# --- بخش دوم: منبع غیرفعال ---

def test_inactive_source_is_rejected_before_fetch(monkeypatch) -> None:
    db = TestingSession()
    try:
        src = _source(db, "off-src", active=False)
        calls: list[str] = []
        _wire(monkeypatch, _items("off-src", 3), calls)

        with pytest.raises(ValueError, match="inactive"):
            _run(source_name="off-src", db=db)

        assert calls == []                                   # هیچ درخواست خارجی
        assert db.query(Document).count() == 0
        assert db.get(Source, src.id).active is False        # وضعیت DB تغییر نکرد
    finally:
        db.close()


def test_inactive_source_is_404_over_api(client: TestClient, monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "off-api", active=False)
    finally:
        db.close()
    calls: list[str] = []
    _wire(monkeypatch, [], calls)

    res = client.post("/api/ingest/bot", json={"source_name": "off-api", "limit": 1})
    assert res.status_code == 404
    assert "inactive" in res.json()["detail"]
    assert calls == []


# --- بخش سوم/چهارم: توقف کنترل‌شده ---

def test_stop_before_first_item_skips_fetch(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "stop-early")
        calls: list[str] = []
        _wire(monkeypatch, _items("stop-early", 3), calls)
        _stop_now()

        metrics = _run(source_name="stop-early", db=db)

        assert metrics.stopped is True
        assert metrics.fetched == 0 and metrics.stored == 0
        assert calls == []                       # توقف پیش از هر fetch شناخته شد
        assert db.query(Document).count() == 0
        assert metrics.sources_ok == 0
        assert metrics.by_source["stop-early"].ok is False
    finally:
        db.close()


def test_stop_after_two_items_keeps_partial_metrics(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "stop-mid")
        _wire(monkeypatch, _items("stop-mid", 5))
        real_deliver = runner_module.deliver
        delivered: list[int] = []

        def deliver_then_stop(*args, **kwargs):  # noqa: ANN002, ANN003
            result = real_deliver(*args, **kwargs)
            delivered.append(1)
            if len(delivered) == 2:
                _stop_now()  # درخواست توقف بین آیتم‌ها می‌رسد
            return result

        monkeypatch.setattr(runner_module, "deliver", deliver_then_stop)
        metrics = _run(source_name="stop-mid", db=db)
        sm = metrics.by_source["stop-mid"]

        assert metrics.stopped is True
        assert metrics.fetched == 5 and sm.fetched == 5
        assert metrics.stored == 2 and sm.stored == 2
        assert sum(sm.by_priority.values()) == 2
        assert sm.duplicates == 0
        assert metrics.sources_ok == 0 and sm.ok is False   # کامل جلوه نمی‌کند
        assert db.query(Document).count() == 2              # اسناد قبلی حذف نشدند
        assert sm.duration_ms is not None
    finally:
        db.close()


def test_stop_file_can_be_removed_and_runs_again(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "stop-resume")
        _wire(monkeypatch, _items("stop-resume", 4))

        _stop_now()
        assert runner_module.should_stop() is True
        first = _run(source_name="stop-resume", db=db)
        assert first.stopped is True and first.stored == 0

        _clear_stop()
        assert runner_module.should_stop() is False
        assert runner_module.should_stop() is False  # تکرار بررسی بی‌خطر است
        second = _run(source_name="stop-resume", db=db)
        assert second.stopped is False and second.stored == 4
        assert first.stored + second.stored == db.query(Document).count()
    finally:
        db.close()


def test_api_survives_stopped_run(client: TestClient, monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "stop-api")
    finally:
        db.close()
    _wire(monkeypatch, _items("stop-api", 3))

    _stop_now()
    stopped = client.post("/api/ingest/bot", json={"source_name": "stop-api", "limit": 1})
    assert stopped.status_code == 200
    body = stopped.json()
    assert body["stopped"] is True and body["stored"] == 0

    _clear_stop()
    resumed = client.post("/api/ingest/bot", json={"source_name": "stop-api", "limit": 1})
    assert resumed.status_code == 200
    assert resumed.json()["stopped"] is False
    assert resumed.json()["stored"] == 3       # اپلیکیشن و قفل سالم مانده‌اند


def test_job_keeps_partial_result_on_stop(client: TestClient, monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "stop-job")
    finally:
        db.close()
    _wire(monkeypatch, _items("stop-job", 5))
    monkeypatch.setattr(jobs_module, "get_session_factory", lambda: TestingSession)

    real_deliver = runner_module.deliver
    delivered: list[int] = []

    def deliver_then_stop(*args, **kwargs):  # noqa: ANN002, ANN003
        result = real_deliver(*args, **kwargs)
        delivered.append(1)
        if len(delivered) == 2:
            _stop_now()
        return result

    monkeypatch.setattr(runner_module, "deliver", deliver_then_stop)

    res = client.post("/api/ingest/jobs",
                      json={"source_name": "stop-job", "limit": 1,
                            "max_items_per_source": 4})
    assert res.status_code == 202, res.text
    job = client.get(f"/api/ingest/jobs/{res.json()['id']}").json()

    assert job["status"] == "partial"                 # هرگز completed ادعا نمی‌شود
    assert job["message"].startswith("stopped: partial run")
    assert job["spec"]["max_items_per_source"] == 4   # سقف در spec حفظ شد
    assert job["result"]["stopped"] is True
    assert job["result"]["fetched"] == 5
    assert job["result"]["stored"] == 2
    assert job["result"]["by_source"]["stop-job"]["stored"] == 2
    db = TestingSession()
    try:
        assert db.query(Document).count() == 2        # اسناد ذخیره‌شده باقی ماندند
    finally:
        db.close()


def test_job_without_cap_keeps_old_spec_shape(client: TestClient, monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "job-old")
    finally:
        db.close()
    _wire(monkeypatch, _items("job-old", 2))
    monkeypatch.setattr(jobs_module, "get_session_factory", lambda: TestingSession)

    res = client.post("/api/ingest/jobs", json={"source_name": "job-old", "limit": 1})
    assert res.status_code == 202, res.text
    job = client.get(f"/api/ingest/jobs/{res.json()['id']}").json()
    assert job["spec"] == {"source_name": "job-old", "limit": 1}
    assert job["status"] == "completed"
    assert job["result"]["stopped"] is False


# --- گزارش: اجرای متوقف‌شده ناقص می‌ماند ---

def test_daily_report_marks_partial_and_skipped_items() -> None:
    from datetime import UTC, datetime

    from source_bot.report import build_daily_report

    stats = {"ok": False, "fetch_ok": True, "fetch_attempts": 1, "fetched": 5,
             "items_skipped_limit": 2, "stored": 2, "duplicates": 0,
             "rejected_keyless": 0, "by_priority": {"P0": 1, "P1": 1},
             "pending": 0, "ai_used": 0, "ai_fallback": 0, "duration_ms": 10}
    record = {
        "at": datetime(2026, 10, 18, 10, tzinfo=UTC), "status": "partial",
        "message": "stopped: partial run",
        "result": {
            "sources_checked": 1, "sources_ok": 0, "sources_failed": {},
            "fetched": 5, "stored": 2, "duplicates": 0,
            "items_skipped_limit": 2, "stopped": True,
            "by_priority": {"P0": 1, "P1": 1}, "ai_used": 0, "ai_fallback": 0,
            "by_source": {"stop-src": stats},
        },
    }

    report = build_daily_report([record], day="2026-10-18")
    row = report["sources"][0]

    assert row["partial_runs"] == 1 and row["ok_runs"] == 0
    assert row["items_skipped_limit"] == 2 and row["fetched"] == 5
    assert report["items_skipped_limit"] == 2


# --- بخش پنجم: بیشینهٔ تلاش‌های شبکه (بدون تغییر رفتار) ---

class _Resp:
    def __init__(self, status: int, *, url: str, headers: dict | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}
        self.content = b"x"
        self.text = "x"
        self.url = url
        self.request = httpx.Request("GET", url)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=self.request, response=self)


def _fake_async_client(calls: list[str], status: int):
    class Client:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):  # noqa: ANN002
            return False

        async def get(self, url, headers=None):  # noqa: ANN001
            calls.append(url)
            return _Resp(status, url=url)

    return Client


def test_rss_adapter_retries_exactly_once_on_5xx(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(calls, 500))

    async def no_sleep(_seconds):  # noqa: ANN001
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(RSSFetcher().fetch(url="https://public.test/feed"))
    assert len(calls) == 2  # 1 + یک retry داخلی


def test_runner_retries_per_attempt_with_backoff(monkeypatch) -> None:
    db = TestingSession()
    try:
        _source(db, "retry-src")
        calls: list[str] = []
        sleeps: list[float] = []

        async def failing_fetch(plan, settings):  # noqa: ANN001
            calls.append(plan.url or "")
            raise RuntimeError("down")

        async def fake_sleep(seconds):  # noqa: ANN001
            sleeps.append(seconds)

        monkeypatch.setattr(runner_module, "_fetch_plan", failing_fetch)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "2")
        monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")

        metrics = _run(source_name="retry-src", db=db)
        sm = metrics.by_source["retry-src"]
        assert len(calls) == 3                       # max_retries=2 → 3 تلاش
        assert sm.fetch_attempts == 3
        assert sleeps == [2.0, 4.0]                  # 2×(attempt+1)، بدون jitter
        assert "retry-src" in metrics.sources_failed
        assert db.query(Document).count() == 0
    finally:
        db.close()


def test_fetch_url_retry_is_bounded(monkeypatch) -> None:
    from domains.news import source_verify

    calls: list[str] = []

    class Client:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):  # noqa: ANN002
            return False

        def get(self, url):
            calls.append(url)
            return _Resp(500, url=url)

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr(source_verify.time, "sleep", lambda _seconds: None)
    res = source_verify.fetch_url("https://public.test/page")
    assert res.ok is False and res.error_kind == "http_5xx"
    assert len(calls) == source_verify.MAX_RETRIES + 1  # 1 + MAX_RETRIES


def test_rest_json_429_is_not_retried(monkeypatch) -> None:
    from source_bot.adapters.rest_json import RestJsonAdapter

    calls: list[str] = []
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(calls, 429))
    res = asyncio.run(RestJsonAdapter(timeout=5).fetch(url="https://public.test/api"))
    assert res.status == "http_error" and res.detail == "http_429 rate limited"
    assert len(calls) == 1  # 429 هرگز retry نمی‌شود

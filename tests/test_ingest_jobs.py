"""Ingestion background jobs (Phase 2) — sqlite ایزوله، بدون شبکه یا DB واقعی.

اجرای Job در همان پروسه (BackgroundTasks) ولی وضعیت/نتیجه در JobRun ذخیره می‌شود.
transportها ساختگی‌اند: `_fetch_plan` و `get_gateway` هرگز واقعی صدا زده نمی‌شوند.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database import models as _models
from backend.database.models.job import JobRun
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot import jobs as jobs_module
from tests.conftest import TestingSession

LEVELS = ("P0", "P1", "P2", "P3", "P4")
BAD_FEED = "https://bad.test/rss"


def _mk_source(name: str, feed: str) -> None:
    db = TestingSession()
    try:
        db.add(Source(name=name, collection_method="rss", type="rss", feed_url=feed))
        db.commit()
    finally:
        db.close()


def _fetch(*, fail_on: str | None = None):
    """transport ساختگی: یک آیتم کامل برای منبع سالم، خطا برای منبع خراب."""
    async def _fake(plan, settings):
        if fail_on and fail_on in (plan.url or ""):
            raise RuntimeError("source down")
        return ([RawItem(title="Triage dispatch", url=f"{plan.url}/1",
                         raw_text="ward logistics update " * 20,
                         raw_payload='{"title": "Triage dispatch"}')], "", {})
    return _fake


def _wire(monkeypatch, fetch, *, ai: bool = False) -> None:
    """محیط ایزوله: بدون شبکه، بدون retry/sleep، session آزمایشی، AI خاموش."""
    from source_bot import runner as runner_module

    monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "0")
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "true" if ai else "false")
    monkeypatch.setattr(runner_module, "_fetch_plan", fetch)
    monkeypatch.setattr(jobs_module, "get_session_factory", lambda: TestingSession)


def _post_job(client: TestClient, body: dict) -> dict:
    res = client.post("/api/ingest/jobs", json=body)
    assert res.status_code == 202, res.text
    return res.json()


def _get_job(client: TestClient, job_id: str) -> dict:
    res = client.get(f"/api/ingest/jobs/{job_id}")
    assert res.status_code == 200, res.text
    return res.json()


def test_start_job_returns_id_without_waiting(client: TestClient, monkeypatch) -> None:
    """پاسخ فوری با شناسه و وضعیت pending؛ اجرای واقعی بعد از پاسخ انجام می‌شود."""
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fetch())

    body = _post_job(client, {"source_name": "job-src", "limit": 5})
    assert body["status"] == "pending"  # پاسخ پیش از اجرای Job ساخته شده است
    assert body["job_name"] == "ingest"
    assert body["spec"] == {"source_name": "job-src", "limit": 5}
    assert uuid.UUID(body["id"])
    assert body["finished_at"] is None and body["result"] is None

    # و کار بعد از پاسخ کامل شده است
    assert _get_job(client, body["id"])["status"] == "completed"


def test_job_completes_and_records_stats(client: TestClient, monkeypatch) -> None:
    """اجرای موفق: وضعیت completed + آمار و اولویت Phase 1 حفظ می‌شود."""
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fetch())

    jid = _post_job(client, {"source_name": "job-src"})["id"]
    body = _get_job(client, jid)
    assert body["status"] == "completed"
    result = body["result"]
    assert result["sources_ok"] == 1 and result["sources_failed"] == {}
    assert (result["fetched"], result["stored"], result["duplicates"]) == (1, 1, 0)
    assert body["started_at"] is not None and body["finished_at"] is not None
    assert body["duration_ms"] is not None and body["duration_ms"] >= 0
    assert "stored=1" in body["message"]

    db = TestingSession()
    try:
        doc = db.query(_models.Document).one()
        assert doc.ingestion_priority in LEVELS
        assert doc.priority_source == "rules"
    finally:
        db.close()

    # Job تمام‌شده مانع Job بعدی نیست
    assert _post_job(client, {"source_name": "job-src"})["status"] == "pending"


def test_partial_status_when_one_source_fails(client: TestClient, monkeypatch) -> None:
    """یک منبع خراب + یک منبع سالم -> partial با آمار مستقل هر منبع."""
    _mk_source("good-src", "https://good.test/rss")
    _mk_source("bad-src", BAD_FEED)
    _wire(monkeypatch, _fetch(fail_on=BAD_FEED))

    jid = _post_job(client, {"limit": 10})["id"]
    body = _get_job(client, jid)
    assert body["status"] == "partial"
    assert body["result"]["sources_ok"] == 1
    assert list(body["result"]["sources_failed"]) == ["bad-src"]
    assert body["result"]["stored"] == 1


def test_all_sources_failed_is_failed_not_partial(client: TestClient, monkeypatch) -> None:
    """وقتی هیچ منبعی موفق نبود وضعیت failed است، نه partial."""
    _mk_source("bad-src", BAD_FEED)
    _wire(monkeypatch, _fetch(fail_on=BAD_FEED))

    body = _get_job(client, _post_job(client, {"limit": 10})["id"])
    assert body["status"] == "failed"
    assert body["result"]["sources_ok"] == 0 and body["result"]["stored"] == 0


def test_concurrent_job_rejected_409(client: TestClient) -> None:
    """Job فعال موجود -> 409 و بدون اجرای موازی."""
    db = TestingSession()
    try:
        db.add(JobRun(job_name="ingest", source="api", status="pending", message="accepted"))
        db.commit()
    finally:
        db.close()

    res = client.post("/api/ingest/jobs", json={"limit": 5})
    assert res.status_code == 409
    assert "already active" in res.json()["detail"]
    db = TestingSession()
    try:
        assert db.query(JobRun).count() == 1  # Job دوم ثبت نشد
    finally:
        db.close()


def test_claim_prevents_second_execution(monkeypatch) -> None:
    """claim اتمیک: اجرای دوباره‌ی همان Job داده تکراری ذخیره نمی‌کند."""
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fetch())

    db = TestingSession()
    try:
        jid = jobs_module.create_job(db, spec={"source_name": "job-src", "limit": 5}).id
    finally:
        db.close()

    asyncio.run(jobs_module.run_job(jid))
    asyncio.run(jobs_module.run_job(jid))  # بار دوم: claim رد می‌شود
    db = TestingSession()
    try:
        assert db.query(_models.Document).count() == 1
        assert db.get(JobRun, jid).status == "completed"
    finally:
        db.close()


def test_recovery_marks_interrupted_jobs_failed(client: TestClient) -> None:
    """بعد از restart هیچ Job نیمه‌کاره‌ای در running/pending نمی‌ماند."""
    db = TestingSession()
    try:
        db.add_all([
            JobRun(job_name="ingest", source="api", status="pending"),
            JobRun(job_name="ingest", source="api", status="running"),
            JobRun(job_name="ingest", source="api", status="completed",
                   finished_at=datetime.now(UTC)),
            JobRun(job_name="other", source="n8n", status="received"),
        ])
        db.commit()
        assert jobs_module.recover_interrupted_jobs(db) == 2

        ingest = db.query(JobRun).filter_by(job_name="ingest").all()
        assert sorted(r.status for r in ingest) == ["completed", "failed", "failed"]
        for r in ingest:
            if r.status == "failed":
                assert r.message == jobs_module.INTERRUPTED_MESSAGE
                assert r.finished_at is not None
        assert db.query(JobRun).filter_by(job_name="other").one().status == "received"
    finally:
        db.close()

    # و بعد از recovery، Job جدید پذیرفته می‌شود (قفل فعلی وجود ندارد)
    db = TestingSession()
    try:
        assert jobs_module.create_job(db, spec={"limit": 5}).status == "pending"
    finally:
        db.close()


def test_failed_job_keeps_stored_documents_and_priority(client: TestClient,
                                                        monkeypatch) -> None:
    """خطای بعدی Job، اسناد خام و اولویت ذخیره‌شده را از بین نمی‌برد."""
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fetch())
    assert _get_job(client, _post_job(client, {"source_name": "job-src"})["id"])[
        "status"] == "completed"

    from source_bot import runner as runner_module

    def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(runner_module, "due_sources", _boom)
    body = _get_job(client, _post_job(client, {"limit": 5})["id"])
    assert body["status"] == "failed" and body["result"] is None

    db = TestingSession()
    try:
        doc = db.query(_models.Document).one()
        assert doc.raw_payload and doc.retrieved_at
        assert doc.ingestion_priority in LEVELS
    finally:
        db.close()


def test_unexpected_error_message_has_no_secret(client: TestClient, monkeypatch) -> None:
    """پیام خطای Job فقط نوع خطاست؛ متن خطا (که می‌تواند راز داشته باشد) ذخیره نمی‌شود."""
    _wire(monkeypatch, _fetch())
    from source_bot import runner as runner_module

    def _boom(*args, **kwargs):
        raise Exception("postgresql://user:supersecret@db/globalintelligence")

    monkeypatch.setattr(runner_module, "due_sources", _boom)
    body = _get_job(client, _post_job(client, {"limit": 5})["id"])
    assert body["status"] == "failed"
    assert body["message"] == "Exception"
    assert "supersecret" not in body["message"]


def test_locked_run_marks_job_failed_with_safe_message(client: TestClient,
                                                       monkeypatch) -> None:
    """قفل اجرای هم‌زمان ربات -> Job ناموفق با پیام ثابت و امن (بدون جزئیات)."""
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fetch())
    from source_bot import runner as runner_module

    monkeypatch.setattr(runner_module, "_acquire_lock", lambda: False)
    body = _get_job(client, _post_job(client, {"source_name": "job-src"})["id"])
    assert body["status"] == "failed"
    assert body["message"] == "another ingestion run is already active"


def test_job_never_uses_live_ai(client: TestClient, monkeypatch) -> None:
    """AI روشن اما Gateway در دسترس نیست: Job کامل می‌شود و اولویت از قواعد می‌ماند."""
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fetch(), ai=True)

    def _no_gateway():
        raise AssertionError("AI gateway must not be reached")

    monkeypatch.setattr("backend.ai.gateway.get_gateway", _no_gateway)
    body = _get_job(client, _post_job(client, {"source_name": "job-src"})["id"])
    assert body["status"] == "completed"
    assert body["result"]["ai_used"] == 0
    assert body["result"]["ai_fallback"] == 1  # تلاش AI رد شد و fallback شد

    db = TestingSession()
    try:
        assert db.query(_models.Document).one().priority_source == "rules"
    finally:
        db.close()


def _fixed_fetch():
    """سه ورودی ثابت و کامل؛ همان ترتیب در هر دو Job."""
    items = [RawItem(title=f"Triage dispatch {i}", url=f"https://example.test/{i}",
                     raw_text="ward logistics update " * 20,
                     raw_payload=f'{{"id": {i}}}',
                     metadata={"mock": False, "text_status": "full_text_extracted",
                               "identity_text": f"dispatch summary {i}"})
             for i in (1, 2, 3)]

    async def _fake(plan, settings):
        return (list(items), "", {})
    return _fake


def _docs_snapshot() -> tuple[dict, list]:
    from backend.database.models.article import Article
    from backend.database.models.document import Document

    db = TestingSession()
    try:
        db.expire_all()
        docs = {d.url: (d.hash, d.content_hash, d.revision, d.retrieved_at,
                        d.duplicate_status, d.doc_metadata,
                        d.ingestion_priority, d.priority_reason)
                for d in db.query(Document).all()}
        arts = sorted((a.document_id, a.duplicate_cluster)
                      for a in db.query(Article).all())
        return docs, arts
    finally:
        db.close()


def test_two_jobs_fixed_input_persist_duplicates_and_keep_first_report(
        client: TestClient, monkeypatch) -> None:
    """دو Job مستقل با ورودی ثابت: گذر دوم duplicate می‌شود، گزارش اول دست‌نخورده."""
    import json

    from backend.core.config import get_settings
    from backend.database.models.job import JobRun
    from source_bot.report import build_daily_report, job_records

    monkeypatch.setenv("DEDUP_ON_INGEST", "true")
    get_settings.cache_clear()
    _mk_source("job-src", "https://example.test/rss")
    _wire(monkeypatch, _fixed_fetch())

    first = _post_job(client, {"source_name": "job-src"})
    body1 = _get_job(client, first["id"])
    result1 = body1["result"]
    assert body1["status"] == "completed"
    assert (result1["stored"], result1["duplicates"]) == (3, 0)
    assert result1["by_source"]["job-src"]["stored"] == 3
    assert result1["by_source"]["job-src"]["duplicates"] == 0

    docs1, arts1 = _docs_snapshot()
    assert len(docs1) == 3 and len(arts1) == 3
    assert {row[2] for row in docs1.values()} == {1}
    for row in docs1.values():
        meta = json.loads(row[5])
        assert meta["mock"] is False and meta["text_status"] == "full_text_extracted"
        assert "dedup_cluster" in meta  # dedup پس از ingest از مسیر واقعی Job اجرا شد
    assert {a[1] for a in arts1} == {None}
    assert {row[4] for row in docs1.values()} == {"new"}

    db = TestingSession()
    try:
        payload1 = db.get(JobRun, uuid.UUID(first["id"])).payload
    finally:
        db.close()

    second = _post_job(client, {"source_name": "job-src"})
    body2 = _get_job(client, second["id"])
    result2 = body2["result"]
    assert second["id"] != first["id"]
    assert body2["status"] == "completed"
    assert (result2["stored"], result2["duplicates"]) == (0, 3)
    assert result2["by_source"]["job-src"]["duplicates"] == 3
    assert body2["finished_at"] is not None

    docs2, arts2 = _docs_snapshot()
    assert docs2 == docs1 and arts2 == arts1  # هیچ ردیف/خوشه/متادیتایی بازنویسی نشد
    assert {row[2] for row in docs2.values()} == {1}  # revision دست‌نخورده

    db = TestingSession()
    try:
        runs = db.query(JobRun).order_by(JobRun.started_at).all()
        assert len(runs) == 2
        assert {r.status for r in runs} == {"completed"}
        assert db.get(JobRun, uuid.UUID(first["id"])).payload == payload1  # گزارش اول بازنویسی نشد
        report = build_daily_report(job_records(db))
    finally:
        db.close()
    assert report["runs"]["total"] == 2 and report["runs"]["with_result"] == 2
    assert len(report["sources"]) == 1
    row = report["sources"][0]
    assert (row["runs"], row["stored"], row["duplicates"]) == (2, 3, 3)


def test_deliver_false_counts_real_duplicate_only(client: TestClient, monkeypatch) -> None:
    """ردیف URL‌دار بدون عنوان/متن (content_hash=NULL) از پیش‌بررسی رد می‌شود؛
    store_item شناسه را می‌بیند و False برمی‌گرداند — شمارنده duplicate فقط برای همین."""
    from backend.database.models.document import Document

    _mk_source("job-src", "https://example.test/rss")

    async def _link_only(plan, settings):
        return ([RawItem(title=None, url="https://example.test/link-only",
                         raw_text=None, raw_payload=None)], "", {})

    _wire(monkeypatch, _link_only)

    body1 = _get_job(client, _post_job(client, {"source_name": "job-src"})["id"])
    assert (body1["result"]["stored"], body1["result"]["duplicates"]) == (1, 0)

    db = TestingSession()
    try:
        doc = db.query(Document).one()
        assert doc.hash is not None and doc.content_hash is None
        assert doc.revision == 1 and doc.duplicate_status == "new"
    finally:
        db.close()

    body2 = _get_job(client, _post_job(client, {"source_name": "job-src"})["id"])
    assert (body2["result"]["stored"], body2["result"]["duplicates"]) == (0, 1)
    assert body2["result"]["by_source"]["job-src"]["rejected_keyless"] == 0

    db = TestingSession()
    try:
        assert db.query(Document).count() == 1
        assert db.get(JobRun, uuid.UUID(body2["id"])).status == "completed"
    finally:
        db.close()


def test_job_not_found_and_invalid_id(client: TestClient) -> None:
    assert client.get("/api/ingest/jobs/not-a-uuid").status_code == 400
    assert client.get(f"/api/ingest/jobs/{uuid.uuid4()}").status_code == 404

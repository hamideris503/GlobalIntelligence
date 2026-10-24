"""Stage91 - screening review queue + dispatch operations view.

Offline only: in-memory SQLite, no network, no real runtimes.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.ai.dispatch.service import DispatchService, task_key
from backend.ai.local_screening import review
from backend.core.config import get_settings
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.document import Document
from backend.database.models.source import Source
from backend.main import app
from tests.conftest import TestingSession


def _screening(*, decision, codes, p0: bool = False, route: str = "KEV_LAYA") -> dict:
    return {
        "scope_rule_version": "relevance_scope_v2",
        "route": route,
        "decision": decision,
        "reason_codes": list(codes),
        "fallback_used": "AI_FALLBACK" in codes,
        "p0_p1_safeguard": p0,
        "downstream_dispatch": decision is True,
        "kev": {"status": "ok", "p_true": 0.9, "relevant": decision},
        "laya": {"status": "ok", "p_true": 0.8, "relevant": decision},
        "provenance": {"settings": {"kev_enabled": True, "laya_enabled": True}},
    }


def _article(
    db,
    *,
    title: str = "Oil rises",
    priority: str = "P2",
    status: str = "done",
    screening: dict | None = None,
    skipped: bool = False,
    retrieved_at: datetime | None = None,
) -> Article:
    src = Source(
        name=f"src-{uuid.uuid4().hex[:8]}",
        domain=f"{uuid.uuid4().hex[:8]}.test",
        type="rss",
        active=True,
    )
    db.add(src)
    db.flush()
    doc = Document(
        source_id=src.id,
        title=title,
        raw_text="Crude oil prices rose after the OPEC decision.",
        url=f"https://example.test/{uuid.uuid4().hex}",
        ingestion_priority=priority,
        priority_source="rules",
    )
    db.add(doc)
    db.flush()
    meta: dict = {}
    if skipped:
        meta = {"skipped_ai": "low_priority_gate"}
    elif screening is not None:
        meta = {"provider": "mock", "model": "m", "local_screening": screening}
    article = Article(
        document_id=doc.id,
        title=title,
        source_name=src.name,
        classification_status=status,
        classification_meta=json.dumps(meta, ensure_ascii=False),
        retrieved_at=retrieved_at or datetime.now(UTC),
    )
    db.add(article)
    db.commit()
    return article


def _dispatch(db, article_id, task: str = "event_extraction", **kwargs) -> ArticleDispatch:
    row = ArticleDispatch(
        article_id=article_id,
        task_name=task_key(task),
        status=kwargs.pop("status", "pending"),
        attempts=kwargs.pop("attempts", 0),
        **kwargs,
    )
    db.add(row)
    db.commit()
    return row


def _queue(client: TestClient, **params):
    res = client.get("/api/screening/queue", params=params)
    assert res.status_code == 200, res.text
    return res.json()


# --- queue eligibility ------------------------------------------------------

def test_queue_returns_only_flagged_records(client: TestClient) -> None:
    db = TestingSession()
    try:
        clean = _article(db, title="clean", screening=_screening(
            decision=True, codes=["BOTH_RELEVANT"]))
        flagged = _article(db, title="flagged", screening=_screening(
            decision=None, codes=["DISAGREEMENT", "AI_UNAVAILABLE"]))
    finally:
        db.close()

    body = _queue(client)
    ids = [item["article_id"] for item in body["items"]]
    assert ids == [str(flagged.id)]
    assert str(clean.id) not in ids
    assert body["items"][0]["review_required"] is True


def test_every_review_code_marker_matches_python(client: TestClient) -> None:
    """The SQL LIKE prefilter and the Python reason list use the same codes."""
    db = TestingSession()
    try:
        created = {}
        for code in sorted(review.REVIEW_CODES):
            created[code] = _article(db, title=code, screening=_screening(
                decision=None, codes=[code],
                p0=code == "P0_P1_SAFEGUARD"))
        for prefix in review.REVIEW_PREFIXES:
            code = f"{prefix}:ValueError"
            created[code] = _article(db, title=code, screening=_screening(
                decision=None, codes=[code]))
    finally:
        db.close()

    body = _queue(client, page_size=100)
    by_title = {item["title"]: item for item in body["items"]}
    for code in created:
        assert code in by_title, code
        assert code in by_title[code]["review_reasons"], code
        assert by_title[code]["screening_status"] == "pending"


def test_priority_is_not_review_required(client: TestClient) -> None:
    db = TestingSession()
    try:
        _article(db, title="p0-clean", priority="P0", screening=_screening(
            decision=True, codes=["BOTH_RELEVANT"]))
        _article(db, title="p0-guard", priority="P0", screening=_screening(
            decision=None, codes=["P0_P1_SAFEGUARD", "PRIORITY_REVIEW"],
            p0=True))
    finally:
        db.close()

    queue = _queue(client)
    assert [i["title"] for i in queue["items"]] == ["p0-guard"]
    assert queue["items"][0]["priority"] == "P0"

    all_p0 = _queue(client, review_required="false", p0_p1="true")
    titles = {i["title"]: i for i in all_p0["items"]}
    assert set(titles) == {"p0-clean"}
    assert titles["p0-clean"]["priority"] == "P0"
    assert titles["p0-clean"]["review_required"] is False


def test_disagreement_visible_with_reason(client: TestClient) -> None:
    db = TestingSession()
    try:
        _article(db, screening=_screening(
            decision=None, codes=["DISAGREEMENT", "AI_FALLBACK"]))
    finally:
        db.close()
    item = _queue(client)["items"][0]
    assert "DISAGREEMENT" in item["review_reasons"]
    assert item["screening"]["reason_codes"] == ["DISAGREEMENT", "AI_FALLBACK"]
    assert item["screening"]["route"] == "KEV_LAYA"


def test_low_margin_and_input_limits_visible(client: TestClient) -> None:
    db = TestingSession()
    try:
        _article(db, title="margin", screening=_screening(
            decision=None, codes=["LOW_MARGIN", "AI_ABSTAINED"]))
        _article(db, title="too-long", screening=_screening(
            decision=None, codes=["LAYA_INPUT_TOO_LONG"], route="LAYA"))
        _article(db, title="truncated", screening=_screening(
            decision=None, codes=["PAIR_INVALID:KEV_TRUNCATED"], route="KEV_LAYA"))
    finally:
        db.close()
    by_title = {i["title"]: i for i in _queue(client)["items"]}
    assert "LOW_MARGIN" in by_title["margin"]["review_reasons"]
    assert "LAYA_INPUT_TOO_LONG" in by_title["too-long"]["review_reasons"]
    assert "PAIR_INVALID:KEV_TRUNCATED" in by_title["truncated"]["review_reasons"]


def test_pending_and_failed_screening_are_not_irrelevant(client: TestClient) -> None:
    db = TestingSession()
    try:
        _article(db, title="pending", status="pending")
        _article(db, title="failed", status="failed")
        _article(db, title="undecided", screening=_screening(
            decision=None, codes=["AI_UNAVAILABLE"]))
    finally:
        db.close()
    by_title = {i["title"]: i for i in _queue(client)["items"]}
    assert by_title["pending"]["screening_status"] == "missing"
    assert "CLASSIFICATION_PENDING" in by_title["pending"]["review_reasons"]
    assert "CLASSIFICATION_FAILED" in by_title["failed"]["review_reasons"]
    assert by_title["undecided"]["screening_status"] == "pending"
    assert "SCREENING_PENDING" in by_title["undecided"]["review_reasons"]
    # Nothing here is a clean "not relevant" outcome.
    assert all(i["screening_status"] != "not_relevant" for i in by_title.values())


def test_skipped_low_priority_is_outcome_not_review(client: TestClient) -> None:
    db = TestingSession()
    try:
        _article(db, title="skipped", priority="P4", skipped=True)
    finally:
        db.close()
    assert _queue(client)["items"] == []
    outcomes = _queue(client, review_required="false", screening="skipped")
    assert [i["title"] for i in outcomes["items"]] == ["skipped"]
    assert outcomes["items"][0]["screening_status"] == "skipped"
    assert outcomes["items"][0]["review_required"] is False


# --- acknowledgement --------------------------------------------------------

def test_ack_does_not_change_automated_decision(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db, screening=_screening(
            decision=None, codes=["LOW_MARGIN"]))
        original = json.loads(article.classification_meta)
        article_id = str(article.id)
    finally:
        db.close()

    res = client.post(f"/api/screening/review/{article_id}/ack", json={"note": "seen"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["review_acknowledged"] is True
    assert body["already_acknowledged"] is False
    assert body["human_review"]["note"] == "seen"

    db = TestingSession()
    try:
        fresh = db.get(Article, uuid.UUID(article_id))
        meta = json.loads(fresh.classification_meta)
    finally:
        db.close()
    assert meta["local_screening"] == original["local_screening"]
    assert meta["human_review"]["acknowledged"] is True

    queue = _queue(client)
    item = next(i for i in queue["items"] if i["article_id"] == article_id)
    assert item["screening"] == original["local_screening"]
    assert item["review_required"] is True  # still flagged, now acknowledged
    assert item["review_acknowledged"] is True


def test_ack_is_idempotent(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db, screening=_screening(
            decision=None, codes=["DISAGREEMENT"]))
        article_id = str(article.id)
    finally:
        db.close()

    first = client.post(f"/api/screening/review/{article_id}/ack", json={})
    second = client.post(f"/api/screening/review/{article_id}/ack", json={})
    assert first.status_code == second.status_code == 200
    assert first.json()["already_acknowledged"] is False
    assert second.json()["already_acknowledged"] is True
    assert first.json()["human_review"]["acknowledged_at"] == \
        second.json()["human_review"]["acknowledged_at"]

    db = TestingSession()
    try:
        meta = json.loads(db.get(Article, uuid.UUID(article_id)).classification_meta)
    finally:
        db.close()
    assert meta["human_review"]["acknowledged"] is True
    assert len([k for k in meta if k == "human_review"]) == 1


# --- auth / validation / pagination ----------------------------------------

def test_queue_and_ack_require_api_key() -> None:
    os.environ["API_KEY"] = "test-key-123"
    get_settings.cache_clear()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/api/screening/queue").status_code == 401
        assert client.get("/api/dispatch/jobs").status_code == 401
        assert client.post(
            f"/api/screening/review/{uuid.uuid4()}/ack", json={}
        ).status_code == 401
        assert client.post(f"/api/dispatch/{uuid.uuid4()}/retry").status_code == 401
    finally:
        os.environ["API_KEY"] = ""
        get_settings.cache_clear()


def test_pagination_is_bounded_and_stable(client: TestClient) -> None:
    db = TestingSession()
    try:
        now = datetime.now(UTC)
        for i in range(5):
            _article(db, title=f"r{i}", screening=_screening(
                decision=None, codes=["LOW_MARGIN"]),
                retrieved_at=now + timedelta(seconds=i))
    finally:
        db.close()

    first = _queue(client, page=1, page_size=2)
    second = _queue(client, page=2, page_size=2)
    assert len(first["items"]) == 2 and first["has_more"] is True
    assert {i["article_id"] for i in first["items"]}.isdisjoint(
        {i["article_id"] for i in second["items"]})
    assert [i["title"] for i in first["items"]] == ["r4", "r3"]
    assert [i["title"] for i in second["items"]] == ["r2", "r1"]
    assert client.get(
        "/api/screening/queue", params={"page_size": 101}
    ).status_code == 422
    assert client.get(
        "/api/screening/queue", params={"page": 0}
    ).status_code == 422


# --- dispatch operations ----------------------------------------------------

def test_dispatch_jobs_reflect_database(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db, title="dispatch-me", screening=_screening(
            decision=None, codes=["LOW_MARGIN"]))
        retry_at = datetime.now(UTC) + timedelta(minutes=5)
        _dispatch(db, article.id, status="retryable", attempts=2,
                  last_error="boom", next_retry_at=retry_at)
        _dispatch(db, article.id, task="claim_extraction", status="completed", attempts=1)
        article_id = str(article.id)
    finally:
        db.close()

    body = client.get("/api/dispatch/jobs").json()
    rows = {i["task"]: i for i in body["items"]}
    assert set(rows) == {"event_extraction", "claim_extraction"}
    retryable = rows["event_extraction"]
    assert retryable["article_id"] == article_id
    assert retryable["article_url"].startswith("https://example.test/")
    assert retryable["task_version"] == "1"
    assert retryable["status"] == "retryable" and retryable["attempts"] == 2
    assert retryable["last_error"] == "boom"
    assert retryable["can_retry"] is True
    assert retryable["next_retry_at"] is not None
    assert retryable["review_required"] is True
    assert rows["claim_extraction"]["can_retry"] is False   # completed != retryable
    assert rows["claim_extraction"]["review_required"] is True

    filtered = client.get(
        "/api/dispatch/jobs", params={"status": "completed"}).json()["items"]
    assert [i["task"] for i in filtered] == ["claim_extraction"]


def test_dispatch_jobs_filter_task_priority_and_review(client: TestClient) -> None:
    db = TestingSession()
    try:
        p0 = _article(db, priority="P0", screening=_screening(
            decision=None, codes=["P0_P1_SAFEGUARD"], p0=True))
        clean = _article(db, priority="P2", screening=_screening(
            decision=True, codes=["BOTH_RELEVANT"]))
        _dispatch(db, p0.id, task="screening", status="pending")
        _dispatch(db, clean.id, task="screening", status="pending")
    finally:
        db.close()

    by_priority = client.get(
        "/api/dispatch/jobs", params={"p0_p1": "true"}).json()["items"]
    assert [i["priority"] for i in by_priority] == ["P0"]
    by_review = client.get(
        "/api/dispatch/jobs", params={"review_required": "true"}).json()["items"]
    assert [i["priority"] for i in by_review] == ["P0"]
    by_task = client.get(
        "/api/dispatch/jobs", params={"task": "screening"}).json()["items"]
    assert len(by_task) == 2
    assert client.get(
        "/api/dispatch/jobs", params={"task": "bogus"}).status_code == 422


def test_completed_dispatch_is_not_reenqueued(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db)
        row = _dispatch(db, article.id, status="completed", attempts=1)
        dispatch_id = str(row.id)
        article_id = str(article.id)
    finally:
        db.close()

    res = client.post(f"/api/dispatch/{dispatch_id}/retry")
    assert res.status_code == 409
    assert "completed" in res.json()["detail"]

    db = TestingSession()
    try:
        fresh = db.get(ArticleDispatch, uuid.UUID(dispatch_id))
        assert fresh.status == "completed"
        assert fresh.attempts == 1
        rows = DispatchService(db).for_article(uuid.UUID(article_id))
        assert len(rows) == 1
    finally:
        db.close()


def test_retry_makes_row_claimable_without_resetting_attempts(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db)
        row = _dispatch(
            db, article.id, status="retryable", attempts=1,
            last_error="temporary", next_retry_at=datetime.now(UTC) + timedelta(hours=1),
        )
        dispatch_id = str(row.id)
        assert DispatchService(db).claimable("event_extraction") == []
    finally:
        db.close()

    res = client.post(f"/api/dispatch/{dispatch_id}/retry")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "retryable"
    assert body["attempts"] == 1  # not reset, not incremented

    db = TestingSession()
    try:
        # The existing claim query now sees the row as due; no new row exists.
        claimable = DispatchService(db).claimable("event_extraction")
        assert [str(r.id) for r in claimable] == [dispatch_id]
        assert db.execute(
            select(func.count()).select_from(ArticleDispatch).where(
                ArticleDispatch.article_id == uuid.UUID(body["article_id"])
            )
        ).scalar_one() == 1
    finally:
        db.close()


def test_pending_retry_is_noop(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db)
        row = _dispatch(db, article.id, status="pending")
        dispatch_id = str(row.id)
    finally:
        db.close()
    res = client.post(f"/api/dispatch/{dispatch_id}/retry")
    assert res.status_code == 200
    assert res.json()["status"] == "pending"

    db = TestingSession()
    try:
        assert len(DispatchService(db).for_article(
            db.get(ArticleDispatch, uuid.UUID(dispatch_id)).article_id)) == 1
    finally:
        db.close()


def test_terminal_is_not_success(client: TestClient) -> None:
    db = TestingSession()
    try:
        article = _article(db)
        row = _dispatch(db, article.id, status="terminal", attempts=3,
                        last_error="max attempts reached")
        dispatch_id = str(row.id)
    finally:
        db.close()

    job = next(i for i in client.get("/api/dispatch/jobs").json()["items"]
               if i["dispatch_id"] == dispatch_id)
    assert job["status"] == "terminal"
    assert job["can_retry"] is False
    assert client.post(f"/api/dispatch/{dispatch_id}/retry").status_code == 409

    db = TestingSession()
    try:
        assert db.get(ArticleDispatch, uuid.UUID(dispatch_id)).status == "terminal"
    finally:
        db.close()


def test_missing_ids_return_safe_errors(client: TestClient) -> None:
    missing = uuid.uuid4()
    ack = client.post(f"/api/screening/review/{missing}/ack", json={})
    retry = client.post(f"/api/dispatch/{missing}/retry")
    assert ack.status_code == 404 and "not found" in ack.json()["detail"]
    assert retry.status_code == 404 and "not found" in retry.json()["detail"]
    assert client.post(
        "/api/screening/review/not-a-uuid/ack", json={}
    ).status_code == 422


def test_runtime_status_comes_from_backend(client: TestClient) -> None:
    from backend.api.routers import local_runtimes

    supervisor = local_runtimes._supervisor
    before = supervisor.status("kev").enabled
    try:
        supervisor.set_enabled("kev", True)
        body = client.get("/api/local-runtimes/status").json()
        assert body["kev"]["enabled"] is True
        assert body["kev"]["state"] == "ENABLED_NOT_LOADED"
        assert body["laya"]["state"] in ("DISABLED", "ENABLED_NOT_LOADED", "ERROR")
    finally:
        supervisor.set_enabled("kev", before)

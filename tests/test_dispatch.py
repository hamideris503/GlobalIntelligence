"""Stage89 — durable screening-to-analysis dispatch.

Offline only: mock AI Gateway / fake screeners, in-memory SQLite, no network.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.ai.dispatch.runner import recover_at_startup, run_once
from backend.ai.dispatch.service import (
    ANALYSIS_TASKS,
    ANALYSIS_VERSION,
    DispatchService,
    logical_task,
    task_key,
)
from backend.ai.local_screening import orchestrator as orch
from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from tests.conftest import TestingSession


def _article(db, *, body: str = "Crude oil prices rose after the OPEC decision.",
             done: bool = True, meta: dict | None = None) -> Article:
    src = Source(name=f"src-{uuid.uuid4().hex[:8]}", domain="d.local", type="rss", active=True)
    db.add(src)
    db.flush()
    doc = Document(source_id=src.id, title="Oil rises", raw_text=body,
                   url=f"https://example.test/{uuid.uuid4().hex}")
    db.add(doc)
    db.flush()
    art = Article(
        document_id=doc.id,
        title="Oil rises",
        summary="Crude oil prices rose today.",
        classification_status="done" if done else "pending",
        classification_meta=json.dumps(meta or {}),
    )
    db.add(art)
    db.commit()
    return art


def _count(db, article_id, task: str) -> int:
    return int(db.execute(
        select(func.count()).select_from(ArticleDispatch).where(
            ArticleDispatch.article_id == article_id,
            ArticleDispatch.task_name == task_key(task),
        )
    ).scalar_one())


# --- enqueue ---------------------------------------------------------------

def test_enqueue_is_idempotent_and_versioned() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        first = svc.ensure_dispatch(art.id, "event_extraction")
        second = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
        assert first.id == second.id
        assert first.task_name == f"event_extraction@v{ANALYSIS_VERSION}"
        assert logical_task(first.task_name) == "event_extraction"
        assert _count(db, art.id, "event_extraction") == 1
    finally:
        db.close()


def test_relevant_decision_enqueues_only_analysis_tasks() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        decision = orch.ScreeningDecision(route="KEV", relevant=True)
        DispatchService(db).enqueue_after_screening(art.id, decision)
        db.commit()
        assert _count(db, art.id, "event_extraction") == 1
        assert _count(db, art.id, "claim_extraction") == 1
        assert _count(db, art.id, "evidence_collection") == 1
        assert _count(db, art.id, "screening") == 0
    finally:
        db.close()


def test_pending_decision_creates_durable_screening_retry() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        decision = orch.ScreeningDecision(route="AI_GATEWAY", relevant=None,
                                          reason_codes=["AI_ABSTAINED"])
        DispatchService(db).enqueue_after_screening(art.id, decision)
        db.commit()
        assert _count(db, art.id, "screening") == 1
        assert _count(db, art.id, "event_extraction") == 0
        row = DispatchService(db).get_dispatch(art.id, "screening")
        assert row is not None and json.loads(row.meta)["screening_decision"] is None
    finally:
        db.close()


def test_negative_decision_suppresses_analysis_dispatch() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        DispatchService(db).enqueue_after_screening(
            art.id, orch.ScreeningDecision(route="KEV", relevant=False))
        db.commit()
        assert db.execute(select(func.count()).select_from(ArticleDispatch)).scalar_one() == 0
    finally:
        db.close()


# --- claims / retries -------------------------------------------------------

def test_claim_is_atomic() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
    finally:
        db.close()

    first = TestingSession()
    second = TestingSession()
    try:
        row = first.get(ArticleDispatch, row_id := row.id)
        other = second.get(ArticleDispatch, row_id)
        assert DispatchService(first).claim(row) is True
        assert DispatchService(second).claim(other) is False
        first.commit()
        assert row.attempts == 1
        assert row.status == "running"
    finally:
        first.close()
        second.close()


def test_retry_backoff_and_terminal_after_bounded_attempts() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()

        assert svc.claim(row) is True
        svc.mark_retryable(row, "transient failure")
        assert row.status == "retryable"
        assert row.next_retry_at is not None
        assert row.attempts == 1

        for _ in range(10):
            row.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            if not svc.claim(row):
                break
            svc.mark_retryable(row, "still failing")
        db.commit()
        assert row.status == "terminal"
        assert row.attempts == 3
        assert row.last_error is not None and "max attempts" in row.last_error
    finally:
        db.close()


def test_stale_running_is_recovered_without_losing_attempts() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
        assert svc.claim(row) is True
        row.updated_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()

        assert svc.recover_stale(stale_seconds=60) == 1
        db.commit()
        assert row.status == "retryable"
        assert row.attempts == 1
        assert row.next_retry_at is not None
    finally:
        db.close()


def test_stale_running_at_max_attempts_becomes_terminal() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
        row.status = "running"
        row.attempts = svc.settings.dispatch_max_attempts
        row.updated_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()

        assert svc.recover_stale(stale_seconds=60) == 1
        db.commit()
        assert row.status == "terminal"
        assert "max attempts" in (row.last_error or "")
    finally:
        db.close()


def test_ai_fallback_cannot_route_back_into_local_runtimes(monkeypatch) -> None:
    """Both local models off: the Gateway chain must exclude Kev/Laya."""
    import backend.ai.gateway as gateway_module
    from backend.ai.schemas.types import AIRequest, AIResponse

    captured: list[AIRequest] = []

    class _Gateway:
        async def generate(self, request: AIRequest) -> AIResponse:
            captured.append(request)
            return AIResponse(text="NO", provider="mock", model="m", is_mock=True)

    monkeypatch.setattr(gateway_module, "get_gateway", lambda: _Gateway())
    db = TestingSession()
    try:
        decision = asyncio.run(orch.screen_with_db(
            db, "Crude oil prices rose.", "P3"))
        assert decision.relevant is False
        assert captured and captured[0].metadata["exclude_local_providers"] is True
    finally:
        db.close()


def test_missing_dispatch_reenqueued_from_stored_decision() -> None:
    db = TestingSession()
    try:
        art = _article(db, meta={
            "local_screening": {"route": "KEV", "decision": True},
        })
        # All analysis tasks (Stage92: domain_routing + claim_independence added).
        assert recover_at_startup(db)["reenqueued"] == len(ANALYSIS_TASKS)
        assert _count(db, art.id, "domain_routing") == 1
        assert _count(db, art.id, "event_extraction") == 1
        assert _count(db, art.id, "claim_independence") == 1
        # idempotent: a second startup scan creates nothing new
        assert recover_at_startup(db)["reenqueued"] == 0
    finally:
        db.close()


# --- runner through the real extractors ------------------------------------

def test_runner_executes_existing_extractors_once() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        svc.ensure_dispatch(art.id, "claim_extraction")
        svc.ensure_dispatch(art.id, "graph_extraction")
        svc.ensure_dispatch(art.id, "evidence_collection")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="event_extraction"))
        db.refresh(art)
        assert outcome.completed == 1
        assert art.event_id is not None
        assert db.get(ArticleDispatch, row.id).status == "completed"

        outcome = asyncio.run(run_once(db, limit=5, task="claim_extraction"))
        assert outcome.completed == 1
        event = db.get(Event, art.event_id)
        assert event is not None and event.claims_extracted is True
        assert db.execute(select(func.count()).select_from(Claim)).scalar_one() >= 1

        outcome = asyncio.run(run_once(db, limit=5, task="graph_extraction"))
        assert outcome.completed == 1
        db.refresh(event)
        assert event.graph_extracted is True

        outcome = asyncio.run(run_once(db, limit=5, task="evidence_collection"))
        assert outcome.completed == 1
        claims = db.execute(select(Claim)).scalars().all()
        assert claims and all(c.evidence_extracted for c in claims)
    finally:
        db.close()


def test_runner_screening_retry_completes_and_enqueues_analysis(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):  # noqa: ANN001, ANN202
        return orch.ScreeningDecision(route="AI_GATEWAY", relevant=True,
                                      reason_codes=["AI_FALLBACK"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "AI_GATEWAY",
                                                     "decision": None}})
        row = DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="screening"))
        assert outcome.completed == 1
        db.refresh(row)
        assert row.status == "completed"
        assert _count(db, art.id, "event_extraction") == 1
        meta = json.loads(db.get(Article, art.id).classification_meta)
        assert meta["local_screening"]["decision"] is True
    finally:
        db.close()


def test_runner_retries_when_event_not_ready_and_terminalizes_permanent_error() -> None:
    db = TestingSession()
    try:
        art = _article(db, done=False)  # classification not done -> retryable
        DispatchService(db).ensure_dispatch(art.id, "event_extraction")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="event_extraction"))
        assert outcome.retryable == 1
        row = DispatchService(db).get_dispatch(art.id, "event_extraction")
        assert row is not None and row.status == "retryable"

        # missing article is permanent, not retried
        ghost = DispatchService(db).ensure_dispatch(uuid.uuid4(), "event_extraction")
        db.commit()
        outcome = asyncio.run(run_once(db, limit=5, task="event_extraction"))
        db.refresh(ghost)
        assert ghost.status == "terminal"
    finally:
        db.close()


# --- single entry point / precedence --------------------------------------

def test_legacy_master_switch_is_ignored(monkeypatch) -> None:
    from backend.ai.credentials_store import set_app_setting

    def forbidden(*args, **kwargs):  # noqa: ANN001, ANN202
        raise AssertionError("local runtime must not be called")

    monkeypatch.setattr(orch, "make_kev_caller", forbidden)
    monkeypatch.setattr(orch, "make_laya_caller", forbidden)

    db = TestingSession()
    try:
        set_app_setting(db, "local_screening_enabled", "true")  # legacy switch
        set_app_setting(db, "kev_local_screening_enabled", "false")
        set_app_setting(db, "laya_local_screening_enabled", "false")
        db.commit()

        async def fake_ai(text: str) -> dict:
            return {"relevant": True}

        decision = asyncio.run(
            orch.screen_with_db(db, "Crude oil prices rose.", "P3", ai_screen=fake_ai))
        assert decision.route == "AI_GATEWAY"
        assert decision.relevant is True
    finally:
        db.close()


def test_single_entry_point_syncs_supervisor_flags() -> None:
    from unittest.mock import MagicMock

    from backend.ai.credentials_store import set_app_setting

    db = TestingSession()
    try:
        set_app_setting(db, "kev_local_screening_enabled", "true")
        set_app_setting(db, "laya_local_screening_enabled", "false")
        db.commit()
        sup = MagicMock()
        sup.ensure_loaded.return_value = MagicMock()
        sup.ensure_loaded.return_value.state = MagicMock(value="ERROR")

        async def fake_ai(text: str) -> dict:
            return {"relevant": False}

        asyncio.run(orch.screen_with_db(
            db, "text", "P3", supervisor=sup, ai_screen=fake_ai,
            kev_caller=lambda t: {"status": "unavailable"},
            laya_caller=lambda t: {"status": "unavailable"},
        ))
        sup.set_enabled.assert_any_call("kev", True)
        sup.set_enabled.assert_any_call("laya", False)
    finally:
        db.close()


# --- API -------------------------------------------------------------------

def test_dispatch_api_status_and_run(client: TestClient) -> None:
    status = client.get("/api/dispatch/status")
    assert status.status_code == 200
    body = status.json()
    assert body["analysis_version"] == ANALYSIS_VERSION
    assert "tasks" in body

    run = client.post("/api/dispatch/run?limit=5")
    assert run.status_code == 200
    assert set(run.json()) >= {"claimed", "completed", "retryable", "terminal"}


def test_dispatch_api_article_view(client: TestClient) -> None:
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": True}})
        DispatchService(db).ensure_dispatch(art.id, "event_extraction")
        db.commit()
        article_id = str(art.id)
    finally:
        db.close()

    res = client.get(f"/api/dispatch/articles/{article_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["screening"]["route"] == "KEV"
    assert body["dispatches"][0]["task"] == "event_extraction"
    assert body["dispatches"][0]["status"] == "pending"

    assert client.get(f"/api/dispatch/articles/{uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize("task", ["screening", "domain_routing", "event_extraction",
                                  "claim_extraction", "graph_extraction",
                                  "evidence_collection", "claim_independence"])
def test_each_task_has_independent_key(task: str) -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, task)
        db.commit()
        assert row.task_name == task_key(task)
        assert _count(db, art.id, task) == 1
    finally:
        db.close()


# --- classifier integration / synthetic end-to-end -------------------------

def test_classifier_records_negative_screening_without_suppressing_classification(
        monkeypatch) -> None:
    from domains.news.classifier import ArticleClassifier

    async def fake_screen(db, text, priority=None, **kwargs):  # noqa: ANN001, ANN202
        return orch.ScreeningDecision(route="KEV", relevant=False,
                                      reason_codes=["KEV_NOT_RELEVANT"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, done=False)
        out = asyncio.run(ArticleClassifier(db).classify_pending(limit=5))
        db.refresh(art)
        assert out.classified == 1
        assert art.classification_status == "done"
        assert art.topics is not None  # existing classification contract kept
        # only the bookkeeping `classification` row exists; no analysis work
        assert _count(db, art.id, "event_extraction") == 0
        assert _count(db, art.id, "claim_extraction") == 0
        assert _count(db, art.id, "evidence_collection") == 0
        meta = json.loads(art.classification_meta)
        assert meta["local_screening"]["decision"] is False
    finally:
        db.close()


def test_p0_p1_safeguard_is_persisted_without_analysis_dispatch(monkeypatch) -> None:
    from domains.news.classifier import ArticleClassifier

    async def fake_screen(db, text, priority=None, **kwargs):  # noqa: ANN001, ANN202
        return orch.ScreeningDecision(
            route="AI_GATEWAY", relevant=False, p0_p1_safeguard=True,
            reason_codes=["P0_P1_SAFEGUARD", "AI_FALLBACK", "PRIORITY_REVIEW"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, done=False)
        out = asyncio.run(ArticleClassifier(db).classify_pending(limit=5))
        db.refresh(art)
        assert out.classified == 1  # retained: classification kept, not deleted
        meta = json.loads(art.classification_meta)["local_screening"]
        assert meta["p0_p1_safeguard"] is True
        assert "PRIORITY_REVIEW" in meta["reason_codes"]
        assert _count(db, art.id, "event_extraction") == 0
    finally:
        db.close()


def test_completed_dispatch_is_not_reclaimed() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
        assert svc.claim(row) is True
        svc.mark_completed(row)
        db.commit()
        assert svc.claimable("event_extraction") == []
        assert svc.claim(row) is False
        assert svc.get_dispatch(art.id, "event_extraction").status == "completed"
    finally:
        db.close()


def test_synthetic_collection_to_dispatch_end_to_end() -> None:
    """RawItem -> Document/Article -> screening -> dispatch -> real extractor."""
    from domains.news.classifier import ArticleClassifier
    from domains.news.fetchers import RawItem
    from domains.news.ingestion import NewsIngestionPipeline

    db = TestingSession()
    try:
        src = Source(name="E2ESrc", domain="e2e.local", type="rss",
                     collection_method="rss", active=True)
        db.add(src)
        db.commit()
        pipeline = NewsIngestionPipeline(db)
        item = RawItem(
            title="Oil rises on OPEC cuts",
            url="https://example.test/e2e-oil",
            raw_text="Crude oil prices rose after OPEC announced production cuts. " * 3,
            raw_payload='{"synthetic": true}',
        )
        assert pipeline.store_item(src, item) is True
        db.commit()
        assert pipeline.store_item(src, item) is False  # duplicate ingestion

        art = db.execute(select(Article)).scalars().one()
        art.document.ingestion_priority = None  # force the AI gate in this test
        db.commit()

        out = asyncio.run(ArticleClassifier(db).classify_pending(limit=5))
        assert out.classified == 1
        assert _count(db, art.id, "event_extraction") == 1
        assert _count(db, art.id, "claim_extraction") == 1
        assert _count(db, art.id, "evidence_collection") == 1
        meta = json.loads(db.get(Article, art.id).classification_meta)
        assert meta["local_screening"]["decision"] is True

        outcome = asyncio.run(run_once(db, limit=10, task="event_extraction"))
        assert outcome.completed == 1
        db.refresh(art)
        assert art.event_id is not None
    finally:
        db.close()


# --- Stage90: PostgreSQL/dialect and reliability verification ---------------

def _file_session(tmp_path):  # noqa: ANN001, ANN202
    """A second, independent SQLite *file* database (no shared connection)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.base import Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'dispatch.db'}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_unique_key_blocks_duplicate_rows_and_enqueue_survives_the_race(
        tmp_path) -> None:
    """The unique constraint is the real guard; a lost SELECT race recovers."""
    from sqlalchemy.exc import IntegrityError

    engine, Session = _file_session(tmp_path)
    seed = Session()
    try:
        src = Source(name="race", domain="r.local", type="rss", active=True)
        seed.add(src)
        seed.flush()
        doc = Document(source_id=src.id, title="t", raw_text="body",
                       url="https://example.test/race")
        seed.add(doc)
        seed.flush()
        art = Article(document_id=doc.id, title="t", summary="s")
        seed.add(art)
        seed.commit()
        article_id = art.id

        dup = ArticleDispatch(article_id=article_id, task_name=task_key("event_extraction"))
        seed.add(dup)
        seed.commit()

        seed.add(ArticleDispatch(article_id=article_id,
                                 task_name=task_key("event_extraction")))
        with pytest.raises(IntegrityError):
            seed.commit()
        seed.rollback()

        class _Miss:
            def scalar_one_or_none(self):
                return None

        db = Session()
        real_execute = db.execute
        state = {"first": True}

        def execute(stmt, *args, **kwargs):  # noqa: ANN001, ANN202
            if state["first"]:
                state["first"] = False
                return _Miss()  # simulate: row committed after our SELECT
            return real_execute(stmt, *args, **kwargs)

        db.execute = execute
        row = DispatchService(db).ensure_dispatch(article_id, "event_extraction")
        db.commit()
        assert row.id == dup.id
        assert db.execute(
            select(func.count()).select_from(ArticleDispatch)
        ).scalar_one() == 1
        db.close()
    finally:
        seed.close()
        engine.dispose()


def test_completed_work_is_not_repeated_after_restart() -> None:
    db = TestingSession()
    try:
        art = _article(db)
        DispatchService(db).ensure_dispatch(art.id, "event_extraction")
        db.commit()
        assert asyncio.run(run_once(db, limit=5, task="event_extraction")).completed == 1
        db.refresh(art)
        event_id = art.event_id
    finally:
        db.close()

    # "restart": a fresh session on the same durable store.
    db2 = TestingSession()
    try:
        outcome = asyncio.run(run_once(db2, limit=5, task="event_extraction"))
        assert outcome.claimed == 0
        art2 = db2.get(Article, art.id)
        assert art2.event_id == event_id
        row = DispatchService(db2).get_dispatch(art.id, "event_extraction")
        assert row is not None and row.status == "completed"
    finally:
        db2.close()


def test_enqueue_failure_keeps_article_retryable_and_loses_nothing(monkeypatch) -> None:
    from domains.news.classifier import ArticleClassifier

    async def fake_screen(db, text, priority=None, **kwargs):  # noqa: ANN001, ANN202
        return orch.ScreeningDecision(route="KEV", relevant=True,
                                      reason_codes=["KEV_RELEVANT"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)

    real_enqueue = DispatchService.enqueue_after_screening
    state = {"fail": True}

    def flaky(self, article_id, decision):  # noqa: ANN001, ANN202
        if state["fail"]:
            raise RuntimeError("simulated write failure")
        return real_enqueue(self, article_id, decision)

    monkeypatch.setattr(DispatchService, "enqueue_after_screening", flaky)
    db = TestingSession()
    try:
        art = _article(db, done=False)
        asyncio.run(ArticleClassifier(db).classify_pending(limit=5))
        db.refresh(art)
        assert art.classification_status == "pending"
        assert (art.classification_attempts or 0) >= 1
        assert _count(db, art.id, "event_extraction") == 0

        state["fail"] = False
        out = asyncio.run(ArticleClassifier(db).classify_pending(limit=5))
        db.refresh(art)
        assert out.classified == 1
        assert art.classification_status == "done"
        assert _count(db, art.id, "event_extraction") == 1
    finally:
        db.close()


def test_app_starts_when_dispatch_recovery_is_unavailable(monkeypatch) -> None:
    import backend.ai.budget as budget_module
    import backend.ai.credentials_store as store_module
    import backend.ai.dispatch.runner as runner_module
    import backend.database.session as session_module
    from backend.main import app

    def boom(db):  # noqa: ANN001, ANN202
        raise RuntimeError("database unavailable")

    async def idle(stop, *, interval, limit):  # noqa: ANN001, ANN202
        await stop.wait()

    # Keep startup offline: the test session stands in for the real factory.
    monkeypatch.setattr(session_module, "get_session_factory", lambda: TestingSession)
    monkeypatch.setattr(store_module, "set_session_factory", lambda factory: None)
    monkeypatch.setattr(budget_module, "set_session_factory", lambda factory: None)
    monkeypatch.setattr(runner_module, "recover_at_startup", boom)
    monkeypatch.setattr(runner_module, "run_forever", idle)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_model_disabled_while_screening_is_queued_uses_gateway(monkeypatch) -> None:
    from backend.ai.credentials_store import set_app_setting

    def forbidden(*args, **kwargs):  # noqa: ANN001, ANN202
        raise AssertionError("disabled local runtime must not be called")

    monkeypatch.setattr(orch, "make_kev_caller", forbidden)
    monkeypatch.setattr(orch, "make_laya_caller", forbidden)

    db = TestingSession()
    try:
        set_app_setting(db, "kev_local_screening_enabled", "false")
        set_app_setting(db, "laya_local_screening_enabled", "false")
        db.commit()
        art = _article(db, meta={"local_screening": {"route": "KEV",
                                                     "decision": None}})
        row = DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="screening"))
        assert outcome.completed == 1
        db.refresh(row)
        assert row.status == "completed"
        meta = json.loads(db.get(Article, art.id).classification_meta)
        assert meta["local_screening"]["route"] == "AI_GATEWAY"
        assert _count(db, art.id, "event_extraction") == 1
    finally:
        db.close()


def test_gateway_failure_keeps_screening_retryable(monkeypatch) -> None:
    from backend.ai.credentials_store import set_app_setting

    monkeypatch.setattr(
        orch, "make_ai_gateway_screen",
        lambda: (lambda text: {"relevant": None, "reason": "unparseable"}))

    db = TestingSession()
    try:
        set_app_setting(db, "kev_local_screening_enabled", "false")
        set_app_setting(db, "laya_local_screening_enabled", "false")
        db.commit()
        art = _article(db, meta={"local_screening": {"decision": None}})
        row = DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="screening"))
        assert outcome.retryable == 1
        db.refresh(row)
        assert row.status == "retryable"
        assert row.next_retry_at is not None
        assert _count(db, art.id, "event_extraction") == 0  # never "irrelevant"
    finally:
        db.close()

"""Tests for article classification (Phase 10)."""
from __future__ import annotations

import asyncio
import json as _json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.classifier import ArticleClassifier, compute_importance
from domains.news.classifier_schema import (
    CLASSIFY_SCHEMA,
    ClassificationResult,
    ImportanceInputs,
)
from tests.conftest import TestingSession


# --- importance (deterministic) ---
def test_importance_high() -> None:
    inp = ImportanceInputs(
        impact=1.0, scope=1.0, novelty=1.0, market_relevance=1.0,
        geopolitical_relevance=1.0, economic_relevance=1.0,
    )
    assert compute_importance(inp) <= 3


def test_importance_low() -> None:
    inp = ImportanceInputs()
    assert compute_importance(inp) >= 7


def test_importance_range() -> None:
    for _ in range(5):
        v = compute_importance(ImportanceInputs(impact=0.5))
        assert 1 <= v <= 10


# --- schema parsing ---
def test_classification_from_dict() -> None:
    data = {
        "topics": ["energy", "markets", "bogus_topic"],  # bogus باید فیلتر شود
        "country": "us",  # باید به US تبدیل شود
        "entities": [
            {"name": "OPEC", "type": "organization"},
            {"name": "OPEC", "type": "organization"},  # تکراری حذف شود
        ],
        "sentiment": -0.3,
        "stance": "negative",
        "summary": "Oil rose.",
        "importance": {"impact": 0.8, "market_relevance": 0.9},
        "confidence": 0.8,
    }
    r = ClassificationResult.from_dict(data)
    assert r.topics == ["energy", "markets"]
    assert r.country == "US"
    assert len(r.entities) == 1
    assert r.sentiment == -0.3
    assert r.importance_inputs.market_relevance == 0.9


def test_sentiment_and_confidence_clamped() -> None:
    data = {
        "topics": [], "entities": [], "sentiment": 5.0, "summary": "x",
        "importance": {}, "confidence": -3.0,
    }
    r = ClassificationResult.from_dict(data)
    assert r.sentiment == 1.0
    assert r.confidence == 0.0


def test_classify_schema_requires_importance() -> None:
    assert CLASSIFY_SCHEMA["type"] == "object"
    assert "importance" in CLASSIFY_SCHEMA["required"]


def test_jsonschema_validation_rejects_bad_output() -> None:
    import pytest

    from domains.news.classifier import _validate

    with pytest.raises(ValueError):
        _validate({"topics": [], "entities": [], "sentiment": 0.0}, CLASSIFY_SCHEMA)


# --- classifier with mock provider ---
def _seed_article() -> str:
    session = TestingSession()
    try:
        src = Source(name="ClassifySrc", domain="c.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="Oil rises", raw_text="Crude oil prices rose.")
        session.add(doc)
        session.flush()
        art = Article(document_id=doc.id, title="Oil rises", summary="Crude oil prices rose today.")
        session.add(art)
        session.commit()
        return str(art.id)
    finally:
        session.close()


def test_classify_pending_uses_mock() -> None:
    _seed_article()
    session = TestingSession()
    try:
        outcome = asyncio.run(ArticleClassifier(session).classify_pending(limit=10))
        assert outcome.classified == 1
        art = session.query(Article).first()
        assert art.topics is not None
        assert art.importance is not None
        assert 1 <= art.importance <= 10
    finally:
        session.close()


def _valid_classify_json() -> str:
    import json as _json

    return _json.dumps({
        "topics": ["energy"],
        "country": "US",
        "entities": [{"name": "OPEC", "type": "organization"}],
        "sentiment": 0.2,
        "stance": "neutral",
        "summary": "Oil rose.",
        "importance": {
            "impact": 0.8, "scope": 0.5, "probability": 0.5, "novelty": 0.5,
            "market_relevance": 0.9, "geopolitical_relevance": 0.5,
            "economic_relevance": 0.5, "time_sensitivity": 0.5,
            "strategic_relevance": 0.5, "historical_significance": 0.5,
        },
        "confidence": 0.8,
    })


def test_classify_repair_retry_recovers_non_json() -> None:
    """Fallback مستند: خروجی غیرJSON اول → یک retry تعمیری → classified + ثبت repair_retry."""
    import json as _json

    from backend.ai.schemas.types import AIResponse, AIUsage

    _seed_article()
    session = TestingSession()
    try:
        clf = ArticleClassifier(session)
        calls = {"n": 0}

        async def fake_structured(request, schema):  # noqa: ANN001, ANN202
            calls["n"] += 1
            text = "not json at all" if calls["n"] == 1 else _valid_classify_json()
            return AIResponse(text=text, provider="fake", model="fake-1",
                              usage=AIUsage(), is_mock=False)

        clf.gateway.structured_generate = fake_structured  # type: ignore[method-assign]
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.classified == 1
        assert calls["n"] == 2  # دقیقاً یک retry
        art = session.query(Article).first()
        meta = _json.loads(art.classification_meta)
        assert meta["repair_retry"] is True
        assert meta["provider"] == "fake"
    finally:
        session.close()


def test_local_screening_is_advisory_metadata(monkeypatch) -> None:
    """Screening is recorded as provenance, never used as the decision itself."""
    import json as _json

    from backend.ai.local_screening import orchestrator as orch
    from backend.ai.schemas.types import AIResponse, AIUsage

    _seed_article()
    session = TestingSession()
    try:
        clf = ArticleClassifier(session)

        async def fake_screen(db, text, priority=None, **kwargs):  # noqa: ANN001, ANN202
            assert "Crude oil" in text
            return orch.ScreeningDecision(
                route="KEV", relevant=True, reason_codes=["KEV_RELEVANT"],
                provenance={"priority": priority},
            )

        async def fake_structured(request, schema):  # noqa: ANN001, ANN202
            return AIResponse(text=_valid_classify_json(), provider="fake",
                              model="fake-1", usage=AIUsage(), is_mock=False)

        monkeypatch.setattr(orch, "screen_with_db", fake_screen)
        clf.gateway.structured_generate = fake_structured  # type: ignore[method-assign]
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.classified == 1
        art = session.query(Article).first()
        meta = _json.loads(art.classification_meta)
        assert meta["local_screening"]["route"] == "KEV"
        assert meta["local_screening"]["decision"] is True
        assert art.classification_status == "done"
    finally:
        session.close()


def test_classify_repair_retry_gives_up_after_one() -> None:
    """دو خروجی غیرJSON پشت سر هم → failed (نه retry بی‌نهایت)."""
    from backend.ai.schemas.types import AIResponse, AIUsage

    _seed_article()
    session = TestingSession()
    try:
        clf = ArticleClassifier(session)
        calls = {"n": 0}

        async def fake_structured(request, schema):  # noqa: ANN001, ANN202
            calls["n"] += 1
            return AIResponse(text="still not json", provider="fake", model="fake-1",
                              usage=AIUsage(), is_mock=False)

        clf.gateway.structured_generate = fake_structured  # type: ignore[method-assign]
        article = session.query(Article).first()
        article.classification_attempts = 2  # سومین تلاش → failed نهایی
        session.commit()
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.classified == 0
        assert outcome.failed == 1
        assert calls["n"] == 2
        session.refresh(article)
        assert article.classification_status == "failed"
    finally:
        session.close()


def test_classify_api(client: TestClient) -> None:
    _seed_article()
    res = client.post("/api/classify/run?limit=10")
    assert res.status_code == 200
    assert res.json()["classified"] == 1

    listing = client.get("/api/classify/articles")
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["importance"] is not None
    assert "priority" in items[0]  # اولویت سند (P0..P4) در خواندن مقاله موجود است

    detail = client.get(f"/api/classify/articles/{items[0]['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == items[0]["id"]
    assert "summary" in body and "event_id" in body and "is_mock" in body

    missing = client.get("/api/classify/articles/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


def test_classify_api_returns_skipped_zero_when_nothing_skipped(client: TestClient) -> None:
    _seed_article()  # بدون اولویت کم و بدون محدودیت → هیچ موردی کنار گذاشته نمی‌شود
    res = client.post("/api/classify/run?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["classified"] == 1
    assert body["skipped"] == 0 and isinstance(body["skipped"], int)


def test_classify_api_skipped_equals_classify_outcome(client: TestClient, monkeypatch) -> None:
    """مقدار پاسخ باید همان ClassifyOutcome.skipped باشد، نه بازمحاسبه در route."""
    from domains.news.classifier import ArticleClassifier, ClassifyOutcome

    async def fake_pending(self, *, limit: int = 20) -> ClassifyOutcome:  # noqa: ARG001
        return ClassifyOutcome(classified=2, failed=1, skipped=3, errors=["boom"])

    monkeypatch.setattr(ArticleClassifier, "classify_pending", fake_pending)
    body = client.post("/api/classify/run?limit=10").json()
    assert body == {"classified": 2, "failed": 1, "skipped": 3, "errors": ["boom"]}


def test_classify_api_reports_gate_skips_from_real_run(client: TestClient) -> None:
    """اجرای واقعی با گیت P3: skipped=1 و بقیهٔ قراردادهای قبلی پاسخ دست‌نخورده."""
    import uuid

    session = TestingSession()
    try:
        art = _seed_queue_article(session, title="api-low-p3", priority="P3", hours_ago=1)
        art_id = art.id
    finally:
        session.close()

    body = client.post("/api/classify/run?limit=10").json()
    assert body["classified"] == 0 and body["failed"] == 0 and body["errors"] == []
    assert body["skipped"] == 1

    session = TestingSession()
    try:  # قرارداد داخلی گیت حفظ شده است
        row = session.get(Article, uuid.UUID(str(art_id)))
        assert row.classification_status == "done" and row.classification_attempts == 0
        assert row.importance == 7 and row.decided_by == "rules"
    finally:
        session.close()


def test_classify_uses_document_body_when_summary_missing() -> None:
    """AUDIT-REPAIR: بدنه‌ی سند در ورودی طبقه‌بندی است (نه فقط عنوان)."""
    import json as _json

    session = TestingSession()
    try:
        src = Source(name="BodySrc", domain="b.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(
            source_id=src.id, title="T", raw_text="Full body text about oil markets."
        )
        session.add(doc)
        session.flush()
        # عنوان/خلاصه تهی؛ فقط بدنه موجود است (قبلاً خطای empty می‌داد)
        art = Article(document_id=doc.id, title="", summary=None)
        session.add(art)
        session.commit()
        outcome = asyncio.run(ArticleClassifier(session).classify_pending(limit=10))
        assert outcome.classified == 1
        meta = _json.loads(art.classification_meta or "{}")
        assert meta.get("prompt_version") == "v3"
    finally:
        session.close()


def _apply_with_doc(analytic_json_dict, *, priority=None, priority_source=None):
    """_apply واقعی روی مقاله+داکیومنت sqlite؛ برمی‌گرداند (article, session)."""
    from domains.news.classifier_schema import ClassificationResult

    session = TestingSession()
    doc = Document(source_id=None, title="T", raw_text="Text " * 40)
    if priority is not None:
        doc.ingestion_priority = priority
    if priority_source is not None:
        doc.priority_source = priority_source
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title="T")
    session.add(art)
    session.commit()
    result = ClassificationResult.from_dict(analytic_json_dict)
    ArticleClassifier(session)._apply(art, result)
    session.commit()
    return art, session


def _high_inputs_dict():
    return {
        "topics": ["energy"], "country": "US",
        "entities": [{"name": "OPEC", "type": "organization"}],
        "sentiment": 0.2, "stance": "neutral", "summary": "Oil rose.",
        "importance": {
            "impact": 0.9, "scope": 0.9, "probability": 0.9, "novelty": 0.9,
            "market_relevance": 0.9, "geopolitical_relevance": 0.9,
            "economic_relevance": 0.9, "time_sensitivity": 0.9,
            "strategic_relevance": 0.9, "historical_significance": 0.9,
        },
        "confidence": 0.8,
    }


def _mid_inputs_dict():
    d = _high_inputs_dict()
    d["importance"] = {k: 0.55 for k in d["importance"]}
    return d


def _low_inputs_dict():
    d = _high_inputs_dict()
    d["importance"] = {k: 0.1 for k in d["importance"]}
    return d


def test_level_bands_cover_all_five():
    from domains.news.classifier import align_importance_to_level

    for level, (lo, hi) in (("P0", (1, 2)), ("P1", (3, 4)), ("P2", (5, 6)),
                            ("P3", (7, 8)), ("P4", (9, 10))):
        for analytic in (1, 5, 10):
            v, _ = align_importance_to_level(level, analytic, priority_source="rules")
            assert lo <= v <= hi, (level, analytic)


def test_band_boundaries_and_invalid():
    from domains.news.classifier import align_importance_to_level

    assert align_importance_to_level("P0", 1) == (1, None)
    assert align_importance_to_level("P0", 10) == (2, None)
    assert align_importance_to_level("P4", 1) == (9, None)
    assert align_importance_to_level("PX", 5) == (5, None)
    assert align_importance_to_level("", 5) == (5, None)
    assert align_importance_to_level("p2", 5) == (5, None)
    assert align_importance_to_level(None, 7) == (7, None)


def test_lower_number_sorts_first_in_queries():
    from sqlalchemy import select

    from domains.news.classifier import align_importance_to_level

    session = TestingSession()
    try:
        for level in ("P4", "P0"):
            doc = Document(source_id=None, title=level)
            session.add(doc)
            session.flush()
            v, _ = align_importance_to_level(level, 5, priority_source="rules")
            session.add(Article(document_id=doc.id, title=level, importance=v))
        session.commit()
        rows = session.execute(
            select(Article).order_by(Article.importance.asc())).scalars().all()
        assert [r.title for r in rows] == ["P0", "P4"]
    finally:
        session.close()


def test_rules_decided_by_through_apply():
    art, session = _apply_with_doc(
        _high_inputs_dict(), priority="P1", priority_source="rules")
    try:
        assert art.importance in (3, 4)
        assert art.decided_by == "rules"
    finally:
        session.close()


def test_ai_decided_by_through_apply():
    art, session = _apply_with_doc(
        _high_inputs_dict(), priority="P2", priority_source="ai")
    try:
        assert art.importance in (5, 6)
        assert art.decided_by == "ai"
    finally:
        session.close()


def test_unknown_provenance_stays_null():
    art, session = _apply_with_doc(_high_inputs_dict())
    try:
        assert art.decided_by is None
        assert art.importance is not None and 1 <= art.importance <= 10
    finally:
        session.close()


def _seed_queue_article(session, *, title, priority=None, hours_ago=0):
    from datetime import timedelta

    from backend.database.models.document import Document

    now = datetime.now(UTC)
    doc = Document(source_id=None, title=title, raw_text="Body text " * 40,
                   retrieved_at=now - timedelta(hours=hours_ago))
    if priority is not None:
        doc.ingestion_priority = priority
        doc.priority_source = "rules"
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title=title, retrieved_at=doc.retrieved_at)
    session.add(art)
    session.commit()
    return art


def test_queue_orders_p0_before_p2_before_unknown(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        _seed_queue_article(session, title="new-unknown", hours_ago=0)
        _seed_queue_article(session, title="mid-p2", priority="P2", hours_ago=5)
        _seed_queue_article(session, title="old-p0", priority="P0", hours_ago=50)
        clf = ArticleClassifier(session)
        calls = []
        real = clf.classify_article

        async def spy(article):
            calls.append(article.title)
            return await real(article)

        monkeypatch.setattr(clf, "classify_article", spy)
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.classified == 3
        assert calls == ["old-p0", "mid-p2", "new-unknown"]
    finally:
        session.close()


def test_queue_unknown_not_dropped_and_limit_kept(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        for i in range(3):
            _seed_queue_article(session, title=f"u-{i}", hours_ago=i)
        clf = ArticleClassifier(session)
        outcome = asyncio.run(clf.classify_pending(limit=2))
        assert outcome.classified == 2
        assert session.query(Article).filter(
            Article.classification_status == "pending").count() == 1
    finally:
        session.close()


def test_queue_retrieved_desc_within_level(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        _seed_queue_article(session, title="older-p1", priority="P1", hours_ago=9)
        _seed_queue_article(session, title="newer-p1", priority="P1", hours_ago=1)
        clf = ArticleClassifier(session)
        calls = []
        real = clf.classify_article

        async def spy(article):
            calls.append(article.title)
            return await real(article)

        monkeypatch.setattr(clf, "classify_article", spy)
        asyncio.run(clf.classify_pending(limit=10))
        assert calls == ["newer-p1", "older-p1"]
    finally:
        session.close()


def test_queue_tiebreak_stable(monkeypatch):
    from domains.news.classifier import ArticleClassifier, _pending_stmt

    session = TestingSession()
    try:
        _seed_queue_article(session, title="t-a", priority="P2", hours_ago=0)
        _seed_queue_article(session, title="t-b", priority="P2", hours_ago=0)
        first = [a.title for a in session.execute(_pending_stmt(10)).scalars().all()]
        second = [a.title for a in session.execute(_pending_stmt(10)).scalars().all()]
        assert sorted(first) == ["t-a", "t-b"] and first == second
        clf = ArticleClassifier(session)
        assert asyncio.run(clf.classify_pending(limit=10)).classified == 2
    finally:
        session.close()


def test_gate_skips_p3_without_ai(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        art = _seed_queue_article(session, title="low-p3", priority="P3", hours_ago=1)
        clf = ArticleClassifier(session)

        async def boom(article):
            raise AssertionError("provider must not be called for P3")

        monkeypatch.setattr(clf, "classify_article", boom)
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.classified == 0 and outcome.failed == 0
        assert outcome.skipped == 1
        session.refresh(art)
        assert art.classification_status == "done"
        assert art.classification_attempts == 0
        assert art.importance == 7 and art.decided_by == "rules"
        assert art.topics == "[]"
        assert art.confidence is None
    finally:
        session.close()


def test_gate_skips_p4_without_ai(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        art = _seed_queue_article(session, title="low-p4", priority="P4", hours_ago=1)
        clf = ArticleClassifier(session)

        async def boom(article):
            raise AssertionError("provider must not be called for P4")

        monkeypatch.setattr(clf, "classify_article", boom)
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.skipped == 1
        session.refresh(art)
        assert art.importance == 9 and art.classification_status == "done"
    finally:
        session.close()


def test_gate_unknown_level_goes_to_ai(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        _seed_queue_article(session, title="mystery", hours_ago=1)
        clf = ArticleClassifier(session)
        calls = []
        real = clf.classify_article

        async def spy(article):
            calls.append(article.title)
            return await real(article)

        monkeypatch.setattr(clf, "classify_article", spy)
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert calls == ["mystery"] and outcome.classified == 1
    finally:
        session.close()


def test_gate_invalid_level_goes_to_ai(monkeypatch):
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        art = _seed_queue_article(session, title="weird", hours_ago=1)
        art.document.ingestion_priority = "PX"
        session.commit()
        clf = ArticleClassifier(session)
        calls = []
        real = clf.classify_article

        async def spy(article):
            calls.append(article.title)
            return await real(article)

        monkeypatch.setattr(clf, "classify_article", spy)
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert calls == ["weird"] and outcome.classified == 1
    finally:
        session.close()


def test_budget_exceeded_keeps_pending_without_attempt(monkeypatch):
    from backend.ai.schemas.types import AIError, AIErrorKind
    from domains.news.classifier import ArticleClassifier

    session = TestingSession()
    try:
        art = _seed_queue_article(session, title="rich", priority="P0", hours_ago=1)
        clf = ArticleClassifier(session)

        async def broke(article):
            raise AIError("ai budget exceeded", kind=AIErrorKind.budget,
                          retryable=False)

        monkeypatch.setattr(clf, "classify_article", broke)
        outcome = asyncio.run(clf.classify_pending(limit=10))
        assert outcome.failed == 0 and outcome.skipped == 1
        session.refresh(art)
        assert art.classification_status == "pending"
        assert art.classification_attempts == 0
    finally:
        session.close()


def test_keep_in_band_records_null_not_rules():
    art, session = _apply_with_doc(
        _mid_inputs_dict(), priority="P2", priority_source="rules")
    try:
        assert art.importance == 5
        assert art.decided_by is None
    finally:
        session.close()


def test_clamp_to_p0_records_rules():
    art, session = _apply_with_doc(
        _low_inputs_dict(), priority="P0", priority_source="rules")
    try:
        assert art.importance == 2
        assert art.decided_by == "rules"
    finally:
        session.close()


def test_clamp_to_p4_records_ai():
    art, session = _apply_with_doc(
        _high_inputs_dict(), priority="P4", priority_source="ai")
    try:
        assert art.importance == 9
        assert art.decided_by == "ai"
    finally:
        session.close()


def test_keep_in_band_with_ai_records_null():
    art, session = _apply_with_doc(
        _mid_inputs_dict(), priority="P2", priority_source="ai")
    try:
        assert art.importance == 5
        assert art.decided_by is None
    finally:
        session.close()


def test_clamp_unknown_source_corrects_without_provenance():
    art, session = _apply_with_doc(
        _low_inputs_dict(), priority="P0")
    try:
        assert art.importance == 2
        assert art.decided_by is None
    finally:
        session.close()


def test_reapply_is_idempotent():
    import json as _json

    from domains.news.classifier import ArticleClassifier
    from domains.news.classifier_schema import ClassificationResult

    art, session = _apply_with_doc(
        _low_inputs_dict(), priority="P0", priority_source="rules")
    try:
        first = (art.importance, art.decided_by, art.confidence)
        meta_before = art.classification_meta
        result = ClassificationResult.from_dict(_low_inputs_dict())
        ArticleClassifier(session)._apply(art, result)
        session.commit()
        assert (art.importance, art.decided_by, art.confidence) == first
        assert _json.loads(art.classification_meta or "{}").get(
            "importance_inputs") == _json.loads(meta_before or "{}").get(
            "importance_inputs")
    finally:
        session.close()


def test_apply_preserves_doc_priority_and_raw():
    from backend.database.models.document import Document

    art, session = _apply_with_doc(
        _mid_inputs_dict(), priority="P3", priority_source="rules")
    try:
        doc = session.get(Document, art.document_id)
        assert (doc.ingestion_priority, doc.priority_source) == ("P3", "rules")
        assert art.importance == 7
        assert art.decided_by == "rules"
        assert art.confidence == 0.8
        assert art.title == "T"
    finally:
        session.close()


def test_raw_and_confidence_untouched_by_align():
    from domains.news.classifier import align_importance_to_level, compute_importance
    from domains.news.classifier_schema import ImportanceInputs

    assert compute_importance(ImportanceInputs(impact=0.5)) == compute_importance(
        ImportanceInputs(impact=0.5))
    v, d = align_importance_to_level("P3", 4, priority_source="rules")
    assert (v, d) == (7, "rules")


def test_decided_by_migration_chain():
    import importlib.util
    from pathlib import Path

    mig = (Path(__file__).resolve().parent.parent / "db" / "migrations"
           / "versions" / "b67a512b5ad2_article_decided_by.py")
    assert mig.is_file()
    spec = importlib.util.spec_from_file_location("mig_decided", str(mig))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "b67a512b5ad2"
    assert mod.down_revision == "f594a47ca800"
    assert callable(mod.upgrade) and callable(mod.downgrade)


# =====================================================================
# شفاف‌سازی محدودسازی اهمیت تحلیلی (analytic_importance / band_clamped)
# =====================================================================
def _analytic_from_meta(meta: dict) -> int:
    """مقدار تحلیلی را از همان inputs ذخیره‌شده بازسازی می‌کند (بدون حدس)."""
    return compute_importance(ImportanceInputs(**meta["importance_inputs"]))


def test_in_band_records_raw_analytic_and_not_clamped():
    art, session = _apply_with_doc(
        _mid_inputs_dict(), priority="P2", priority_source="rules")
    try:
        meta = _json.loads(art.classification_meta or "{}")
        assert art.importance == 5 and art.decided_by is None
        assert meta["band_clamped"] is False
        assert meta["analytic_importance"] == 5 == _analytic_from_meta(meta)
        # عمل clamp انجام نشده: مقدار تحلیلی و مقدار نهایی یکی‌اند
        assert meta["analytic_importance"] == art.importance
    finally:
        session.close()


def test_clamped_records_raw_analytic_and_flag():
    art, session = _apply_with_doc(
        _low_inputs_dict(), priority="P0", priority_source="rules")
    try:
        meta = _json.loads(art.classification_meta or "{}")
        assert art.importance == 2 and art.decided_by == "rules"
        assert meta["band_clamped"] is True
        # مقدار خام پیش از clamp حفظ شده، نه مقدار clamp‌شده
        assert meta["analytic_importance"] == _analytic_from_meta(meta)
        assert meta["analytic_importance"] > art.importance
    finally:
        session.close()


def test_clamp_unknown_provenance_is_distinguishable_from_in_band():
    """ابهام قبلی رفع شده: clamp با منشأ نامعلوم با «داخل باند» قابل تفکیک است."""
    art, session = _apply_with_doc(_low_inputs_dict(), priority="P0")
    try:
        meta = _json.loads(art.classification_meta or "{}")
        assert art.decided_by is None          # قرارداد ستون تغییر نکرده
        assert meta["band_clamped"] is True    # ولی واقعاً clamp شده است
    finally:
        session.close()


def test_no_band_records_null_not_false():
    """بدون سطح معتبر، نه ادعای داخل‌باند و نه عدد ساختگی."""
    art, session = _apply_with_doc(_high_inputs_dict())
    try:
        meta = _json.loads(art.classification_meta or "{}")
        assert art.decided_by is None
        assert meta["band_clamped"] is None
        assert meta["analytic_importance"] == art.importance == _analytic_from_meta(meta)
    finally:
        session.close()


def test_band_map_and_existing_meta_keys_unchanged():
    from domains.news.classifier import PRIORITY_BANDS

    assert PRIORITY_BANDS == {"P0": (1, 2), "P1": (3, 4), "P2": (5, 6),
                              "P3": (7, 8), "P4": (9, 10)}
    art, session = _apply_with_doc(
        _high_inputs_dict(), priority="P1", priority_source="rules")
    try:
        meta = _json.loads(art.classification_meta or "{}")
        for key in ("provider", "model", "prompt_version", "is_mock", "repair_retry",
                    "classified_at", "importance_inputs", "response_hash"):
            assert key in meta
    finally:
        session.close()


def test_meta_survives_reapply():
    art, session = _apply_with_doc(
        _low_inputs_dict(), priority="P0", priority_source="rules")
    try:
        meta = _json.loads(art.classification_meta or "{}")
        first = (meta["analytic_importance"], meta["band_clamped"])
        result = ClassificationResult.from_dict(_low_inputs_dict())
        ArticleClassifier(session)._apply(art, result)
        session.commit()
        again = _json.loads(art.classification_meta or "{}")
        assert (again["analytic_importance"], again["band_clamped"]) == first
        assert again["band_clamped"] is True
    finally:
        session.close()


def test_low_priority_gate_records_unknown_analytic(monkeypatch):
    """گیت P3/P4 هیچ مقدار تحلیلی محاسبه نکرده → null (نه false کاذب)."""
    session = TestingSession()
    try:
        art = _seed_queue_article(session, title="meta-p3", priority="P3", hours_ago=1)
        clf = ArticleClassifier(session)

        async def boom(article):
            raise AssertionError("provider must not be called for P3")

        monkeypatch.setattr(clf, "classify_article", boom)
        assert asyncio.run(clf.classify_pending(limit=10)).skipped == 1
        session.refresh(art)
        meta = _json.loads(art.classification_meta or "{}")
        assert meta["skipped_ai"] == "low_priority_gate"
        assert meta["analytic_importance"] is None
        assert meta["band_clamped"] is None
        assert meta["level"] == "P3" and meta["decided_by"] == "rules"
    finally:
        session.close()


def test_failed_classification_writes_no_false_band_claim(monkeypatch):
    """طبقه‌بندی ناموفق هیچ ادعای باندی نمی‌سازد (غیبت کلید ≠ band_clamped=false)."""
    _seed_article()
    session = TestingSession()
    try:
        clf = ArticleClassifier(session)

        async def broke(article):
            raise RuntimeError("provider down")

        monkeypatch.setattr(clf, "classify_article", broke)
        assert asyncio.run(clf.classify_pending(limit=10)).failed == 1
        art = session.query(Article).first()
        assert art.classification_meta is None
        assert art.importance is None and art.decided_by is None
    finally:
        session.close()

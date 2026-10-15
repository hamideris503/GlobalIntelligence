"""Tests for article classification (Phase 10)."""
from __future__ import annotations

import asyncio

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

    detail = client.get(f"/api/classify/articles/{items[0]['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == items[0]["id"]
    assert "summary" in body and "event_id" in body and "is_mock" in body

    missing = client.get("/api/classify/articles/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


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

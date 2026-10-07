"""Tests for article classification (Phase 10)."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.database import models as _models
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
        "topics": ["energy", "markets"],
        "country": "US",
        "entities": [{"name": "OPEC", "type": "organization"}],
        "sentiment": -0.3,
        "stance": "negative",
        "summary": "Oil rose.",
        "importance": {"impact": 0.8, "market_relevance": 0.9},
        "confidence": 0.8,
    }
    r = ClassificationResult.from_dict(data)
    assert r.topics == ["energy", "markets"]
    assert r.entities[0].name == "OPEC"
    assert r.sentiment == -0.3
    assert r.importance_inputs.market_relevance == 0.9


def test_classify_schema_is_object() -> None:
    assert CLASSIFY_SCHEMA["type"] == "object"
    assert "topics" in CLASSIFY_SCHEMA["properties"]


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

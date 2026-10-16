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

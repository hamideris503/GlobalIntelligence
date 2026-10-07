"""Tests for the news ingestion pipeline (Phase 8)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database import models as _models
from backend.database.models.source import Source
from domains.news.fetchers import MockFetcher, RawItem
from domains.news.ingestion import NewsIngestionPipeline
from domains.news.normalizer import clean_text, content_hash, detect_language, normalize
from tests.conftest import TestingSession


def _make_source() -> str:
    session = TestingSession()
    try:
        s = Source(name="Mock Source", domain="example.local", type="rss", active=True)
        session.add(s)
        session.commit()
        return str(s.id)
    finally:
        session.close()


# --- normalizer ---
def test_clean_text_strips_html() -> None:
    assert clean_text("<p>Hello <b>world</b></p>") == "Hello world"


def test_detect_language_persian() -> None:
    assert detect_language("سلام دنیا") == "fa"
    assert detect_language("hello world") == "en"


def test_content_hash_stable() -> None:
    assert content_hash("a", "b") == content_hash("a", "b")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_normalize_point_in_time() -> None:
    item = RawItem(title="T", url="http://x", raw_text="Body")
    norm = normalize(item)
    assert norm.retrieved_at is not None
    assert norm.available_at is not None
    assert norm.observed_at is not None
    assert norm.content_hash is not None


# --- pipeline ---
def test_pipeline_stores_documents() -> None:
    _make_source()
    session = TestingSession()
    try:
        source = session.query(Source).first()
        pipeline = NewsIngestionPipeline(session, fetcher=MockFetcher())
        result = pipeline.ingest_source(source, limit=10)
        assert result.stored == 3
        assert result.fetched == 3
        assert session.query(_models.Document).count() == 3
        assert session.query(_models.Article).count() == 3
    finally:
        session.close()


def test_pipeline_deduplicates() -> None:
    _make_source()
    session = TestingSession()
    try:
        source = session.query(Source).first()
        pipeline = NewsIngestionPipeline(session, fetcher=MockFetcher())
        pipeline.ingest_source(source, limit=10)
        result2 = pipeline.ingest_source(source, limit=10)
        assert result2.stored == 0
        assert result2.duplicates == 3
    finally:
        session.close()


# --- API ---
def test_ingest_api(client: TestClient) -> None:
    sid = _make_source()
    res = client.post("/api/ingest", json={"source_id": sid, "limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["stored"] == 3

    docs = client.get("/api/ingest/documents")
    assert docs.status_code == 200
    assert len(docs.json()) == 3


def test_ingest_unknown_source_404(client: TestClient) -> None:
    res = client.post("/api/ingest", json={"source_name": "nope"})
    assert res.status_code == 404

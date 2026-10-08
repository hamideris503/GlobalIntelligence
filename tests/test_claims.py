"""Tests for claim extraction (Phase 12)."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from domains.claims.extractor import ClaimExtractor
from domains.claims.prompts import CLAIMS_SCHEMA
from tests.conftest import TestingSession


def _seed_event(*, action: str = "The central bank raised rates") -> str:
    session = TestingSession()
    try:
        src = Source(name="ClaimSrc", domain="c.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="cb raises", raw_text=action)
        session.add(doc)
        session.flush()
        art = Article(
            document_id=doc.id, title="cb raises", summary=action,
            topics=json.dumps(["monetary_policy"]), classification_status="done",
        )
        session.add(art)
        session.flush()
        event = Event(
            event_type="monetary_policy",
            action=action,
            actors=json.dumps(["Central Bank"]),
            sources=json.dumps([str(src.id)]),
            claims_extracted=False,
        )
        session.add(event)
        session.flush()
        art.event_id = event.id
        session.commit()
        return str(event.id)
    finally:
        session.close()


def test_claims_schema() -> None:
    assert CLAIMS_SCHEMA["type"] == "object"
    assert "claims" in CLAIMS_SCHEMA["properties"]


def test_extract_claims_fallback() -> None:
    """با mock، کلید subject/predicate/object باید پر شود (mock مقادیر sample می‌دهد)."""
    _seed_event()
    session = TestingSession()
    try:
        outcome = asyncio.run(ClaimExtractor(session).run(limit=10))
        assert outcome.events_processed == 1
        assert outcome.claims_created >= 1
        claims = session.query(Claim).all()
        assert len(claims) >= 1
        for c in claims:
            assert c.event_id is not None
            assert c.subject
            assert c.predicate
    finally:
        session.close()


def test_event_marked_extracted() -> None:
    _seed_event()
    session = TestingSession()
    try:
        asyncio.run(ClaimExtractor(session).run(limit=10))
        event = session.query(Event).first()
        assert event.claims_extracted is True
    finally:
        session.close()


def test_double_run_is_idempotent() -> None:
    _seed_event()
    session = TestingSession()
    try:
        first = asyncio.run(ClaimExtractor(session).run(limit=10))
        second = asyncio.run(ClaimExtractor(session).run(limit=10))
        assert first.events_processed == 1
        assert second.events_processed == 0  # دوباره پردازش نمی‌شود
    finally:
        session.close()


def test_claims_api(client: TestClient) -> None:
    _seed_event()
    res = client.post("/api/claims/extract?limit=10")
    assert res.status_code == 200
    assert res.json()["events_processed"] == 1

    listing = client.get("/api/claims")
    assert listing.status_code == 200
    claims = listing.json()
    assert len(claims) >= 1
    assert claims[0]["subject"]

"""Tests for the Knowledge Graph engine & API (Phase 15)."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.entity import Entity, EntityRelationship
from backend.database.models.event import Event
from backend.database.models.source import Source
from domains.graph.engine import KnowledgeGraphEngine, normalize_name
from domains.graph.prompts import RELATIONS_SCHEMA
from tests.conftest import TestingSession


def _seed_event(entities: list[dict], *, action: str = "Central Bank raised rates") -> str:
    session = TestingSession()
    try:
        src = Source(name="GraphSrc", domain="g.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="cb", raw_text=action)
        session.add(doc)
        session.flush()
        art = Article(
            document_id=doc.id,
            title="cb",
            summary=action,
            entities=json.dumps(entities),
            classification_status="done",
        )
        session.add(art)
        session.flush()
        event = Event(
            event_type="monetary_policy",
            action=action,
            actors=json.dumps([e["name"] for e in entities]),
            claims_extracted=True,
            graph_extracted=False,
        )
        session.add(event)
        session.flush()
        art.event_id = event.id
        session.commit()
        return str(event.id)
    finally:
        session.close()


def test_normalize_name() -> None:
    assert normalize_name("  Central   Bank ") == "central bank"
    assert normalize_name("Central Bank") == normalize_name("central  bank")


def test_relations_schema() -> None:
    assert RELATIONS_SCHEMA["type"] == "object"
    assert "relationships" in RELATIONS_SCHEMA["properties"]


def test_entities_created_and_deduped() -> None:
    """دو مقاله با نام یکسان (حروف متفاوت) → یک Entity."""
    _seed_event(
        [
            {"name": "Central Bank", "type": "central_bank"},
            {"name": "central bank", "type": "central_bank"},
            {"name": "US Dollar", "type": "currency"},
        ]
    )
    session = TestingSession()
    try:
        outcome = asyncio.run(KnowledgeGraphEngine(session).run(limit=10))
        assert outcome.events_processed == 1
        # case-fold یکسان → یک Entity برای Central Bank
        cbs = session.query(Entity).filter_by(type="central_bank").all()
        assert len(cbs) == 1
        assert session.query(Entity).count() == 2
    finally:
        session.close()


def test_graph_marked_extracted_and_idempotent() -> None:
    _seed_event(
        [
            {"name": "Bank A", "type": "central_bank"},
            {"name": "Country B", "type": "country"},
        ]
    )
    session = TestingSession()
    try:
        first = asyncio.run(KnowledgeGraphEngine(session).run(limit=10))
        assert first.events_processed == 1
        event = session.query(Event).first()
        assert event.graph_extracted is True
        second = asyncio.run(KnowledgeGraphEngine(session).run(limit=10))
        assert second.events_processed == 0
    finally:
        session.close()


def test_fallback_relationships_created() -> None:
    """با Mock رابطه‌ی معتبر ممکن است؛ در هر حال حداقل یک یال ساخته می‌شود."""
    _seed_event(
        [
            {"name": "Actor X", "type": "organization"},
            {"name": "Actor Y", "type": "organization"},
            {"name": "Actor Z", "type": "organization"},
        ]
    )
    session = TestingSession()
    try:
        outcome = asyncio.run(KnowledgeGraphEngine(session).run(limit=10))
        assert outcome.relationships_created >= 1
        assert session.query(EntityRelationship).count() >= 1
    finally:
        session.close()


def test_relationship_link_is_idempotent() -> None:
    """ساختن تکراری همان یال، رکورد جدید نمی‌سازد و weight را تقویت می‌کند."""
    _seed_event(
        [
            {"name": "N1", "type": "organization"},
            {"name": "N2", "type": "organization"},
        ]
    )
    session = TestingSession()
    try:
        from domains.graph.engine import GraphOutcome

        engine = KnowledgeGraphEngine(session)
        event = session.query(Event).first()
        out = GraphOutcome()
        e1, _ = engine.upsert_entity("N1", "organization", outcome=out)
        e2, _ = engine.upsert_entity("N2", "organization", outcome=out)
        session.flush()

        created_first = engine._link(e1, e2, "affects", 0.3, 0.3, event)
        created_second = engine._link(e1, e2, "affects", 0.9, 0.8, event)
        session.commit()

        assert created_first is True
        assert created_second is False  # تکراری → رکورد جدید نه
        rels = session.query(EntityRelationship).all()
        assert len(rels) == 1
        assert rels[0].weight == 0.9  # وزن تقویت شد
    finally:
        session.close()


def test_entity_resolution_merges_alias() -> None:
    """نام دوم همان موجودیت به aliases اضافه می‌شود."""
    session = TestingSession()
    try:
        from domains.graph.engine import GraphOutcome

        engine = KnowledgeGraphEngine(session)
        out = GraphOutcome()
        e1, created1 = engine.upsert_entity("Federal Reserve", "central_bank", outcome=out)
        e2, created2 = engine.upsert_entity("federal reserve", "central_bank", outcome=out)
        session.commit()
        assert created1 is True
        assert created2 is False
        assert e1.id == e2.id
        aliases = json.loads(e1.aliases or "[]")
        assert "federal reserve" in aliases
    finally:
        session.close()


def test_graph_api(client: TestClient) -> None:
    _seed_event(
        [
            {"name": "API Bank", "type": "central_bank"},
            {"name": "API Country", "type": "country"},
        ]
    )
    res = client.post("/api/graph/extract?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["events_processed"] == 1
    assert body["entities_created"] == 2

    entities = client.get("/api/graph/entities").json()
    assert len(entities) == 2

    assert client.get("/api/graph/entities?type=central_bank").json()[0]["type"] == "central_bank"

    eid = entities[0]["id"]
    neighbors = client.get(f"/api/graph/neighbors/{eid}")
    assert neighbors.status_code == 200
    assert isinstance(neighbors.json(), list)


def test_graph_entity_not_found(client: TestClient) -> None:
    res = client.get("/api/graph/entities/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404

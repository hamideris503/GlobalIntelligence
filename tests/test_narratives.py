"""Tests for Narrative Engine analytics, service & API (Phase 24)."""
from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.narrative import Narrative
from backend.database.models.source import Source
from domains.narratives import analytics as an
from domains.narratives.engine import NarrativeEngine
from tests.conftest import TestingSession


def _seed_event_with_articles(
    event_type: str,
    articles: list[dict],
    actors: list[str] | None = None,
) -> str:
    session = TestingSession()
    try:
        src = Source(
            name=f"NarSrc-{uuid.uuid4().hex[:8]}",
            domain="n.local",
            type="rss",
            active=True,
        )
        session.add(src)
        session.flush()
        event = Event(
            event_type=event_type,
            action="test",
            actors=json.dumps(actors or []),
        )
        session.add(event)
        session.flush()
        for art in articles:
            doc = Document(source_id=src.id, title="t", raw_text="x")
            session.add(doc)
            session.flush()
            session.add(
                Article(
                    document_id=doc.id,
                    event_id=event.id,
                    title=art.get("title", "news"),
                    topics=json.dumps(art.get("topics", [])),
                    entities=json.dumps(art.get("entities", [])),
                    stance=art.get("stance"),
                    source_name=art.get("source_name", "SrcA"),
                    classification_status="done",
                )
            )
        session.commit()
        return str(event.id)
    finally:
        session.close()


# --- pure tests ---
def test_linked_rules() -> None:
    assert an.linked({"a"}, {"a"}, set(), set()) is True
    assert an.linked({"a"}, {"b"}, {"x", "y"}, {"x", "y", "z"}) is True
    assert an.linked({"a"}, {"b"}, {"x"}, {"x", "z"}) is False
    assert an.linked(set(), set(), set(), set()) is False


def test_strength_mapping() -> None:
    assert an.strength(10, 5) == 1.0
    assert an.strength(0, 0) == 0.0
    assert an.strength(5, 0) == 0.25


def test_stance_split() -> None:
    assert an.stance_split([]) == (None, None)
    assert an.stance_split(["pos", "pos", "neg"]) == ("pos", round(1 / 3, 4))


def test_build_title() -> None:
    from collections import Counter

    t = an.build_title(Counter({"oil": 3, "opec": 2}), Counter({"market": 2}), 2)
    assert "oil" in t and "(2 events)" in t


def test_union_find_groups() -> None:
    uf = an.UnionFind()
    uf.union(0, 2)
    uf.union(1, 1)
    groups = sorted(uf.groups())
    assert groups == [[0, 2], [1]]


# --- engine tests ---
def test_engine_clusters_shared_entity() -> None:
    _seed_event_with_articles(
        "market", [{"entities": [{"name": "OPEC", "type": "organization"}]}]
    )
    _seed_event_with_articles(
        "market", [{"entities": [{"name": "opec", "type": "organization"}]}]
    )
    _seed_event_with_articles(
        "election", [{"entities": [{"name": "Parliament", "type": "organization"}]}]
    )
    session = TestingSession()
    try:
        outcome = NarrativeEngine(session).build_all(period="2026-10")
        assert outcome.narratives_built == 2
        assert outcome.stored == 2
        rows = session.query(Narrative).all()
        big = max(rows, key=lambda r: r.event_count or 0)
        assert big.event_count == 2
        assert "opec" in big.title
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_event_with_articles("market", [{"entities": [{"name": "OPEC"}]}])
    session = TestingSession()
    try:
        first = NarrativeEngine(session).build_all(period="2026-10")
        assert first.stored == 1
        second = NarrativeEngine(session).build_all(period="2026-10")
        assert second.stored == 0
        assert second.duplicates == 1
        assert session.query(Narrative).count() == 1
    finally:
        session.close()


def test_engine_no_events_skips() -> None:
    session = TestingSession()
    try:
        outcome = NarrativeEngine(session).build_all(period="2026-10")
        assert outcome.skipped == 1
    finally:
        session.close()


# --- API tests ---
def test_narratives_api(client: TestClient) -> None:
    _seed_event_with_articles(
        "market",
        [
            {"entities": [{"name": "OPEC"}], "stance": "pos", "source_name": "SrcA"},
            {"entities": [{"name": "OPEC"}], "stance": "neg", "source_name": "SrcB"},
        ],
    )
    res = client.post("/api/narratives/build?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] == 1

    lst = client.get("/api/narratives?period=2026-10")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    item = lst.json()[0]
    assert item["event_count"] == 1
    assert item["article_count"] == 2
    assert item["source_count"] == 2
    assert item["stance_divergence"] == 0.5

    one = client.get(f"/api/narratives/{item['id']}")
    assert one.status_code == 200
    assert one.json()["signature"] == item["signature"]

    missing = client.get("/api/narratives/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404

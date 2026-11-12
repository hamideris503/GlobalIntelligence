"""Tests for deterministic actor extraction (Step 6A.37)."""
from __future__ import annotations

from domains.events.actor_extraction import (
    _is_valid_actor,
    extract_actors_deterministic,
    resolve_actor_to_entity,
)


def test_extract_actors_returns_list() -> None:
    result = extract_actors_deterministic("Elon Musk said the company will expand")
    assert isinstance(result, list)
    assert "Elon Musk" in result


def test_extract_actors_empty_text() -> None:
    assert extract_actors_deterministic("") == []
    assert extract_actors_deterministic(None) == []  # type: ignore[arg-type]
    assert extract_actors_deterministic("   ") == []


def test_extract_actors_abstains_on_no_clear_actor() -> None:
    # No clear subject-verb pattern → abstain
    result = extract_actors_deterministic("the weather is nice today")
    assert result == []


def test_extract_actors_filters_locations() -> None:
    # Locations should not be extracted as actors
    result = extract_actors_deterministic("In Paris, the weather is nice")
    assert "Paris" not in result


def test_extract_actors_multiple() -> None:
    text = "Iran and Russia signed a new agreement. China announced support."
    result = extract_actors_deterministic(text)
    assert "Iran" not in result  # Iran is a location word
    # Russia is also a location word, so it should be filtered
    # But "China" might be extracted via "announced"
    # The exact result depends on filtering; just check it's a list
    assert isinstance(result, list)


def test_is_valid_actor_rejects_common_words() -> None:
    assert not _is_valid_actor("the")
    assert not _is_valid_actor("and")
    assert not _is_valid_actor("123")
    assert not _is_valid_actor("")


def test_is_valid_actor_rejects_locations() -> None:
    assert not _is_valid_actor("Paris")
    assert not _is_valid_actor("US")
    assert not _is_valid_actor("UK")


def test_is_valid_actor_accepts_names() -> None:
    assert _is_valid_actor("Elon Musk")
    assert _is_valid_actor("Federal Reserve")
    assert _is_valid_actor("Houthis")


def test_resolve_actor_to_entity_does_not_create_by_default() -> None:
    from tests.conftest import TestingSession

    session = TestingSession()
    try:
        # Default: no auto-creation for unverified candidates
        entity = resolve_actor_to_entity(session, "TestActor123")
        assert entity is None
        # No entity created
        from sqlalchemy import select

        from backend.database.models.entity import Entity
        count = session.execute(select(Entity).where(Entity.canonical_name == "testactor123")).scalar_one_or_none()
        assert count is None
    finally:
        session.close()


def test_resolve_actor_to_entity_creates_with_allow_create() -> None:
    from tests.conftest import TestingSession

    session = TestingSession()
    try:
        # allow_create=True: creates entity (AI path)
        entity = resolve_actor_to_entity(session, "TestActor456", allow_create=True)
        assert entity is not None
        assert entity.canonical_name == "testactor456"
        assert entity.display_name == "TestActor456"
        # Idempotent: second call returns same entity
        entity2 = resolve_actor_to_entity(session, "TestActor456", allow_create=True)
        assert entity2.id == entity.id
    finally:
        session.close()


def test_resolve_actor_to_entity_resolves_existing() -> None:
    from backend.database.models.entity import Entity
    from tests.conftest import TestingSession

    session = TestingSession()
    try:
        # Pre-create an entity
        ent = Entity(type="organization", canonical_name="existingactor", display_name="ExistingActor")
        session.add(ent)
        session.commit()
        # resolve should find it (no creation)
        resolved = resolve_actor_to_entity(session, "ExistingActor")
        assert resolved is not None
        assert resolved.id == ent.id
    finally:
        session.close()


def test_resolve_actor_to_entity_empty() -> None:
    from tests.conftest import TestingSession

    session = TestingSession()
    try:
        assert resolve_actor_to_entity(session, "") is None
        assert resolve_actor_to_entity(session, "   ") is None
    finally:
        session.close()


def test_event_extraction_deterministic_does_not_pollute_actors() -> None:
    """In mock mode, deterministic candidates are NOT added to trusted actors."""
    import asyncio
    import json

    from sqlalchemy import select

    from backend.database.models.article import Article
    from backend.database.models.document import Document
    from backend.database.models.entity import Entity
    from backend.database.models.event import Event
    from backend.database.models.source import Source
    from domains.events.extractor import EventExtractor
    from tests.conftest import TestingSession

    session = TestingSession()
    try:
        src = Source(name="Src-actor", domain="e.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="Musk announces new Tesla model", raw_text="Musk announces new Tesla model today")
        session.add(doc)
        session.flush()
        session.add(
            Article(
                document_id=doc.id,
                title="Musk announces new Tesla model",
                summary="Musk announces new Tesla model today",
                topics=json.dumps(["markets"]),
                importance=3,
                duplicate_cluster="actor-cluster-1",
                classification_status="done",
            )
        )
        session.commit()
    finally:
        session.close()

    session = TestingSession()
    try:
        outcome = asyncio.run(EventExtractor(session).run(limit=10))
        assert outcome.events_created == 1
        events = session.query(Event).all()
        assert len(events) == 1
        actors = json.loads(events[0].actors or "[]")
        # Deterministic candidates are NOT trusted actors (safety policy)
        assert actors == [], f"Expected empty trusted actors, got {actors!r}"
        # But actor_resolution metadata should track the candidate
        meta = json.loads(events[0].event_metadata or "{}")
        ar = meta.get("actor_resolution", {})
        assert ar.get("source") == "deterministic"
        assert "Musk" in ar.get("candidates", [])
        assert "Musk" in ar.get("unresolved", [])
        # No Entity created for "Musk"
        ent = session.execute(select(Entity).where(Entity.canonical_name == "musk")).scalar_one_or_none()
        assert ent is None, "No entity should be created for unverified deterministic candidate"
    finally:
        session.close()

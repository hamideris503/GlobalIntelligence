"""Tests for Geopolitical Engine analytics, service & API (Phase 22)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.database.models.entity import Entity, EntityRelationship
from backend.database.models.event import Event
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from domains.geopolitics import analytics as an
from domains.geopolitics.analysis import GeopoliticalEngine, normalize_actor
from tests.conftest import TestingSession


def _seed_event(
    actors: list[str], event_type: str = "conflict", surprise: float | None = 0.8
) -> str:
    session = TestingSession()
    try:
        e = Event(
            event_type=event_type,
            action="test",
            actors=json.dumps(actors),
            surprise=surprise,
        )
        session.add(e)
        session.commit()
        return str(e.id)
    finally:
        session.close()


def _seed_sanction(frm: str, to: str) -> None:
    session = TestingSession()
    try:
        a = Entity(type="country", canonical_name=frm.casefold(), display_name=frm)
        b = Entity(type="country", canonical_name=to.casefold(), display_name=to)
        session.add_all([a, b])
        session.flush()
        session.add(
            EntityRelationship(
                from_entity_id=a.id, to_entity_id=b.id, relation="sanctions"
            )
        )
        session.commit()
    finally:
        session.close()


# --- pure tests ---
def test_normalize_actor() -> None:
    assert normalize_actor("  United   States ") == "united states"


def test_tension_mapping() -> None:
    s = an.tension(
        n_events=10, avg_surprise=1.0, conflict_share=1.0, sanction_links=3
    )
    assert s is not None
    assert s.tension == 1.0
    assert s.confidence == 0.7
    assert an.tension(
        n_events=0, avg_surprise=None, conflict_share=None, sanction_links=0
    ) is None


def test_tension_partial_inputs() -> None:
    s = an.tension(
        n_events=1, avg_surprise=None, conflict_share=None, sanction_links=0
    )
    assert s is not None
    assert s.tension == 0.02  # فقط volume
    assert s.confidence == 0.3


def test_confidence_by_n() -> None:
    assert an.confidence_for(1) == 0.3
    assert an.confidence_for(3) == 0.5
    assert an.confidence_for(5) == 0.7


# --- engine tests ---
def test_engine_groups_and_scores_actors() -> None:
    _seed_event(["Iran", "USA"], event_type="conflict", surprise=0.8)
    _seed_event(["iran"], event_type="election", surprise=0.2)
    session = TestingSession()
    try:
        outcome = GeopoliticalEngine(session).analyze_all(period="2026-10")
        assert outcome.actors_analyzed == 2
        assert outcome.stored == 2
        iran = (
            session.query(GeopoliticalAssessment)
            .filter_by(actor="Iran", period="2026-10")
            .one()
        )
        assert iran.event_count == 2
        assert iran.conflict_share == 0.5
        assert iran.method == "tension_v1"
    finally:
        session.close()


def test_engine_counts_sanction_links() -> None:
    _seed_event(["Iran"], event_type="sanction", surprise=0.5)
    _seed_sanction("USA", "Iran")
    session = TestingSession()
    try:
        GeopoliticalEngine(session).analyze_all(period="2026-10")
        iran = (
            session.query(GeopoliticalAssessment)
            .filter_by(actor="Iran", period="2026-10")
            .one()
        )
        assert iran.sanction_links == 1
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_event(["Iran"], event_type="conflict", surprise=0.8)
    session = TestingSession()
    try:
        first = GeopoliticalEngine(session).analyze_all(period="2026-10")
        assert first.stored == 1
        second = GeopoliticalEngine(session).analyze_all(period="2026-10")
        assert second.stored == 0
        assert second.duplicates == 1
    finally:
        session.close()


def test_engine_no_events_skips() -> None:
    session = TestingSession()
    try:
        outcome = GeopoliticalEngine(session).analyze_all(period="2026-10")
        assert outcome.skipped == 1
        assert outcome.actors_analyzed == 0
    finally:
        session.close()


# --- API tests ---
def test_geopolitics_api(client: TestClient) -> None:
    _seed_event(["Iran", "USA"], event_type="conflict", surprise=0.8)
    res = client.post("/api/geopolitics/analyze?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] == 2

    lst = client.get("/api/geopolitics/assessments?period=2026-10")
    assert lst.status_code == 200
    assert len(lst.json()) == 2
    # مرتب نزولی تنش
    assert lst.json()[0]["tension"] >= lst.json()[1]["tension"]

    ten = client.get("/api/geopolitics/tensions")
    assert ten.status_code == 200
    assert len(ten.json()) == 2

    empty = client.get("/api/geopolitics/tensions?period=1999-01")
    assert empty.status_code == 200
    assert empty.json() == []

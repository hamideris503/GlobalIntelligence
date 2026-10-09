"""Tests for Iran Mode matching, service & API (Phase 33)."""
from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.market import MacroObservation
from backend.database.models.source import Source
from domains.iran import matching as mt
from domains.iran.brief import IranModeService
from tests.conftest import TestingSession


def _seed_event(
    actors: list[str],
    topics: list[str] | None = None,
    country: str | None = None,
) -> str:
    session = TestingSession()
    try:
        src = Source(
            name=f"IranSrc-{uuid.uuid4().hex[:8]}",
            domain="i.local",
            type="rss",
            active=True,
        )
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="x")
        session.add(doc)
        session.flush()
        event = Event(
            event_type="policy", action="test", actors=json.dumps(actors)
        )
        session.add(event)
        session.flush()
        session.add(
            Article(
                document_id=doc.id,
                event_id=event.id,
                title="news",
                topics=json.dumps(topics or []),
                country=country,
                classification_status="done",
            )
        )
        session.commit()
        return str(event.id)
    finally:
        session.close()


# --- pure tests ---
def test_matching_rules() -> None:
    assert mt.is_iran_country("IR") and mt.is_iran_country("irn")
    assert not mt.is_iran_country("US")
    assert not mt.is_iran_country(None)
    assert mt.is_iran_name("Iran") and mt.is_iran_name("Iranian oil")
    assert not mt.is_iran_name("Iraq")  # تطبیق کلمه‌ای، نه زیررشته‌ای
    assert not mt.is_iran_name(None)
    assert mt.is_iran_target("macro:gdp:IRN")
    assert not mt.is_iran_target("market:WTI")
    assert mt.is_iran_source("Tehran Times", "tehrantimes.com") is False
    assert mt.is_iran_source(None, "example.ir") is True


# --- service tests ---
def test_brief_collects_iran_items() -> None:
    _seed_event(["Iran"], topics=["oil"], country="US")
    _seed_event(["France"], topics=["wine"], country="FR")
    session = TestingSession()
    try:
        brief = IranModeService(session).brief()
        assert brief.as_dict()["counts"]["events"] == 1
        assert brief.events[0]["event_type"] == "policy"
    finally:
        session.close()


def test_brief_matches_country_and_topic() -> None:
    _seed_event(["Someone"], topics=["iranian economy"], country=None)
    _seed_event(["Someone"], topics=["sports"], country="IR")
    _seed_event(["Someone"], topics=["sports"], country="US")
    session = TestingSession()
    try:
        brief = IranModeService(session).brief()
        assert brief.as_dict()["counts"]["events"] == 2
    finally:
        session.close()


def test_brief_macro_irn() -> None:
    session = TestingSession()
    try:
        session.add(
            MacroObservation(
                indicator="gdp",
                country="IRN",
                period="2024",
                value=1.0,
                source_name="test",
            )
        )
        session.add(
            MacroObservation(
                indicator="gdp",
                country="USA",
                period="2024",
                value=2.0,
                source_name="test",
            )
        )
        session.commit()
        brief = IranModeService(session).brief()
        assert len(brief.macro) == 1
        assert brief.macro[0]["indicator"] == "gdp"
    finally:
        session.close()


# --- API tests ---
def test_iran_api(client: TestClient) -> None:
    _seed_event(["Iran"], topics=["oil"], country="US")
    res = client.get("/api/iran/brief")
    assert res.status_code == 200
    assert res.json()["counts"]["events"] == 1

    ev = client.get("/api/iran/events")
    assert ev.status_code == 200
    assert len(ev.json()) == 1

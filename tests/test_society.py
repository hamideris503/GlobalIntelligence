"""Tests for Social Engine analytics, service & API (Phase 23)."""
from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.social_assessment import SocialAssessment
from backend.database.models.source import Source
from domains.society import analytics as an
from domains.society.analysis import SocialEngine
from domains.worldstate.signals import SOCIAL_TOPICS
from tests.conftest import TestingSession


def _seed_article(
    topics: list[str],
    sentiment: float | None = 0.2,
    stance: str | None = "neutral",
    country: str | None = "US",
) -> str:
    session = TestingSession()
    try:
        src = Source(
            name=f"SocSrc-{uuid.uuid4().hex[:8]}",
            domain="s.local",
            type="rss",
            active=True,
        )
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="x")
        session.add(doc)
        session.flush()
        art = Article(
            document_id=doc.id,
            title="news",
            topics=json.dumps(topics),
            sentiment=sentiment,
            stance=stance,
            country=country,
            classification_status="done",
        )
        session.add(art)
        session.commit()
        return str(art.id)
    finally:
        session.close()


# --- pure tests ---
def test_mood_mapping() -> None:
    s = an.mood([0.5, -0.5], [{"economy"}, {"protest"}], ["pos", "neg"], SOCIAL_TOPICS)
    assert s is not None
    assert s.avg_sentiment == 0.0
    assert s.article_count == 2
    assert s.unrest_share == 0.5
    assert s.stance_mix == {"pos": 1, "neg": 1}
    assert s.confidence == 0.5


def test_mood_empty_is_none() -> None:
    assert an.mood([], [], [], SOCIAL_TOPICS) is None


def test_mood_no_sentiment() -> None:
    s = an.mood([None], [{"economy"}], [None], SOCIAL_TOPICS)
    assert s is not None
    assert s.avg_sentiment is None
    assert s.unrest_share == 0.0
    assert s.stance_mix == {}


def test_confidence_by_n() -> None:
    assert an.confidence_for(1) == 0.3
    assert an.confidence_for(3) == 0.5
    assert an.confidence_for(5) == 0.7


# --- engine tests ---
def test_engine_groups_topic_and_country() -> None:
    _seed_article(["economy", "protest"], sentiment=0.4, stance="pos", country="US")
    _seed_article(["economy"], sentiment=-0.2, stance="neg", country="US")
    session = TestingSession()
    try:
        outcome = SocialEngine(session).analyze_all(period="2026-10")
        # قلمروها: topic:economy، topic:protest، country:US
        assert outcome.scopes_analyzed == 3
        assert outcome.stored == 3
        eco = (
            session.query(SocialAssessment)
            .filter_by(scope_type="topic", scope="economy", period="2026-10")
            .one()
        )
        assert eco.avg_sentiment == 0.1
        assert eco.unrest_share == 0.5
        assert eco.article_count == 2
    finally:
        session.close()


def test_engine_is_idempotent() -> None:
    _seed_article(["economy"], sentiment=0.1, country="US")
    session = TestingSession()
    try:
        first = SocialEngine(session).analyze_all(period="2026-10")
        assert first.stored == 2  # topic + country
        second = SocialEngine(session).analyze_all(period="2026-10")
        assert second.stored == 0
        assert second.duplicates == 2
    finally:
        session.close()


def test_engine_ignores_pending_articles() -> None:
    session = TestingSession()
    try:
        src = Source(
            name=f"SocSrc-{uuid.uuid4().hex[:8]}",
            domain="s.local",
            type="rss",
            active=True,
        )
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="x")
        session.add(doc)
        session.flush()
        session.add(
            Article(
                document_id=doc.id,
                title="pending",
                topics=json.dumps(["economy"]),
                classification_status="pending",
            )
        )
        session.commit()
        outcome = SocialEngine(session).analyze_all(period="2026-10")
        assert outcome.scopes_analyzed == 0
        assert outcome.skipped == 1
    finally:
        session.close()


# --- API tests ---
def test_society_api(client: TestClient) -> None:
    _seed_article(["protest"], sentiment=-0.6, stance="neg", country="IR")
    res = client.post("/api/society/analyze?period=2026-10")
    assert res.status_code == 200
    assert res.json()["stored"] == 2

    lst = client.get("/api/society/assessments?period=2026-10")
    assert lst.status_code == 200
    assert len(lst.json()) == 2

    mood_res = client.get("/api/society/mood?scope_type=topic")
    assert mood_res.status_code == 200
    assert len(mood_res.json()) == 1
    assert mood_res.json()[0]["unrest_share"] == 1.0

"""Tests for source independence (Phase 14)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from backend.database.models.source_dependency import SourceDependency
from domains.news.independence import (
    SourceDependencyService,
    SourceIndependenceEngine,
)
from tests.conftest import TestingSession


def _mk_source(session, name: str, domain: str, *, credibility: float = 0.8) -> Source:
    s = Source(
        name=name, domain=domain, type="rss", active=True, credibility_score=credibility
    )
    session.add(s)
    session.flush()
    return s


def _seed_event_with_sources(domains: list[str]) -> str:
    """یک رویداد با یک مقاله به‌ازای هر منبع (بر اساس domain)."""
    session = TestingSession()
    try:
        event = Event(
            event_type="monetary_policy",
            action="The central bank raised rates",
            actors=json.dumps(["Central Bank"]),
            claims_extracted=True,
        )
        session.add(event)
        session.flush()
        for i, dom in enumerate(domains):
            src = _mk_source(session, f"Src-{dom}-{i}", dom)
            doc = Document(source_id=src.id, title=f"story {i}", raw_text="rates up")
            session.add(doc)
            session.flush()
            art = Article(
                document_id=doc.id,
                event_id=event.id,
                title=f"story {i}",
                summary="rates up",
                classification_status="done",
            )
            session.add(art)
        claim = Claim(
            event_id=event.id,
            subject="Central Bank",
            predicate="raised",
            object="rate",
            verification_status="unverified",
        )
        session.add(claim)
        session.commit()
        return str(claim.id)
    finally:
        session.close()


def test_same_domain_sources_collapse_to_one_independent() -> None:
    """سه منبع که دو تای آن‌ها هم‌دامنه‌اند → ۳ mention ولی ۲ مستقل."""
    _seed_event_with_sources(["a.local", "a.local", "b.local"])
    session = TestingSession()
    try:
        claim = session.query(Claim).first()
        engine = SourceIndependenceEngine(session)
        mapping, n_sources, _edges = engine.build_groups()
        assert n_sources == 3
        supporting, independent, ratio = engine.compute_for_claim(claim, mapping)
        assert supporting == 3
        assert independent == 2
        assert ratio == round(2 / 3, 4)
    finally:
        session.close()


def test_explicit_dependency_merges_sources() -> None:
    """یال وابستگی دستی، دو منبع با domain متفاوت را یکی می‌کند."""
    _seed_event_with_sources(["x.local", "y.local"])
    session = TestingSession()
    try:
        s1 = session.query(Source).filter_by(domain="x.local").first()
        s2 = session.query(Source).filter_by(domain="y.local").first()
        SourceDependencyService(session).add(s1.id, s2.id, kind="syndication")

        claim = session.query(Claim).first()
        engine = SourceIndependenceEngine(session)
        mapping, _n, edges = engine.build_groups()
        assert edges >= 1
        _supporting, independent, _ratio = engine.compute_for_claim(claim, mapping)
        assert independent == 1
    finally:
        session.close()


def test_corroborated_requires_two_independent_sources() -> None:
    """با دو منبع هم‌دامنه، status نباید corroborated شود (یک تأیید مستقل)."""
    _seed_event_with_sources(["same.local", "same.local"])
    session = TestingSession()
    try:
        outcome = SourceIndependenceEngine(session).run(limit=10)
        assert outcome.claims_processed == 1
        claim = session.query(Claim).first()
        assert claim.supporting_source_count == 2
        assert claim.independent_source_count == 1
        assert claim.verification_status == "single_source"
    finally:
        session.close()


def test_two_independent_sources_corroborated() -> None:
    _seed_event_with_sources(["one.local", "two.local"])
    session = TestingSession()
    try:
        SourceIndependenceEngine(session).run(limit=10)
        claim = session.query(Claim).first()
        assert claim.independent_source_count == 2
        assert claim.verification_status == "corroborated"
    finally:
        session.close()


def test_dependency_unique_pair() -> None:
    session = TestingSession()
    try:
        s1 = _mk_source(session, "A", "a.local")
        s2 = _mk_source(session, "B", "b.local")
        session.commit()
        svc = SourceDependencyService(session)
        d1 = svc.add(s1.id, s2.id)
        d2 = svc.add(s1.id, s2.id)  # تکراری → همان رکورد
        assert d1.id == d2.id
        assert session.query(SourceDependency).count() == 1
    finally:
        session.close()


def test_independence_api(client: TestClient) -> None:
    _seed_event_with_sources(["p.local", "q.local"])
    res = client.post("/api/independence/run?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["claims_processed"] == 1
    assert body["corroborated"] == 1

    groups = client.get("/api/independence/groups")
    assert groups.status_code == 200
    assert len(groups.json()) >= 2


def test_dependency_api_crud(client: TestClient) -> None:
    s1 = client.post("/api/sources", json={"name": "D1", "type": "rss"}).json()["id"]
    s2 = client.post("/api/sources", json={"name": "D2", "type": "rss"}).json()["id"]

    created = client.post(
        "/api/independence/dependencies",
        json={"source_id": s1, "depends_on_id": s2, "kind": "aggregator"},
    )
    assert created.status_code == 201
    dep_id = created.json()["id"]

    listing = client.get("/api/independence/dependencies")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    deleted = client.delete(f"/api/independence/dependencies/{dep_id}")
    assert deleted.status_code == 204
    assert client.get("/api/independence/dependencies").json() == []


def test_self_dependency_rejected(client: TestClient) -> None:
    sid = client.post("/api/sources", json={"name": "Self", "type": "rss"}).json()["id"]
    res = client.post(
        "/api/independence/dependencies",
        json={"source_id": sid, "depends_on_id": sid},
    )
    assert res.status_code == 400


def test_claim_api_exposes_independence(client: TestClient) -> None:
    _seed_event_with_sources(["m.local", "n.local"])
    client.post("/api/independence/run?limit=10")
    claims = client.get("/api/claims").json()
    assert claims
    c = claims[0]
    assert c["supporting_source_count"] == 2
    assert c["independent_source_count"] == 2
    assert c["source_independence"] == 1.0

"""Tests for GraphRAG-lite retrieval & API (Phase 52)."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.database.models.entity import Entity, EntityRelationship
from domains.research.graphrag import GraphRAGService
from tests.conftest import TestingSession


def _seed_graph() -> None:
    """A -affects-> B -supplies-> C ؛ D ایزوله."""
    session = TestingSession()
    try:
        a = Entity(type="organization", canonical_name="a", display_name="A")
        b = Entity(type="organization", canonical_name="b", display_name="B")
        c = Entity(type="organization", canonical_name="c", display_name="C")
        d = Entity(type="organization", canonical_name="d", display_name="D")
        session.add_all([a, b, c, d])
        session.flush()
        session.add_all(
            [
                EntityRelationship(
                    from_entity_id=a.id, to_entity_id=b.id,
                    relation="affects", weight=0.8,
                ),
                EntityRelationship(
                    from_entity_id=b.id, to_entity_id=c.id,
                    relation="supplies", weight=0.6,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()


# --- service tests ---
def test_retrieve_two_hops() -> None:
    _seed_graph()
    session = TestingSession()
    try:
        ctx = GraphRAGService(session).retrieve(entity_names=["A"], hops=2)
        names = {n["name"] for n in ctx.nodes}
        assert {"A", "B", "C"} <= names
        assert "D" not in names
        assert len(ctx.edges) == 2
        assert ctx.truncated is False
    finally:
        session.close()


def test_retrieve_hop_limit() -> None:
    _seed_graph()
    session = TestingSession()
    try:
        ctx = GraphRAGService(session).retrieve(entity_names=["A"], hops=1)
        names = {n["name"] for n in ctx.nodes}
        assert "B" in names
        assert "C" not in names
        assert len(ctx.edges) == 1
    finally:
        session.close()


def test_retrieve_limit_truncates() -> None:
    _seed_graph()
    session = TestingSession()
    try:
        ctx = GraphRAGService(session).retrieve(entity_names=["A"], limit=1)
        assert len(ctx.edges) == 1
        assert ctx.truncated is True
    finally:
        session.close()


def test_retrieve_unknown_entity_empty() -> None:
    _seed_graph()
    session = TestingSession()
    try:
        ctx = GraphRAGService(session).retrieve(entity_names=["Nope"])
        assert ctx.nodes == [] and ctx.edges == []
    finally:
        session.close()


def test_retrieve_case_insensitive() -> None:
    _seed_graph()
    session = TestingSession()
    try:
        ctx = GraphRAGService(session).retrieve(entity_names=["  a  "])
        assert {n["name"] for n in ctx.nodes} >= {"A", "B"}
    finally:
        session.close()


def test_synthesize_mock_extractive() -> None:
    _seed_graph()
    session = TestingSession()
    try:
        service = GraphRAGService(session)
        ctx = service.retrieve(entity_names=["A"])
        out = asyncio.run(service.synthesize(ctx))
        assert out["mode"] == "extractive"
        assert "A affects B" in out["key_relations"]
    finally:
        session.close()


def test_synthesize_empty() -> None:
    session = TestingSession()
    try:
        service = GraphRAGService(session)
        ctx = service.retrieve(entity_names=["Nope"])
        out = asyncio.run(service.synthesize(ctx))
        assert out["mode"] == "empty"
    finally:
        session.close()


# --- API tests ---
def test_graphrag_api(client: TestClient) -> None:
    _seed_graph()
    res = client.post(
        "/api/research/graphrag",
        json={"entity_names": ["A"], "hops": 2, "synthesize": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["edges"]) == 2
    assert body["synthesis"]["mode"] == "extractive"

    bad_empty = client.post("/api/research/graphrag", json={"entity_names": []})
    assert bad_empty.status_code == 422

    bad_hops = client.post(
        "/api/research/graphrag", json={"entity_names": ["A"], "hops": 9}
    )
    assert bad_hops.status_code == 422

    methods = client.get("/api/research/methods")
    assert methods.status_code == 200
    assert "graphrag_lite" in methods.json()["implemented"]

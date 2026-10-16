"""Tests for GraphRAG-lite retrieval & API (Phase 52)."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend.ai.schemas.types import AIResponse
from backend.database.models.entity import Entity, EntityRelationship
from domains.research.graphrag import GraphContext, GraphRAGService
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


# --- real-provider-like response parsing (offline stubs, no network) ---
VALID_TEXT = json.dumps(
    {"summary": "s", "key_relations": ["A rel B", "C rel D"]}
)


class _StubGateway:
    """Gateway stub آفلاین: پاسخ واقعی‌نما (text/structured) برمی‌گرداند."""

    def __init__(self, *, text="", structured=None):
        self.text = text
        self.structured = structured
        self.requests = []

    async def structured_generate(self, request, schema):
        self.requests.append(request)
        return AIResponse(text=self.text, provider="stub-live-like",
                           model="stub-1", structured=self.structured)


def _ctx(n=2) -> GraphContext:
    edges = [{"from": f"A{i}", "to": f"B{i}", "relation": "rel",
              "weight": 0.5, "confidence": 0.5} for i in range(n)]
    nodes = [{"id": f"n{i}", "name": f"N{i}", "type": "x",
              "weighted_degree": 1.0} for i in range(n + 1)]
    return GraphContext(nodes=nodes, edges=edges)


def _stub_service(*, text="", structured=None) -> GraphRAGService:
    service = GraphRAGService(None)
    service._settings = service._settings.model_copy(update={"mock_mode": False})
    service.gateway = _StubGateway(text=text, structured=structured)
    return service


def test_synth_text_valid_structured_none() -> None:
    out = asyncio.run(_stub_service(text=VALID_TEXT).synthesize(_ctx()))
    assert out["mode"] == "llm"
    assert out["summary"] == "s"
    assert out["key_relations"] == ["A rel B", "C rel D"]


def test_synth_structured_valid_used() -> None:
    data = {"summary": "from-structured", "key_relations": ["X rel Y"]}
    out = asyncio.run(
        _stub_service(text="garbage {{{", structured=data).synthesize(_ctx()))
    assert out["mode"] == "llm"
    assert out["summary"] == "from-structured"


def test_synth_empty_structured_falls_back_to_text() -> None:
    out = asyncio.run(
        _stub_service(text=VALID_TEXT, structured={}).synthesize(_ctx()))
    assert out["mode"] == "llm"
    assert out["summary"] == "s"


def test_synth_invalid_structured_falls_back_to_text() -> None:
    out = asyncio.run(
        _stub_service(text=VALID_TEXT,
                      structured={"summary": 1}).synthesize(_ctx()))
    assert out["mode"] == "llm"
    assert out["summary"] == "s"


def test_synth_invalid_json_fails() -> None:
    out = asyncio.run(_stub_service(text="not json {{{").synthesize(_ctx()))
    assert out["mode"] == "failed"
    assert out["summary"] == "" and out["key_relations"] == []
    assert out["reason"] == "invalid_json"


def test_synth_truncated_json_fails() -> None:
    out = asyncio.run(
        _stub_service(text='{"summary": "abc", "key_relations": ["x"')
        .synthesize(_ctx()))
    assert out["mode"] == "failed"
    assert out["summary"] == ""


def test_synth_schema_invalid_fails() -> None:
    missing = asyncio.run(
        _stub_service(text=json.dumps({"summary": "s"})).synthesize(_ctx()))
    assert missing["mode"] == "failed"
    assert missing["reason"] == "schema_mismatch"
    wrong_type = asyncio.run(
        _stub_service(text=json.dumps({"summary": "s", "key_relations": [1]}))
        .synthesize(_ctx()))
    assert wrong_type["mode"] == "failed"


def test_synth_empty_response_fails() -> None:
    out = asyncio.run(_stub_service(text="", structured=None).synthesize(_ctx()))
    assert out["mode"] == "failed"
    assert out["reason"] == "empty_response"
    assert asyncio.run(
        _stub_service(text="", structured={}).synthesize(_ctx()))["mode"] == "failed"


def test_synth_relations_capped_at_ten() -> None:
    rels = [f"A{i} rel B{i}" for i in range(15)]
    text = json.dumps({"summary": "s", "key_relations": rels})
    out = asyncio.run(_stub_service(text=text).synthesize(_ctx()))
    assert out["mode"] == "llm"
    assert out["key_relations"] == rels[:10]


def test_synth_fenced_json_accepted() -> None:
    out = asyncio.run(
        _stub_service(text="```json\n" + VALID_TEXT + "\n```").synthesize(_ctx()))
    assert out["mode"] == "llm"
    assert out["summary"] == "s"


def test_synth_failure_does_not_log_response_text(caplog) -> None:
    canary = "CANARY-SECRET-8421"
    with caplog.at_level("WARNING"):
        out = asyncio.run(
            _stub_service(text=f"broken {canary} {{{{").synthesize(_ctx()))
    assert out["mode"] == "failed"
    assert canary not in caplog.text


def test_synth_gateway_error_fails_without_leak(caplog) -> None:
    class _Boom:
        async def structured_generate(self, request, schema):
            raise RuntimeError("boom CANARY-9917")

    service = GraphRAGService(None)
    service._settings = service._settings.model_copy(update={"mock_mode": False})
    service.gateway = _Boom()
    with caplog.at_level("WARNING"):
        out = asyncio.run(service.synthesize(_ctx()))
    assert out["mode"] == "failed"
    assert out["reason"] == "gateway_error"
    assert "CANARY-9917" not in caplog.text

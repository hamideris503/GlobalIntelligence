"""Tests for the evidence engine (Phase 13)."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.source import Source
from domains.claims.evidence import EvidenceEngine, verify_status
from domains.claims.evidence_prompts import EVIDENCE_SCHEMA
from tests.conftest import TestingSession


# --- verify_status (deterministic) ---
def test_verify_status_matrix() -> None:
    assert verify_status(0, 0) == "unverified"
    assert verify_status(1, 0) == "single_source"
    assert verify_status(2, 0) == "corroborated"
    assert verify_status(0, 1) == "contradicted"
    assert verify_status(1, 1) == "disputed"


def test_evidence_schema() -> None:
    assert EVIDENCE_SCHEMA["type"] == "object"
    assert "evidence" in EVIDENCE_SCHEMA["properties"]


def _seed_claim() -> str:
    session = TestingSession()
    try:
        src = Source(name="EvSrc", domain="e.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="cb raises", raw_text="The central bank raised rates.")
        session.add(doc)
        session.flush()
        art = Article(
            document_id=doc.id, title="cb raises", summary="The central bank raised rates.",
            topics=json.dumps(["monetary_policy"]), classification_status="done",
        )
        session.add(art)
        session.flush()
        event = Event(
            event_type="monetary_policy", action="The central bank raised rates.",
            actors=json.dumps(["Central Bank"]), sources=json.dumps([str(src.id)]),
            claims_extracted=True,
        )
        session.add(event)
        session.flush()
        art.event_id = event.id
        claim = Claim(
            event_id=event.id, subject="Central Bank", predicate="raised",
            object="interest rate", claim_type="monetary_policy",
            verification_status="unverified", evidence_extracted=False,
        )
        session.add(claim)
        session.commit()
        return str(claim.id)
    finally:
        session.close()


def test_collect_evidence_for_claim() -> None:
    _seed_claim()
    session = TestingSession()
    try:
        outcome = asyncio.run(EvidenceEngine(session).run(limit=10))
        assert outcome.claims_processed == 1
        claim = session.query(Claim).first()
        assert claim.evidence_extracted is True
        assert claim.verification_status in {
            "unverified", "single_source", "corroborated", "contradicted", "disputed"
        }
    finally:
        session.close()


def test_evidence_idempotent() -> None:
    _seed_claim()
    session = TestingSession()
    try:
        first = asyncio.run(EvidenceEngine(session).run(limit=10))
        second = asyncio.run(EvidenceEngine(session).run(limit=10))
        assert first.claims_processed == 1
        assert second.claims_processed == 0
    finally:
        session.close()


def test_evidence_api(client: TestClient) -> None:
    _seed_claim()
    res = client.post("/api/claims/evidence?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["claims_processed"] == 1

    claims = client.get("/api/claims").json()
    assert len(claims) == 1
    assert "evidence" in claims[0]


def test_claim_without_event_ok() -> None:
    """claims بدون رویداد نباید خطا بدهد."""
    session = TestingSession()
    try:
        claim = Claim(subject="X", predicate="is", object="Y", evidence_extracted=False)
        session.add(claim)
        session.commit()
    finally:
        session.close()
    session = TestingSession()
    try:
        outcome = asyncio.run(EvidenceEngine(session).run(limit=10))
        assert outcome.failed == 0
        assert outcome.claims_processed == 1
    finally:
        session.close()


def test_ingest_items_manual_data() -> None:
    """منطق Engine با داده‌ی دستی (بدون Mock): 2 معتبر + 1 نامعتبر."""
    _seed_claim()
    session = TestingSession()
    try:
        claim = session.query(Claim).first()
        engine = EvidenceEngine(session)
        crafted = [
            {"direction": "supports", "summary": "rates raised", "weight": 0.8},
            {"direction": "contradicts", "summary": "denied by bank", "weight": 0.6},
            {"direction": "mock", "summary": "invalid direction"},
            "not-a-dict",
        ]
        result = engine._ingest_items(claim, crafted)
        session.commit()

        assert len(result.created) == 2
        assert result.rejected == 2
        directions = sorted(e.direction for e in result.created)
        assert directions == ["contradicts", "supports"]
        # منبع باید از سندِ مبنا پر شده باشد (موردنیاز Phase 14)
        assert all(e.source_id is not None for e in result.created)

        supports = sum(1 for e in claim.evidence if e.direction == "supports")
        contradicts = sum(1 for e in claim.evidence if e.direction == "contradicts")
        claim.verification_status = verify_status(supports, contradicts)
        session.commit()
        assert claim.verification_status == "disputed"
    finally:
        session.close()

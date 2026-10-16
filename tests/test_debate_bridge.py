"""Tests for debate->decision bridge hard gates (Step 5)."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.debate import DebateMessage, DebateRun
from backend.database.models.recommendation import Recommendation
from domains.decision.debate_bridge import NOT_FINANCIAL_ADVICE_FA, build_proposal
from tests.conftest import TestingSession


def _seed_run(session, status="done", consensus=0.7, disagreement=0.1,
              target="market:WTI") -> uuid.UUID:
    run = DebateRun(
        target=target, horizon_days=30, target_date=datetime.now(UTC),
        status=status, context_hash="abc123", reference_price=90.0,
        consensus_probability=consensus, disagreement=disagreement,
        confidence=0.6,
        context_pack=json.dumps({"events": [{"ref_id": "E1", "event_id": "e" * 32}],
                                            "claims": []}),
    )
    session.add(run)
    session.flush()
    for agent in ("bull", "bear"):
        session.add(DebateMessage(
            run_id=run.id, round_no=2, agent=agent, provider="fake",
            model="fake-1", probability_up=consensus, confidence=0.6,
            quality_score=1.0,
            response_text=json.dumps({
                "key_evidence": [{"ref_id": "E1", "why": "r"}],
                "invalidation_conditions": ["if x then not"],
            }),
        ))
    session.commit()
    return run.id


def _rec(session, decision_id: str) -> Recommendation:
    return session.get(Recommendation, uuid.UUID(decision_id))


def test_gate_failed_run_is_insufficient() -> None:
    session = TestingSession()
    try:
        rid = _seed_run(session, status="failed", consensus=None)
        out = build_proposal(session, rid)
        assert out.decision == "insufficient_evidence"
        assert _rec(session, out.decision_id).model == "decision_debate_v1"
    finally:
        session.close()


def test_gate_high_disagreement_is_no_action() -> None:
    session = TestingSession()
    try:
        rid = _seed_run(session, disagreement=0.5)
        out = build_proposal(session, rid)
        assert out.decision == "no_action"
        rec = _rec(session, out.decision_id)
        assert "0.5" in (rec.evidence_for or "")
    finally:
        session.close()


def test_experimental_when_scorecard_insufficient() -> None:
    session = TestingSession()
    try:
        rid = _seed_run(session, consensus=0.7)
        out = build_proposal(session, rid)
        assert out.decision == "hold"
        assert out.experimental is True  # کارنامه ناکافی است
        rec = _rec(session, out.decision_id)
        assert rec.model == "decision_debate_v1:experimental"
        assert rec.direction == "up"
        assert rec.probability_up == 0.7
        assert rec.probability_down == 0.3
        assert rec.invalidation == "if x then not"
        assert NOT_FINANCIAL_ADVICE_FA in (rec.main_risks or "")
        assert "event:" in (rec.evidence_for or "")
    finally:
        session.close()


def test_missing_run() -> None:
    session = TestingSession()
    try:
        out = build_proposal(session, uuid.uuid4())
        assert out.decision == "failed"
        assert out.decision_id is None
    finally:
        session.close()


def test_from_debate_api(client: TestClient) -> None:
    session = TestingSession()
    try:
        rid = _seed_run(session, consensus=0.3)
    finally:
        session.close()
    res = client.post(f"/api/decisions/from-debate?run_id={rid}")
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "hold"
    assert body["experimental"] is True
    got = client.get(f"/api/decisions/{body['decision_id']}")
    assert got.status_code == 200
    assert got.json()["direction"] == "down"

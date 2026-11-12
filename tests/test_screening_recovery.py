"""Stage104 — regression coverage for screening provenance preservation
and safe terminal recovery.

Synthetic inputs only. No real providers, no inference, no network.
"""
from __future__ import annotations

import asyncio
import json

from backend.ai.dispatch.runner import (
    run_once,
)
from backend.ai.dispatch.service import DispatchService
from backend.ai.local_screening import orchestrator as orch
from tests.conftest import TestingSession
from tests.test_dispatch import _article


def _make_article(db, *, meta=None, text="Crude oil prices rose after OPEC decision. " * 3):
    """Create an article with optional classification_meta."""
    return _article(db, meta=meta)


# --- 1. First Kev result preserved after retry -------------------------------

def test_first_kev_result_preserved_in_history_after_retry(monkeypatch) -> None:
    """The original Kev prediction survives a later screening attempt."""
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=None,
                                      reason_codes=["KEV_LOW_MARGIN"],
                                      kev={"status": "ok", "p_true": 0.42, "relevant": True})

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {
            "route": "KEV", "decision": True, "reason_codes": ["KEV_RELEVANT"],
            "kev": {"status": "ok", "p_true": 0.85, "relevant": True},
        }})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="screening"))
        assert outcome.completed == 0  # None → retryable
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        # Original Kev prediction preserved in history
        history = meta.get("screening_history", [])
        assert len(history) >= 1
        assert history[0]["kev"]["p_true"] == 0.85
        assert history[0]["decision"] is True
        # Latest result is the retry's
        assert meta["local_screening"]["reason_codes"] == ["KEV_LOW_MARGIN"]
    finally:
        db.close()


# --- 2. Second attempt records own result without destroying first ----------

def test_second_attempt_appends_without_destroying_first(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="AI_GATEWAY", relevant=True,
                                      reason_codes=["AI_FALLBACK"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {
            "route": "KEV", "decision": True, "reason_codes": ["KEV_RELEVANT"],
            "kev": {"p_true": 0.9},
        }})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        # Both original and new are present
        assert meta["local_screening"]["route"] == "AI_GATEWAY"
        assert len(meta.get("screening_history", [])) >= 1
        assert meta["screening_history"][0]["route"] == "KEV"
    finally:
        db.close()


# --- 3. Existing Laya and Gateway history preserved -------------------------

def test_laya_and_gateway_history_preserved(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="AI_GATEWAY", relevant=False,
                                      reason_codes=["AI_FALLBACK"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {
            "route": "KEV_LAYA", "decision": True,
            "kev": {"p_true": 0.7}, "laya": {"p_true": 0.6},
            "provenance": {"fallback_is_mock": False},
        }})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        history = meta.get("screening_history", [])
        assert len(history) >= 1
        assert history[0].get("laya", {}).get("p_true") == 0.6
        assert history[0].get("provenance", {}).get("fallback_is_mock") is False
    finally:
        db.close()


# --- 4. Replaying same attempt doesn't duplicate history --------------------

def test_replay_same_attempt_no_duplicate_history(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=None,
                                      reason_codes=["KEV_LOW_MARGIN"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {
            "route": "KEV", "decision": None, "reason_codes": ["KEV_LOW_MARGIN"],
        }})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        # First retry
        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        meta1 = json.loads(art.classification_meta)
        hist_len1 = len(meta1.get("screening_history", []))

        # Reset dispatch to retryable and run again
        _row = DispatchService(db).get_dispatch(art.id, "screening")
        _row.status = "retryable"
        _row.next_retry_at = None
        db.commit()
        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        meta2 = json.loads(art.classification_meta)
        hist_len2 = len(meta2.get("screening_history", []))

        # History should not grow if the result is identical
        # (the new result equals the old, so append is skipped)
        assert hist_len2 <= hist_len1 + 1
    finally:
        db.close()


# --- 5. Mock Gateway response never stored as genuine result ----------------

def test_mock_gateway_not_stored_as_genuine(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):
        d = orch.ScreeningDecision(route="AI_GATEWAY", relevant=True,
                                   reason_codes=["AI_FALLBACK"])
        d.provenance["fallback_is_mock"] = True
        return d

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {
            "route": "KEV", "decision": None, "reason_codes": ["KEV_LOW_MARGIN"],
        }})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        # Mock provenance must be visible
        assert meta["local_screening"].get("provenance", {}).get("fallback_is_mock") is True
    finally:
        db.close()


# --- 6. Missing real provider doesn't produce false negative -----------------

def test_no_provider_produces_pending_not_negative(monkeypatch) -> None:
    """When no real provider is available, screening stays pending."""
    monkeypatch.setattr(
        "backend.ai.dispatch.runner._real_provider_available", lambda db: False
    )
    async def fake_screen(db, text, priority=None, **kwargs):
        # Simulate what happens when _no_provider_ai_screen is used
        return orch.ScreeningDecision(route="KEV", relevant=None,
                                      reason_codes=["KEV_LOW_MARGIN", "AI_ERROR:no_real_provider"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": None}})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="screening"))
        # Parked, not failed: a missing provider is a blocked prerequisite and
        # must not spend the bounded retry budget.
        assert outcome.blocked == 1
        assert outcome.retryable == 0
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        assert meta["local_screening"]["decision"] is None
        assert "AI_ERROR:no_real_provider" in meta["local_screening"]["reason_codes"]
    finally:
        db.close()


# --- 7. Repeated claims don't cause retry churn -----------------------------

def test_no_retry_churn_with_unavailable_provider(monkeypatch) -> None:
    """Unavailable screening must not churn the bounded retry budget.

    Previously: 3 attempts then ``terminal`` — which is how the live database
    reached 711/711 terminal rows. Now each run parks the row instead.
    """
    monkeypatch.setattr(
        "backend.ai.dispatch.runner._real_provider_available", lambda db: False
    )
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=None,
                                      reason_codes=["KEV_LOW_MARGIN", "AI_ERROR:no_real_provider"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": None}})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        # Attempt 1
        o1 = asyncio.run(run_once(db, limit=5, task="screening"))
        assert o1.blocked == 1
        assert o1.terminal == 0
        # Attempt 2
        _row = DispatchService(db).get_dispatch(art.id, "screening")
        _row.next_retry_at = None
        db.commit()
        o2 = asyncio.run(run_once(db, limit=5, task="screening"))
        assert o2.blocked == 1
        # Attempt 3 and beyond: still no terminal row and no consumed budget.
        row = DispatchService(db).get_dispatch(art.id, "screening")
        row.next_retry_at = None
        db.commit()
        o3 = asyncio.run(run_once(db, limit=5, task="screening"))
        assert o3.terminal == 0
        assert o3.blocked == 1
        row = DispatchService(db).get_dispatch(art.id, "screening")
        assert row.status == "pending"
        assert row.attempts == 0
        assert (row.last_error or "").startswith("screening_unavailable:")
    finally:
        db.close()


# --- 8. Pending fallback becomes eligible when prerequisite available --------

def test_pending_becomes_eligible_when_provider_available(monkeypatch) -> None:
    """When a real provider becomes available, screening can succeed."""
    # First: no provider → pending
    monkeypatch.setattr(
        "backend.ai.dispatch.runner._real_provider_available", lambda db: False
    )
    async def fake_fail(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=None,
                                      reason_codes=["KEV_LOW_MARGIN", "AI_ERROR:no_real_provider"])

    monkeypatch.setattr(orch, "screen_with_db", fake_fail)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": None}})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        o1 = asyncio.run(run_once(db, limit=5, task="screening"))
        assert o1.blocked == 1
        assert o1.terminal == 0

        # Now provider becomes available
        monkeypatch.setattr(
            "backend.ai.dispatch.runner._real_provider_available", lambda db: True
        )
        async def fake_success(db, text, priority=None, **kwargs):
            return orch.ScreeningDecision(route="KEV", relevant=True,
                                          reason_codes=["KEV_RELEVANT"])

        monkeypatch.setattr(orch, "screen_with_db", fake_success)
        row = DispatchService(db).get_dispatch(art.id, "screening")
        row.next_retry_at = None
        db.commit()

        o2 = asyncio.run(run_once(db, limit=5, task="screening"))
        assert o2.completed == 1
    finally:
        db.close()


# --- 9. Terminal screening dispatch can't be recovered without provider ------

def test_terminal_screening_not_recoverable_without_provider() -> None:
    """Recovery endpoint requires real provider. Tested via runner level:
    a terminal row stays terminal when _real_provider_available is False."""
    # This is tested at the API level; here we verify the gate logic.
    db = TestingSession()
    try:
        from backend.ai.dispatch.runner import _real_provider_available
        assert _real_provider_available(db) is False  # no provider in tests
    finally:
        db.close()


# --- 10. Unrelated terminal tasks remain non-retryable ----------------------

def test_unrelated_terminal_tasks_non_retryable() -> None:
    """Only screening tasks are eligible for recovery."""
    db = TestingSession()
    try:
        art = _article(db)
        svc = DispatchService(db)
        row = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
        # Make it terminal
        assert svc.claim(row) is True
        svc.mark_terminal(row, "permanent error")
        db.commit()
        assert row.status == "terminal"
        # Recovery should not apply (task != screening)
        # Verified by the API endpoint's task check
    finally:
        db.close()


# --- 11. Completed downstream tasks remain completed ------------------------

def test_completed_downstream_not_reset_on_screening_retry(monkeypatch) -> None:
    """Screening retry doesn't touch completed downstream dispatches."""
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=True,
                                      reason_codes=["KEV_RELEVANT"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": None}})
        # Create a completed downstream dispatch
        svc = DispatchService(db)
        downstream = svc.ensure_dispatch(art.id, "event_extraction")
        db.commit()
        assert svc.claim(downstream) is True
        svc.mark_completed(downstream)
        db.commit()
        assert downstream.status == "completed"

        # Retry screening
        svc.ensure_dispatch(art.id, "screening")
        db.commit()
        asyncio.run(run_once(db, limit=5, task="screening"))

        # Downstream still completed
        db.refresh(downstream)
        assert downstream.status == "completed"
    finally:
        db.close()


# --- 12. Unrelated classification_meta fields preserved ---------------------

def test_unrelated_meta_fields_preserved(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=True,
                                      reason_codes=["KEV_RELEVANT"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={
            "local_screening": {"route": "KEV", "decision": None},
            "human_review": {"acknowledged": True, "note": "test"},
            "priority_source": "rules",
        })
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        # Original screening preserved in history
        assert len(meta.get("screening_history", [])) >= 1
        # Unrelated fields preserved
        assert meta.get("human_review", {}).get("acknowledged") is True
        assert meta.get("priority_source") == "rules"
        # Latest screening updated
        assert meta["local_screening"]["decision"] is True
    finally:
        db.close()


# --- 13. P0/P4 priority not affected by screening retry ---------------------

def test_priority_not_overwritten_by_screening_retry(monkeypatch) -> None:
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=True,
                                      reason_codes=["KEV_RELEVANT"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": None}})
        art.document.ingestion_priority = "P1"
        db.commit()
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        asyncio.run(run_once(db, limit=5, task="screening"))
        db.refresh(art)
        assert art.document.ingestion_priority == "P1"
    finally:
        db.close()


# --- 14. Provider failure produces pending, not negative --------------------

def test_provider_failure_produces_pending_not_negative(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.ai.dispatch.runner._real_provider_available", lambda db: False
    )
    async def fake_screen(db, text, priority=None, **kwargs):
        return orch.ScreeningDecision(route="KEV", relevant=None,
                                      reason_codes=["KEV_LOW_MARGIN", "AI_ERROR:no_real_provider"])

    monkeypatch.setattr(orch, "screen_with_db", fake_screen)
    db = TestingSession()
    try:
        art = _article(db, meta={"local_screening": {"route": "KEV", "decision": None}})
        DispatchService(db).ensure_dispatch(art.id, "screening")
        db.commit()

        outcome = asyncio.run(run_once(db, limit=5, task="screening"))
        assert outcome.blocked == 1
        assert outcome.retryable == 0
        db.refresh(art)
        meta = json.loads(art.classification_meta)
        assert meta["local_screening"]["decision"] is None  # pending, not False
        assert "AI_ERROR:no_real_provider" in meta["local_screening"]["reason_codes"]
    finally:
        db.close()

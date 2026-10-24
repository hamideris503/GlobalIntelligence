"""Stage88 screening orchestration policy tests (offline, fully mocked)."""
from __future__ import annotations

import asyncio
import functools
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.ai.local_screening.orchestrator import (
    LAYA_MAX_STATE,
    ScreeningDecision,
    screen_item,
)


def async_test(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        return asyncio.run(fn(*a, **kw))
    return wrapper


def _settings(kev: bool = False, laya: bool = False) -> SimpleNamespace:
    # AppSetting values arrive as strings; the policy must parse them.
    return SimpleNamespace(
        kev_local_screening_enabled="true" if kev else "false",
        laya_local_screening_enabled="true" if laya else "false",
    )


class _State:
    def __init__(self, value: str) -> None:
        self.value = value


def _sup(state: str = "READY", ensure_state: str = "READY") -> MagicMock:
    sup = MagicMock()
    sup.ensure_loaded.return_value = SimpleNamespace(state=_State(ensure_state))
    sup.status.return_value = SimpleNamespace(state=_State(state))
    return sup


def _kev(relevant: bool, p: float = 0.9, **extra) -> dict:
    return {"status": "ok", "relevant": relevant, "p_true": p, **extra}


def _laya(relevant: bool, p: float = 0.9, **extra) -> dict:
    return {"status": "ok", "relevant": relevant, "p_true": p,
            "state_tokens": 20, "truncated": False, **extra}


def _ai(relevant: bool | None, calls: list | None = None):
    def call(text: str) -> dict:
        if calls is not None:
            calls.append(text)
        return {"relevant": relevant}
    return call


# 1. both disabled -> AI Gateway
@async_test
async def test_both_disabled_uses_ai_gateway() -> None:
    calls: list = []
    d = await screen_item("text", "P3", settings=_settings(), supervisor=_sup(),
                          ai_screen=_ai(True, calls))
    assert d.route == "AI_GATEWAY"
    assert d.relevant is True
    assert d.downstream_dispatch is True
    assert len(calls) == 1


# 2. Kev only, relevant -> dispatch
@async_test
async def test_kev_only_relevant_dispatches() -> None:
    d = await screen_item("text", "P3", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: _kev(True))
    assert d.route == "KEV"
    assert d.relevant is True
    assert d.downstream_dispatch is True
    assert d.kev is not None


# 3. Kev only, high-margin negative P2-P4 -> retain, suppress dispatch
@async_test
async def test_kev_only_high_margin_negative_suppresses() -> None:
    d = await screen_item("text", "P3", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: _kev(False, 0.05))
    assert d.relevant is False
    assert d.downstream_dispatch is False
    assert "KEV_NOT_RELEVANT" in d.reason_codes


# 4. Laya only, relevant -> dispatch
@async_test
async def test_laya_only_relevant_dispatches() -> None:
    d = await screen_item("text", "P3", settings=_settings(laya=True), supervisor=_sup(),
                          laya_caller=lambda t: _laya(True))
    assert d.route == "LAYA"
    assert d.relevant is True
    assert d.downstream_dispatch is True


# 5. Laya truncation -> rejected, AI fallback
@async_test
async def test_laya_truncated_output_rejected() -> None:
    calls: list = []
    d = await screen_item("text", "P3", settings=_settings(laya=True), supervisor=_sup(),
                          laya_caller=lambda t: {"status": "truncated", "truncated": True},
                          ai_screen=_ai(True, calls))
    assert d.route == "LAYA"
    assert d.fallback_used is True
    assert any("TRUNCATED" in r for r in d.reason_codes)
    assert len(calls) == 1


# 6. Kev input beyond 7552 tokens -> AI fallback, local caller never runs
@async_test
async def test_kev_input_too_long_falls_back() -> None:
    calls: list = []
    ran: list = []
    long_text = "word " * 7000  # ~9333 estimated tokens
    d = await screen_item(long_text, "P3", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: ran.append(1) or _kev(True),
                          ai_screen=_ai(True, calls))
    assert "KEV_INPUT_TOO_LONG" in d.reason_codes
    assert d.fallback_used is True
    assert ran == []
    assert len(calls) == 1


# 6b. Laya input beyond 1024 tokens -> AI fallback
@async_test
async def test_laya_input_too_long_falls_back() -> None:
    ran: list = []
    long_text = "word " * 1000  # ~1333 estimated tokens
    d = await screen_item(long_text, "P3", settings=_settings(laya=True), supervisor=_sup(),
                          laya_caller=lambda t: ran.append(1) or _laya(True),
                          ai_screen=_ai(True))
    assert "LAYA_INPUT_TOO_LONG" in d.reason_codes
    assert ran == []
    assert d.fallback_used is True
    assert LAYA_MAX_STATE == 1024


# 7. Unsupported language -> no local decision accepted
@async_test
async def test_unsupported_language_falls_back() -> None:
    ran: list = []
    d = await screen_item("این یک خبر درباره سیاست پولی است", "P3",
                          settings=_settings(kev=True, laya=True), supervisor=_sup(),
                          kev_caller=lambda t: ran.append("k") or _kev(True),
                          laya_caller=lambda t: ran.append("l") or _laya(True),
                          ai_screen=_ai(True))
    assert "UNSUPPORTED_LANGUAGE" in d.reason_codes
    assert ran == []
    assert d.fallback_used is True


# 8. Both enabled, agreement relevant -> dispatch once
@async_test
async def test_both_agree_relevant_dispatches_once() -> None:
    calls: list = []
    d = await screen_item("text", "P3", settings=_settings(kev=True, laya=True),
                          supervisor=_sup(),
                          kev_caller=lambda t: _kev(True, 0.9),
                          laya_caller=lambda t: _laya(True, 0.85),
                          ai_screen=_ai(True, calls))
    assert d.route == "KEV_LAYA"
    assert d.relevant is True
    assert d.downstream_dispatch is True
    assert calls == []  # no AI call when the pair is valid


# 9. Both enabled, agreement not relevant, P2-P4 -> suppress
@async_test
async def test_both_agree_not_relevant_suppresses() -> None:
    d = await screen_item("text", "P2", settings=_settings(kev=True, laya=True),
                          supervisor=_sup(),
                          kev_caller=lambda t: _kev(False, 0.05),
                          laya_caller=lambda t: _laya(False, 0.1))
    assert d.relevant is False
    assert d.downstream_dispatch is False
    assert "BOTH_NOT_RELEVANT" in d.reason_codes


# 10. Disagreement -> AI Gateway fallback
@async_test
async def test_disagreement_falls_back() -> None:
    calls: list = []
    d = await screen_item("text", "P3", settings=_settings(kev=True, laya=True),
                          supervisor=_sup(),
                          kev_caller=lambda t: _kev(True, 0.9),
                          laya_caller=lambda t: _laya(False, 0.1),
                          ai_screen=_ai(True, calls))
    assert "DISAGREEMENT" in d.reason_codes
    assert d.fallback_used is True
    assert len(calls) == 1


# 11. Either model low-margin -> fallback
@async_test
async def test_low_margin_falls_back() -> None:
    calls: list = []
    d = await screen_item("text", "P3", settings=_settings(kev=True, laya=True),
                          supervisor=_sup(),
                          kev_caller=lambda t: _kev(True, 0.55),
                          laya_caller=lambda t: _laya(True, 0.9),
                          ai_screen=_ai(True, calls))
    assert "LOW_MARGIN" in d.reason_codes
    assert d.fallback_used is True
    assert len(calls) == 1


# 12. One model fails -> fallback, no fabricated pair
@async_test
async def test_one_model_fails_falls_back() -> None:
    d = await screen_item("text", "P3", settings=_settings(kev=True, laya=True),
                          supervisor=_sup(),
                          kev_caller=lambda t: _kev(True),
                          laya_caller=lambda t: {"status": "unavailable"},
                          ai_screen=_ai(True))
    assert any(r.startswith("PAIR_INVALID:LAYA_") for r in d.reason_codes)
    assert d.fallback_used is True
    assert d.relevant is True


# 13. Both fail + no AI -> durable pending, never silent discard
@async_test
async def test_both_fail_no_ai_pending() -> None:
    d = await screen_item("text", "P3", settings=_settings(kev=True, laya=True),
                          supervisor=_sup(), ai_screen=None,
                          kev_caller=lambda t: {"status": "error"},
                          laya_caller=lambda t: {"status": "error"})
    assert d.relevant is None
    assert d.downstream_dispatch is False
    assert "AI_UNAVAILABLE" in d.reason_codes


# 14. P0/P1 negative -> safeguard via fallback
@async_test
async def test_p0_negative_safeguard() -> None:
    calls: list = []
    d = await screen_item("text", "P0", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: _kev(False, 0.05),
                          ai_screen=_ai(True, calls))
    assert d.p0_p1_safeguard is True
    assert d.fallback_used is True
    assert d.relevant is True
    assert d.downstream_dispatch is True
    assert len(calls) == 1


# 14b. P0 negative and fallback also negative -> review, no dispatch, retained
@async_test
async def test_p0_negative_review_state() -> None:
    d = await screen_item("text", "P1", settings=_settings(laya=True), supervisor=_sup(),
                          laya_caller=lambda t: _laya(False, 0.05),
                          ai_screen=_ai(False))
    assert d.p0_p1_safeguard is True
    assert d.relevant is False
    assert d.downstream_dispatch is False
    assert "PRIORITY_REVIEW" in d.reason_codes


# 15. AI fallback unavailable -> pending/error, item preserved
@async_test
async def test_ai_unavailable_keeps_pending() -> None:
    def boom(text: str) -> dict:
        raise RuntimeError("gateway down")

    d = await screen_item("text", "P3", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: _kev(True, 0.55), ai_screen=boom)
    assert d.relevant is None
    assert d.downstream_dispatch is False
    assert any(r.startswith("AI_ERROR:") for r in d.reason_codes)


# 16. Model disabled -> local caller never invoked
@async_test
async def test_disabled_model_never_invoked() -> None:
    ran: list = []
    d = await screen_item("text", "P3", settings=_settings(kev=False, laya=True),
                          supervisor=_sup(),
                          kev_caller=lambda t: ran.append("k") or _kev(True),
                          laya_caller=lambda t: _laya(True))
    assert ran == []
    assert d.route == "LAYA"


# 17. Lifecycle: busy/idle wrapped, idle always called even on caller error
@async_test
async def test_lifecycle_busy_idle_on_error() -> None:
    sup = _sup()

    def fail(text: str) -> dict:
        raise RuntimeError("boom")

    d = await screen_item("text", "P3", settings=_settings(kev=True), supervisor=sup,
                          kev_caller=fail, ai_screen=_ai(True))
    sup.mark_busy.assert_called_once_with("kev")
    sup.mark_idle.assert_called_once_with("kev")
    assert d.fallback_used is True


# 17b. Not ready -> no busy/idle, fallback
@async_test
async def test_not_ready_skips_busy() -> None:
    sup = _sup(ensure_state="ERROR")
    d = await screen_item("text", "P3", settings=_settings(kev=True), supervisor=sup,
                          kev_caller=lambda t: _kev(True), ai_screen=_ai(True))
    sup.mark_busy.assert_not_called()
    assert "KEV_UNAVAILABLE" in d.reason_codes


# 20. Fallback does not re-enter local screening: called exactly once, and
#     routing after fallback does not invoke the local caller again.
@async_test
async def test_fallback_single_shot_no_recursion() -> None:
    kev_calls: list = []
    ai_calls: list = []
    await screen_item("text", "P3", settings=_settings(kev=True), supervisor=_sup(),
                      kev_caller=lambda t: kev_calls.append(1) or _kev(True, 0.55),
                      ai_screen=_ai(True, ai_calls))
    assert len(kev_calls) == 1
    assert len(ai_calls) == 1


# 23. Priority is never overwritten by relevance
@async_test
async def test_priority_is_not_overwritten() -> None:
    d = await screen_item("text", "P0", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: _kev(True), ai_screen=_ai(True))
    assert d.provenance["priority"] == "P0"
    assert not hasattr(d, "priority")
    assert d.as_dict()["scope_rule_version"] == "relevance_scope_v2"


# 29. Provenance preserved in the serialised outcome
@async_test
async def test_provenance_serialised() -> None:
    d = await screen_item("text", "P2", settings=_settings(kev=True), supervisor=_sup(),
                          kev_caller=lambda t: _kev(True))
    payload = d.as_dict()
    assert payload["route"] == "KEV"
    assert payload["kev"]["p_true"] == 0.9
    assert payload["provenance"]["settings"]["kev_enabled"] is True
    assert payload["decision"] is True


def test_screening_decision_is_not_human_truth() -> None:
    d = ScreeningDecision(route="KEV", relevant=True)
    payload = d.as_dict()
    assert "confidence" not in payload or payload.get("confidence") is not None
    assert payload["decision"] is True


# --- Stage89: AI Gateway screening prompt/parser (offline) ------------------

def _fake_gateway(text: str, *, is_mock: bool = True):
    from backend.ai.schemas.types import AIResponse

    class _G:
        async def generate(self, request):  # noqa: ANN001, ANN202
            return AIResponse(text=text, provider="mock", model="m", is_mock=is_mock)

    return _G()


async def _ai_screen(monkeypatch, text: str):
    import backend.ai.gateway as gateway_module
    from backend.ai.local_screening.orchestrator import make_ai_gateway_screen

    monkeypatch.setattr(gateway_module, "get_gateway",
                        lambda: _fake_gateway(text))
    return await make_ai_gateway_screen()(text)


@async_test
async def test_ai_parser_accepts_single_yes_no(monkeypatch) -> None:
    assert (await _ai_screen(monkeypatch, "YES"))["relevant"] is True
    assert (await _ai_screen(monkeypatch, "No."))["relevant"] is False


@async_test
async def test_ai_parser_rejects_malformed_and_contradictory(monkeypatch) -> None:
    for text in ("", "maybe", "YES and NO", "the answer is YES"):
        out = await _ai_screen(monkeypatch, text)
        assert out["relevant"] is None, text


@async_test
async def test_mock_fallback_provenance_is_marked() -> None:
    d = await screen_item(
        "text", "P2", settings=_settings(kev=False, laya=False), supervisor=_sup(),
        ai_screen=lambda t: {"relevant": True, "is_mock": True},
    )
    assert d.relevant is True
    assert d.provenance["fallback_is_mock"] is True

"""Daily token budget + ledger — deterministic, no network, no real provider.

Concurrency note: tests run on SQLite (single connection serializes
writers). The thread test below proves the accounting invariant
(sum never exceeds budget, no double rows), not PG-grade proof of the
race window; the single-statement conditional INSERT is what closes it
on PostgreSQL.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.ai import budget
from backend.ai.schemas.types import AIError, AIErrorKind, AIRequest, Message
from backend.database.models.ai_token_ledger import AITokenLedger
from tests.conftest import TestingSession


@pytest.fixture
def wired():
    import os

    os.environ["AI_DAILY_TOKEN_BUDGET"] = "1000000"
    from backend.core.config import get_settings

    get_settings.cache_clear()
    budget.set_session_factory(TestingSession)
    try:
        yield
    finally:
        budget.reset_session_factory()
        get_settings.cache_clear()


def _req(text="hello world triage probe", max_tokens=None):
    return AIRequest(messages=[Message.user(text)], task="triage_probe",
                     role="fast_extraction", max_tokens=max_tokens)


def _rows():
    db = TestingSession()
    try:
        return db.execute(select(AITokenLedger)).scalars().all()
    finally:
        db.close()


def test_disabled_by_default_no_ledger():
    assert budget.is_enabled() is False
    assert budget.budget_limit() is None


def test_estimate_formula():
    # capped by request, then by task map, else None (never a fixed 8000)
    assert budget.resolve_output_cap(_req("x", max_tokens=100)) == 100
    assert budget.resolve_output_cap(_req("x")) is None
    assert budget.estimate_input_tokens(_req("x" * 400)) == int(400 // 4 * 2.1)


def test_resolve_output_cap_priority_and_task_map(monkeypatch):
    import json

    from backend.core.config import get_settings

    monkeypatch.setenv("AI_TASK_MAX_TOKENS", json.dumps({"triage_probe": 700}))
    get_settings.cache_clear()
    assert budget.resolve_output_cap(_req("x", max_tokens=100)) == 100
    assert budget.resolve_output_cap(_req("x")) == 700
    monkeypatch.setenv("AI_TASK_MAX_TOKENS", '{"triage_probe": -5}')
    get_settings.cache_clear()
    assert budget.resolve_output_cap(_req("x")) is None
    # مقدار نامعتبر نقشه: fail-fast در بارگذاری تنظیمات (نه سکوت)
    import pydantic

    monkeypatch.setenv("AI_TASK_MAX_TOKENS", '{"triage_probe": "big"}')
    get_settings.cache_clear()
    with pytest.raises(pydantic.ValidationError):
        get_settings()


def test_estimate_input_covers_languages_and_schema():
    fa = budget.estimate_input_tokens(_req("نرخ ارز و طلا بالا رفت " * 20))
    en = budget.estimate_input_tokens(_req("gold price update " * 20))
    assert fa > 0 and en > 0
    r = _req("hi")
    r.json_schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert budget.estimate_input_tokens(r) > budget.estimate_input_tokens(_req("hi"))


def test_reserve_allowed_and_recorded(wired):
    day = budget.utc_day()
    assert budget.reserve(db=TestingSession(), day=day, task="t", provider="p",
                          model="m", request_key="k-1", estimate=50,
                          budget=1000000) is True
    rows = _rows()
    assert len(rows) == 1 and rows[0].status == "reserved"
    assert rows[0].reserved_tokens == 50


def test_reserve_denied_when_full(wired):
    import os

    from backend.core.config import get_settings

    os.environ["AI_DAILY_TOKEN_BUDGET"] = "10"
    get_settings.cache_clear()
    day = budget.utc_day()
    assert budget.reserve(db=TestingSession(), day=day, task="t", provider="p",
                          model="m", request_key="k-2", estimate=500,
                          budget=10) is False
    assert _rows() == []


def test_double_submit_single_row(wired):
    day = budget.utc_day()
    kw = dict(db=TestingSession(), day=day, task="t", provider="p",
              model="m", request_key="k-3", estimate=10, budget=1000000)
    assert budget.reserve(**kw) is True
    assert budget.reserve(**kw) is True
    assert len(_rows()) == 1


def test_settle_uses_actual_and_failed_keeps_reserved(wired):
    day = budget.utc_day()
    db = TestingSession()
    try:
        assert budget.reserve(db=db, day=day, task="t", provider="p", model="m",
                              request_key="k-4", estimate=100, budget=1000000)
        assert budget.reserve(db=db, day=day, task="t", provider="p", model="m",
                              request_key="k-5", estimate=100, budget=1000000)
        budget.settle("k-4", actual=30, status="settled", db=db)
        budget.settle("k-5", actual=None, status="failed", db=db)
        assert budget.spent_today(db, day) == 130
        rep = budget.get_daily_usage(db, day)
        assert rep["by_task"]["t"]["attempts"] == 2
    finally:
        db.close()


def test_day_boundary_isolated(wired):
    yesterday = budget.utc_day() - timedelta(days=1)
    db = TestingSession()
    try:
        assert budget.reserve(db=db, day=yesterday, task="t", provider="p",
                              model="m", request_key="k-6", estimate=700,
                              budget=1000000)
        assert budget.spent_today(db, budget.utc_day()) == 0
    finally:
        db.close()


def test_release_frees_reservation(wired):
    day = budget.utc_day()
    db = TestingSession()
    try:
        assert budget.reserve(db=db, day=day, task="t", provider="p", model="m",
                              request_key="k-7", estimate=400, budget=1000000)
        budget.release("k-7", db=db)
        assert budget.spent_today(db, day) == 0
    finally:
        db.close()


def test_concurrent_reserves_consistent_no_duplicates(tmp_path):
    """sqlite چنداتصالی: بدون کرش، بدون ردیف تکراری، سازگاری ledger با نتایج.

    سقف دقیق هم‌زمانی فقط روی PostgreSQL (advisory lock) تضمین می‌شود؛
    اینجا invariantهای مستقل از race بررسی می‌شوند (تست PG جدا).
    """
    import threading

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.base import Base

    eng = create_engine(f"sqlite:///{tmp_path}/c.db")
    Base.metadata.create_all(bind=eng)
    maker = sessionmaker(bind=eng)
    day = budget.utc_day()
    results = []
    errors = []

    def worker(i):
        db = maker()
        try:
            ok = budget.reserve(db=db, day=day, task="t", provider="p",
                                model="m", request_key=f"kx-{i}",
                                estimate=200, budget=1000000)
            results.append(ok)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc)[:120])
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(results) == 8
    db = maker()
    try:
        rows = db.execute(select(AITokenLedger)).scalars().all()
        assert len(rows) == sum(results)
        assert len({r.request_key for r in rows}) == len(rows)
        assert budget.spent_today(db, day) == sum(
            r.reserved_tokens for r in rows)
    finally:
        db.close()


class _StubProvider:
    name = "stub-test"
    default_model = "stub-1"

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def generate(self, request):
        from backend.ai.schemas.types import AIResponse

        self.calls += 1
        action = self.script[min(self.calls - 1, len(self.script) - 1)]
        if action == "raise-retryable":
            raise AIError("busy", kind=AIErrorKind.rate_limit, retryable=True)
        if action == "raise-fatal":
            raise AIError("bad", kind=AIErrorKind.bad_request, retryable=False)
        return AIResponse(text='{"ok": true}', provider=self.name, model="stub-1")


def test_gateway_denies_without_calling_provider(wired):
    import os

    from backend.ai.gateway import AIGateway
    from backend.core.config import get_settings

    os.environ["AI_DAILY_TOKEN_BUDGET"] = "1"
    get_settings.cache_clear()
    gw = AIGateway()
    p = _StubProvider(["ok"])
    with pytest.raises(AIError) as exc:
        asyncio.run(gw._call_with_retry(p, _req("x" * 5000, max_tokens=500),
                                        budget_key="r-deny"))
    assert exc.value.kind == AIErrorKind.budget
    assert p.calls == 0
    assert _rows() == []


def test_gateway_estimate_unavailable_without_cap(wired):
    from backend.ai.gateway import AIGateway

    gw = AIGateway()
    p = _StubProvider(["ok"])
    with pytest.raises(AIError) as exc:
        asyncio.run(gw._call_with_retry(p, _req("hi"), budget_key="r-nocap"))
    assert exc.value.kind == AIErrorKind.estimate
    assert "estimate unavailable" in str(exc.value)
    assert p.calls == 0
    assert _rows() == []


def test_reserve_records_estimate_split(wired):
    day = budget.utc_day()
    db = TestingSession()
    try:
        assert budget.reserve(db=db, day=day, task="t", provider="p", model="m",
                              request_key="k-split", estimate=900,
                              input_est=300, output_cap=600,
                              budget=1000000) is True
        row = db.execute(select(AITokenLedger).where(
            AITokenLedger.request_key == "k-split")).scalars().one()
        assert row.reserved_tokens == 900
        assert row.estimated_input_tokens == 300
        assert row.output_cap_tokens == 600
    finally:
        db.close()


def test_gateway_retry_attempts_recorded_separately(wired):
    from backend.ai.gateway import AIGateway

    gw = AIGateway()
    gw._max_retries = 1
    p = _StubProvider(["raise-retryable", "ok"])
    resp = asyncio.run(gw._call_with_retry(p, _req("hi", max_tokens=500),
                                               budget_key="r-retry"))
    assert resp.text == '{"ok": true}' and p.calls == 2
    keys = sorted(r.request_key for r in _rows())
    assert keys == ["r-retry:stub-test:0", "r-retry:stub-test:1"]


def test_gateway_fatal_error_settles_failed(wired):
    from backend.ai.gateway import AIGateway

    gw = AIGateway()
    p = _StubProvider(["raise-fatal"])
    with pytest.raises(AIError):
        asyncio.run(gw._call_with_retry(p, _req("hi", max_tokens=500),
                                        budget_key="r-fatal"))
    rows = _rows()
    assert len(rows) == 1 and rows[0].status == "failed"


def test_gateway_unconfigured_keeps_old_behavior():
    from backend.ai.gateway import AIGateway

    gw = AIGateway()
    p = _StubProvider(["ok"])
    resp = asyncio.run(gw._call_with_retry(p, _req("hi")))
    assert resp.text == '{"ok": true}' and p.calls == 1
    assert _rows() == []


def _req_task(task, **kw):
    req = _req("probe", **kw)
    req.task = task
    return req


def test_exact_match_beats_shared_debate_cap(monkeypatch):
    import json

    from backend.core.config import get_settings

    monkeypatch.setenv("AI_TASK_MAX_TOKENS", json.dumps(
        {"debate_report": 111, "debate_agent": 222}))
    get_settings.cache_clear()
    assert budget.resolve_output_cap(_req_task("debate_report")) == 111
    assert budget.resolve_output_cap(_req_task("debate_bull")) == 222


def test_dynamic_debate_agents_share_cap(monkeypatch):
    import json

    from backend.core.config import get_settings

    monkeypatch.setenv("AI_TASK_MAX_TOKENS", json.dumps({"debate_agent": 1500}))
    get_settings.cache_clear()
    for agent in ("bull", "bear", "macro", "geopolitical", "risk_critic",
                  "quant_anchor"):
        assert budget.resolve_output_cap(_req_task(f"debate_{agent}")) == 1500
    # unknown debate-like name is NOT covered by the shared cap
    assert budget.resolve_output_cap(_req_task("debate_fiction")) is None


def test_graphrag_has_no_cap_until_validated(monkeypatch):
    import json

    from backend.core.config import get_settings

    monkeypatch.setenv("AI_TASK_MAX_TOKENS", json.dumps({"debate_agent": 1500}))
    get_settings.cache_clear()
    assert budget.resolve_output_cap(_req_task("graphrag_synthesize")) is None


def test_unknown_task_fails_closed_under_budget(wired):
    from backend.ai.gateway import AIGateway

    gw = AIGateway()
    p = _StubProvider(["ok"])
    with pytest.raises(AIError) as exc:
        asyncio.run(gw._call_with_retry(p, _req_task("no_such_task_xyz"),
                                        budget_key="r-unknown"))
    assert exc.value.kind == AIErrorKind.estimate
    assert p.calls == 0


def test_sample_profile_json_parses_with_expected_keys():
    import json

    sample = {"classify_article": 1500, "extract_claims": 1000,
              "extract_event": 800, "extract_evidence": 1000,
              "extract_relations": 800, "debate_agent": 1500,
              "debate_report": 1500}
    parsed = json.loads(json.dumps(sample))
    assert parsed["debate_report"] == 1500
    assert set(parsed) == {"classify_article", "extract_claims", "extract_event",
                           "extract_evidence", "extract_relations",
                           "debate_agent", "debate_report"}


def test_truncated_output_fails_validation_not_success():
    import json as _json

    from domains.news.classifier import _safe_json, _validate
    from domains.news.classifier_schema import CLASSIFY_SCHEMA

    full = _json.dumps({"topics": ["energy"], "country": "US",
                        "entities": [{"name": "OPEC", "type": "organization"}],
                        "sentiment": 0.2, "stance": "neutral",
                        "summary": "Oil rose.",
                        "importance": {"impact": 0.8, "scope": 0.5},
                        "confidence": 0.8})
    # cut before the final brace: unparseable at all
    assert _safe_json(full[:full.rfind("}")]) is None
    # cut that still parses but lost required keys: validation rejects
    partial = {"topics": ["energy"]}
    assert _safe_json(_json.dumps(partial)) == partial
    with pytest.raises(ValueError):
        _validate(partial, CLASSIFY_SCHEMA)

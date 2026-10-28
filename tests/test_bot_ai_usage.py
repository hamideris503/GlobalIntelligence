"""مصرف واقعی AI در Source Bot: از پاسخ provider تا گزارش روزانهٔ هر منبع.

همهٔ تست‌ها آفلاین‌اند: یا Gateway ساختگی، یا provider mock محلی.
هیچ provider/شبکه‌ای صدا زده نمی‌شود و هیچ عددی از ai_used/ai_fallback استنتاج نمی‌شود.
"""
from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, datetime

from backend.ai.schemas.types import AIResponse, AIUsage
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot import runner as runner_module
from source_bot.ai_priority_fallback import ai_prioritize, usage_meta
from source_bot.config import BotSettings
from source_bot.metrics import BotMetrics, SourceMetrics
from source_bot.report import build_daily_report
from tests.conftest import TestingSession

_NEEDS_AI = {"title": "breaking but disputed contradict claims", "raw_text": "text " * 50}


def _src(session, name: str) -> Source:
    s = Source(name=name, collection_method="rss", type="rss", feed_url=f"https://{name}.test/rss")
    session.add(s)
    session.commit()
    return s


def _ai_result(*, prompt=120, completion=30, total=150, provider="prov-real", cost=None,
               is_mock=False) -> dict:
    return {
        "priority": "P2", "confidence": 0.8, "reason": "r", "reason_codes": ["X"],
        "is_mock": is_mock,
        "usage": {"provider": provider, "model": "m", "prompt_tokens": prompt,
                  "completion_tokens": completion, "total_tokens": total,
                  "cost_estimate": cost},
    }


def _run_source(monkeypatch, session, src: Source, item: RawItem, *, ai_enabled=True) -> BotMetrics:
    async def fake_fetch(plan, settings):
        return ([item], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    settings = BotSettings()
    settings.max_retries = 0
    settings.ai_enabled = ai_enabled
    metrics = BotMetrics()
    asyncio.run(runner_module.run_source(session, src, metrics, settings))
    return metrics


# --- ۱) usage واقعی پاسخ، بدون تغییر/ساخت مقدار ---

def test_usage_meta_copies_only_reported_values() -> None:
    resp = AIResponse(text="{}", provider="gemini", model="gemini-x",
                      usage=AIUsage(prompt_tokens=120, completion_tokens=30, total_tokens=150))
    assert usage_meta(resp) == {"provider": "gemini", "model": "gemini-x",
                                "prompt_tokens": 120, "completion_tokens": 30,
                                "total_tokens": 150, "cost_estimate": None}

    empty = usage_meta(AIResponse(text="{}", provider="t", model="m"))
    assert empty["prompt_tokens"] is None and empty["total_tokens"] is None
    assert empty["cost_estimate"] is None


def test_ai_prioritize_exposes_provider_usage(monkeypatch) -> None:
    class Gw:
        async def generate(self, req):
            return AIResponse(text=json.dumps({"priority": "P3", "confidence": 0.7,
                                               "reason": "ok", "reason_codes": ["C"]}),
                              provider="groq", model="llama",
                              usage=AIUsage(40, 10, 50))

    monkeypatch.setattr("backend.ai.gateway.get_gateway", lambda: Gw())

    async def go():
        return await ai_prioritize(title="t", text="body")

    result = asyncio.run(go())
    assert result is not None
    assert (result["priority"], result["is_mock"]) == ("P3", False)
    assert result["usage"] == {"provider": "groq", "model": "llama", "prompt_tokens": 40,
                               "completion_tokens": 10, "total_tokens": 50,
                               "cost_estimate": None}


# --- ۲+۵+۶) شمارنده‌ها: سازگاری مجموع، نبود usage ≠ صفر، هزینه فقط با نرخ واقعی ---

def test_record_ai_counts_are_consistent() -> None:
    sm = SourceMetrics()
    sm.record_ai(_ai_result())                          # کامل
    sm.record_ai(_ai_result(total=None))               # total غایب → in+out
    sm.record_ai(None)                                 # خطا/timeout
    sm.record_ai(_ai_result(prompt=None, completion=None, total=None))  # usage ناقص
    sm.record_ai(_ai_result(is_mock=True))             # mock

    assert sm.ai_calls == 5
    assert sm.ai_calls == sm.ai_ok + sm.ai_failed + sm.ai_mock
    assert (sm.ai_ok, sm.ai_failed, sm.ai_mock) == (3, 1, 1)
    assert (sm.ai_usage_events, sm.ai_usage_missing) == (2, 1)
    assert (sm.ai_tokens_in, sm.ai_tokens_out, sm.ai_tokens_total) == (240, 60, 300)
    assert sm.ai_tokens_total == sm.ai_tokens_in + sm.ai_tokens_out
    assert sm.ai_providers == {"prov-real": 3}
    assert sm.ai_cost_usd is None and sm.ai_cost_events == 0  # mock با cost=0 شمرده نشد


def test_cost_requires_reported_value_by_provider() -> None:
    sm = SourceMetrics()
    sm.record_ai(_ai_result(cost=0.0021))
    sm.record_ai(_ai_result(cost=0.0009))
    assert sm.ai_cost_events == 2
    assert sm.ai_cost_usd == 0.003


# --- ۳+۸) attribution واقعی به منبع، بدون تغییر معنای ai_used/ai_fallback ---

def test_tokens_are_attributed_to_the_right_source(monkeypatch) -> None:
    per_source = {"src-a": (100, 20), "src-b": (7, 3)}

    async def fake_ai(*, title, text, metadata=None):
        tokens = per_source[(metadata or {}).get("source")]
        return _ai_result(prompt=tokens[0], completion=tokens[1], total=sum(tokens))

    monkeypatch.setattr(runner_module, "ai_prioritize", fake_ai)
    session = TestingSession()
    try:
        a, b = _src(session, "src-a"), _src(session, "src-b")
        metrics = BotMetrics()
        settings = BotSettings()
        settings.max_retries = 0
        settings.ai_enabled = True

        async def fake_fetch(plan, settings):
            return ([RawItem(url=f"https://{plan.url.split('//')[1]}/1", **_NEEDS_AI)], "", {})

        monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
        asyncio.run(runner_module.run_source(session, a, metrics, settings))
        asyncio.run(runner_module.run_source(session, b, metrics, settings))

        ai_a, ai_b = metrics.by_source["src-a"], metrics.by_source["src-b"]
        assert (ai_a.ai_tokens_in, ai_a.ai_tokens_out, ai_a.ai_tokens_total) == (100, 20, 120)
        assert (ai_b.ai_tokens_in, ai_b.ai_tokens_out, ai_b.ai_tokens_total) == (7, 3, 10)
        assert ai_a.ai_providers == ai_b.ai_providers == {"prov-real": 1}
        # معنای قبلی شمارنده‌ها دست‌نخورده: پذیرش تصمیم AI
        assert (ai_a.ai_used, ai_a.ai_fallback) == (1, 0)
        assert (ai_b.ai_used, ai_b.ai_fallback) == (1, 0)
        assert session.query(Document).count() == 2
    finally:
        session.close()


def test_failure_and_mock_are_not_counted_as_usage(monkeypatch) -> None:
    session = TestingSession()
    try:
        s = _src(session, "src-fail")
        monkeypatch.setattr(runner_module, "ai_prioritize",
                            lambda **kw: asyncio.sleep(0, result=None))
        metrics = _run_source(monkeypatch, session, s, RawItem(url="https://f.test/1", **_NEEDS_AI))
        sm = metrics.by_source["src-fail"]
        assert (sm.ai_calls, sm.ai_failed, sm.ai_ok) == (1, 1, 0)
        assert (sm.ai_tokens_in, sm.ai_tokens_total) == (0, 0)
        assert (sm.ai_usage_events, sm.ai_usage_missing) == (0, 0)
        assert (metrics.ai_fallback, metrics.ai_used) == (1, 0)  # معنای قبلی حفظ شده
        assert session.query(Document).count() == 1

        async def fake_mock(**kw):
            return _ai_result(prompt=999, completion=999, total=1998, provider="mock",
                              cost=0.0, is_mock=True)

        monkeypatch.setattr(runner_module, "ai_prioritize", fake_mock)
        session.query(Document).delete()
        session.commit()
        metrics = _run_source(monkeypatch, session, s, RawItem(url="https://m.test/1", **_NEEDS_AI))
        sm = metrics.by_source["src-fail"]
        assert (sm.ai_calls, sm.ai_mock, sm.ai_ok) == (1, 1, 0)
        assert (sm.ai_tokens_total, sm.ai_usage_events, sm.ai_cost_usd) == (0, 0, None)
        assert (metrics.ai_fallback, metrics.ai_used) == (1, 0)
    finally:
        session.close()


def test_real_gateway_in_mock_mode_never_counts_synthetic_tokens() -> None:
    """MOCK_MODE روشن است → provider محلی mock؛ usage تخمینی نباید مصرف واقعی شود."""

    async def go():
        return await ai_prioritize(title="t", text="some text")

    result = asyncio.run(go())
    assert result is not None and result["is_mock"] is True
    assert result["usage"]["provider"] == "mock"
    sm = SourceMetrics()
    sm.record_ai(result)
    assert (sm.ai_mock, sm.ai_ok) == (1, 0)
    assert sm.ai_tokens_total == 0 and sm.ai_usage_events == 0


# --- گزارش: تفکیک منبع، مجموع، و ناموجود به‌جای صفر ---

def _run_record(*, at: str, by_source: dict, failures: dict | None = None) -> dict:
    return {"at": datetime.fromisoformat(at).replace(tzinfo=UTC),
            "status": "completed", "message": None,
            "result": {"by_source": by_source, "sources_failed": failures or {}}}


def _stats(*, calls=2, ok=2, failed=0, mock=0, events=2, missing=0,
           tokens_in=100, tokens_out=20, total=120, cost=None, cost_events=0) -> dict:
    return {"ok": True, "fetch_attempts": 1, "fetched": 2, "stored": 2,
            "ai_calls": calls, "ai_ok": ok, "ai_failed": failed, "ai_mock": mock,
            "ai_providers": {"gemini": ok} if ok else {},
            "ai_usage_events": events, "ai_usage_missing": missing,
            "ai_tokens_in": tokens_in, "ai_tokens_out": tokens_out,
            "ai_tokens_total": total, "ai_cost_usd": cost, "ai_cost_events": cost_events}


def test_report_exposes_per_source_ai_usage_and_totals() -> None:
    records = [
        _run_record(at="2026-10-18T10:00:00", by_source={
            "src-a": _stats(),
            "src-b": _stats(calls=1, ok=1, events=1, missing=0,
                            tokens_in=7, tokens_out=3, total=10),
        }),
        _run_record(at="2026-10-18T11:00:00", by_source={
            "src-a": _stats(calls=1, ok=1, events=1, tokens_in=5, tokens_out=5, total=10),
        }),
    ]
    report = build_daily_report(records, day="2026-10-18")
    a = next(r for r in report["sources"] if r["name"] == "src-a")["ai"]
    b = next(r for r in report["sources"] if r["name"] == "src-b")["ai"]

    assert a["status"] == "available" and a["runs_instrumented"] == 2 and a["legacy_runs"] == 0
    assert (a["requests"], a["ok"], a["failed"], a["mock"]) == (3, 3, 0, 0)
    assert (a["tokens_in"], a["tokens_out"], a["tokens_total"]) == (105, 25, 130)
    assert a["tokens_total"] == a["tokens_in"] + a["tokens_out"]
    assert a["providers"] == {"gemini": 3}
    assert a["cost_usd"] is None and a["cost_events"] == 0
    assert b["tokens_total"] == 10 and b["requests"] == 1

    totals = report["ai_usage"]
    assert totals["instrumented_sources"] == 2 and totals["status"] == "available"
    assert (totals["requests"], totals["tokens_in"], totals["tokens_out"],
            totals["tokens_total"]) == (4, 112, 28, 140)
    assert totals["cost_usd"] is None
    assert report["history_gap"]["runs_without_ai_usage"] == 0


def test_report_cost_only_from_reported_values() -> None:
    records = [_run_record(at="2026-10-18T10:00:00", by_source={
        "src-a": _stats(cost=0.0042, cost_events=2),
        "src-b": _stats(),
    })]
    report = build_daily_report(records)
    a = next(r for r in report["sources"] if r["name"] == "src-a")["ai"]
    b = next(r for r in report["sources"] if r["name"] == "src-b")["ai"]
    assert a["cost_events"] == 2 and a["cost_usd"] == 0.0042
    assert b["cost_usd"] is None
    assert report["ai_usage"]["cost_usd"] == 0.0042


def test_report_marks_missing_and_legacy_usage_not_zero() -> None:
    partial_stats = _stats(events=1, missing=1, tokens_in=10, tokens_out=5, total=15)
    missing_stats = _stats(calls=3, ok=3, events=0, missing=3,
                           tokens_in=0, tokens_out=0, total=0)
    legacy_stats = {"ok": True, "fetch_attempts": 1, "fetched": 1, "stored": 1}

    report = build_daily_report([
        _run_record(at="2026-10-18T10:00:00", by_source={
            "src-partial": partial_stats, "src-missing": missing_stats,
            "src-legacy": legacy_stats}),
        _run_record(at="2026-10-18T11:00:00", by_source={"src-legacy": legacy_stats}),
    ])
    rows = {r["name"]: r["ai"] for r in report["sources"]}

    assert rows["src-partial"]["status"] == "partial"
    assert rows["src-partial"]["tokens_total"] == 15          # فقط مقادیر گزارش‌شده

    assert rows["src-missing"]["status"] == "missing"
    assert rows["src-missing"]["requests"] == 3               # تماس واقعی ثبت شده
    assert rows["src-missing"]["tokens_in"] is None           # مصرف ناموجود، نه صفر
    assert rows["src-missing"]["tokens_total"] is None

    assert rows["src-legacy"]["status"] == "not_instrumented"
    assert rows["src-legacy"]["runs_instrumented"] == 0
    assert rows["src-legacy"]["legacy_runs"] == 2
    assert rows["src-legacy"]["tokens_total"] is None
    assert report["history_gap"]["runs_without_ai_usage"] == 1  # فقط اجرای بدون هیچ منبع ابزاردار

    # دادهٔ قدیمی همچنان گزارش می‌شود؛ فقط مصرفش ناموجود است
    assert rows["src-legacy"]["requests"] is None


def test_report_status_distinguishes_mock_only_from_missing() -> None:
    instrumented = _stats(calls=2, ok=0, failed=0, mock=2, events=0, missing=0,
                          tokens_in=0, tokens_out=0, total=0)
    report = build_daily_report([
        _run_record(at="2026-10-18T10:00:00", by_source={"src-mock": instrumented})])
    ai = next(r for r in report["sources"] if r["name"] == "src-mock")["ai"]
    assert (ai["status"], ai["mock"], ai["requests"]) == ("mock_only", 2, 2)
    assert ai["tokens_total"] is None and ai["cost_usd"] is None


def test_ai_report_is_idempotent() -> None:
    records = [_run_record(at="2026-10-18T10:00:00", by_source={"src-a": _stats()})]
    before = copy.deepcopy(records)
    first = build_daily_report(records, day="2026-10-18")
    second = build_daily_report(records, day="2026-10-18")
    assert first == second
    assert records == before
    assert first["ai_usage"]["requests"] == 2                 # یک‌بار شمرده شد

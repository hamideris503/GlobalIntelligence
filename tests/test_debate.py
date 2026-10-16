"""Tests for Debate Engine (Step 3) — all deterministic with fake providers.

هیچ تماس واقعی گرفته نمی‌شود. تست live جدا با فلگ صریح است (در CI اجرا نمی‌شود).
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai.schemas.types import AIResponse, AIUsage
from backend.database.models.ai_settings import AIModelRow, AIProviderRow
from backend.database.models.debate import DebateMessage, DebateRun
from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.market import MarketObservation
from domains.debate.agents import AgentResult, clip_probability
from domains.debate.aggregate import aggregate, quant_anchor_probability
from domains.debate.context import build_context_pack
from domains.debate.engine import DebateEngine
from tests.conftest import TestingSession


@pytest.fixture(autouse=True)
def _wire_price_store():
    """store قیمت را به DB تستی وصل می‌کند (Step 8)؛ پس از تست جدا می‌شود."""
    from backend.ai import credentials_store as store

    store.set_session_factory(TestingSession)
    try:
        yield
    finally:
        store.set_session_factory(None)


def _seed_price(session, name="t-gemini", kind="gemini", model="fake-1") -> None:
    """یک Provider + قیمت برای تست‌های engine (گیت price_missing رد شود)."""
    row = AIProviderRow(name=name, kind=kind, enabled=True)
    session.add(row)
    session.flush()
    session.add(AIModelRow(provider_id=row.id, model_name=model,
                           price_in_per_mtok=1.0, price_out_per_mtok=2.0,
                           enabled=True))
    session.commit()


def _agent_json(p: float = 0.7, refs: list | None = None) -> str:
    return json.dumps({
        "direction": "up" if p > 0.5 else "down",
        "probability_up": p,
        "horizon_days": 30,
        "confidence": 0.6,
        "key_evidence": refs if refs is not None else [],
        "assumptions": ["a1"],
        "invalidation_conditions": ["i1"],
        "uncertainties": ["u1"],
    })


# --- agents: schema/clip/anti-hallucination ---
def test_clip_probability() -> None:
    assert clip_probability(0.0) == 0.02
    assert clip_probability(1.0) == 0.98
    assert clip_probability(0.6) == 0.6


def test_agent_rejects_hallucinated_refs() -> None:
    data = json.loads(_agent_json(0.7, [{"ref_id": "E99", "why": "fake"}]))
    with pytest.raises(ValueError):
        AgentResult.from_dict("bull", {"direction": "up"}, {"E1"})
    r = AgentResult.from_dict("bull", data, {"E1"})
    assert r.rejected_refs == ["E99"]
    assert r.quality_score == 0.8
    assert r.key_evidence == []
    assert r.probability_up == 0.7


def test_normalize_string_evidence_then_rejected() -> None:
    """مدل‌های شلخته evidence رشته‌ای می‌دهند؛ نرمال می‌شود ولی چون ref ندارد رد می‌شود."""
    from domains.debate.agents import normalize_output

    data = json.loads(_agent_json(0.6))
    data["key_evidence"] = ["plain text evidence", {"ref_id": "E1", "why": "ok"}]
    data = normalize_output(data)
    r = AgentResult.from_dict("bear", data, {"E1"})
    assert r.key_evidence == [{"ref_id": "E1", "why": "ok"}]
    assert "" in r.rejected_refs
    assert r.quality_score == 0.8


def test_agent_missing_key_raises() -> None:
    with pytest.raises(ValueError):
        AgentResult.from_dict("bear", {"direction": "down"}, set())


# --- aggregate: deterministic ---
def test_aggregate_equal_weights_when_no_history() -> None:
    out = aggregate({"a": 0.7, "b": 0.5})
    assert abs(sum(out.weights.values()) - 1.0) < 1e-9
    assert abs(out.weights["a"] - out.weights["b"]) < 1e-9
    assert 0.5 < out.consensus_probability < 0.7
    assert out.disagreement > 0
    assert out.confidence < 1.0  # جریمه‌ی اختلاف


def test_aggregate_favors_better_brier() -> None:
    briers = {"good": (0.05, 100), "bad": (0.24, 100)}
    out = aggregate({"good": 0.6, "bad": 0.6}, briers=briers)
    assert out.weights["good"] > out.weights["bad"]


def test_aggregate_empty_raises() -> None:
    with pytest.raises(ValueError):
        aggregate({})


def test_quant_anchor() -> None:
    base = {"m1": {"expected_value": 100.0}, "m2": {"expected_value": 102.0}}
    assert quant_anchor_probability(base, 90.0) == 0.55
    assert quant_anchor_probability(base, 110.0) == 0.45
    assert quant_anchor_probability({}, 90.0) == 0.5
    assert quant_anchor_probability(base, None) == 0.5


# --- context: point-in-time + hash + insufficient ---
def _seed_prices(session, symbol="WTI", n=10, future=False):
    base = datetime.now(UTC).replace(microsecond=0)
    for i in range(n):
        dt = base - timedelta(days=n - i) + (timedelta(days=30) if future else timedelta(0))
        session.add(MarketObservation(
            symbol=symbol, asset_class="energy", value=80.0 + i,
            unit="usd_per_bbl", currency="USD", source_name="test", observed_at=dt,
        ))
    session.commit()
    return base


def test_context_point_in_time() -> None:
    session = TestingSession()
    try:
        as_of = _seed_prices(session)
        pack = build_context_pack(session, target="market:WTI", horizon_days=30, as_of=as_of)
        assert pack.insufficient_reason is None
        assert pack.reference_price == 80.0 + 9
        # ردیف‌های آینده حذف شده‌اند
        _seed_prices(session, n=3, future=True)
        pack2 = build_context_pack(session, target="market:WTI", horizon_days=30, as_of=as_of)
        assert pack2.reference_price == pack.reference_price
        assert pack2.context_hash == pack.context_hash  # بازتولیدپذیر
    finally:
        session.close()


def test_context_insufficient() -> None:
    session = TestingSession()
    try:
        pack = build_context_pack(session, target="market:NOPE", horizon_days=30)
        assert pack.insufficient_reason is not None
        assert pack.reference_price is None
    finally:
        session.close()


# --- engine with fake provider ---
class _FakeGateway:
    def __init__(self, probs: dict[str, float], fail_agents: set[str] | None = None) -> None:
        self.probs = probs
        self.fail = fail_agents or set()
        self.models_seen: list[str | None] = []

    async def generate(self, request):  # noqa: ANN001, ANN202
        self.models_seen.append(request.metadata.get("model"))
        agent = (request.task or "").replace("debate_", "")
        if agent in self.fail:
            from backend.ai.schemas.types import AIError, AIErrorKind
            raise AIError("boom", kind=AIErrorKind.provider_error, retryable=False)
        p = self.probs.get(agent, 0.6)
        return AIResponse(text=_agent_json(p), provider="fake", model="fake-1",
                          usage=AIUsage(prompt_tokens=10, completion_tokens=5,
                                        total_tokens=15),
                          cost_estimate=0.001, latency_ms=1.0)


def test_engine_full_run_fake() -> None:
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)
        engine.gateway = _FakeGateway({"bull": 0.8, "bear": 0.3, "macro": 0.6,
                                       "geopolitical": 0.55, "risk_critic": 0.5})
        before = session.execute(select(Forecast)).scalars().all()
        n_before = len(before)
        outcome = asyncio.run(engine.run(target="market:WTI", horizon_days=30))
        assert outcome.status == "done"
        assert outcome.consensus is not None and 0.02 <= outcome.consensus <= 0.98
        assert outcome.run_id is not None
        # Ledger: ۵ agent + لنگر + اجماع = ۷ ردیف جدید، قدیمی‌ها سر جایشان
        after = session.execute(select(Forecast)).scalars().all()
        assert len(after) == n_before + 7
        models = {f.model for f in after if f.model and f.model.startswith("debate")}
        assert "debate_consensus" in models
        assert any(m.startswith("debate:bull:") for m in models)
        # پیام‌ها ذخیره شده‌اند (۵ دور۱ + ۵ دور۲ + لنگر کمی + گزارش)
        import uuid as _uuid

        msgs = session.execute(
            select(DebateMessage).where(
                DebateMessage.run_id == _uuid.UUID(str(outcome.run_id))
            )
        ).scalars().all()
        assert len(msgs) == 12
        run = session.get(DebateRun, _uuid.UUID(str(outcome.run_id)))
        assert run is not None and run.context_hash
    finally:
        session.close()


def test_engine_model_override_reaches_provider() -> None:
    import os

    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session, model="custom-model-x")
        os.environ["DEBATE_MODEL_BULL"] = "custom-model-x"
        from backend.core.config import get_settings
        get_settings.cache_clear()
        try:
            engine = DebateEngine(session)
            fake = _FakeGateway({"bull": 0.8})
            engine.gateway = fake
            asyncio.run(engine.run(target="market:WTI", horizon_days=30, max_rounds=1))
            assert "custom-model-x" in fake.models_seen
        finally:
            del os.environ["DEBATE_MODEL_BULL"]
            get_settings.cache_clear()
    finally:
        session.close()


def test_engine_agent_failure_does_not_crash() -> None:
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)
        engine.gateway = _FakeGateway({"bull": 0.8}, fail_agents={"bear", "macro",
                                                                  "geopolitical",
                                                                  "risk_critic"})
        outcome = asyncio.run(engine.run(target="market:WTI", horizon_days=30, max_rounds=1))
        # فقط bull + لنگر → باز هم اجماع دارد، خطاها ثبت شده‌اند
        assert outcome.status == "done"
        assert outcome.consensus is not None
    finally:
        session.close()


def test_engine_all_llm_failed_is_failed_not_quant_only() -> None:
    """اگر هیچ agent واقعی موفق نشد، اجماع تک‌لنگر ثبت نمی‌شود (گمراه‌کننده است)."""
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)
        engine.gateway = _FakeGateway({}, fail_agents={"bull", "bear", "macro",
                                                       "geopolitical", "risk_critic"})
        n_before = len(session.execute(select(Forecast)).scalars().all())
        outcome = asyncio.run(engine.run(target="market:WTI", horizon_days=30, max_rounds=1))
        assert outcome.status == "failed"
        assert outcome.consensus is None
        assert outcome.run_id is not None
        n_after = len(session.execute(select(Forecast)).scalars().all())
        assert n_after == n_before  # هیچ ردیف Ledger ساخته نشد
    finally:
        session.close()


def test_engine_schema_invalid_gets_repair_retry() -> None:
    """خروجی JSON ناقص → یک repair retry → بهبودیافت."""
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)

        class _SeqFake(_FakeGateway):
            def __init__(self) -> None:
                super().__init__({})
                self.n = 0

            async def generate(self, request):  # noqa: ANN001, ANN202
                self.n += 1
                if self.n == 1:
                    return AIResponse(text='{"direction": "up"}', provider="fake",
                                      model="fake-1", usage=AIUsage(),
                                      cost_estimate=0.001, latency_ms=1.0)
                return AIResponse(text=_agent_json(0.7), provider="fake",
                                  model="fake-1", usage=AIUsage(),
                                  cost_estimate=0.001, latency_ms=1.0)

        engine.gateway = _SeqFake()
        outcome = asyncio.run(engine.run(target="market:WTI", horizon_days=30, max_rounds=1))
        assert outcome.status == "done"
        bull_p = None
        for fc_id in outcome.forecast_ids:
            import uuid as _uuid
            fc = session.get(Forecast, _uuid.UUID(fc_id))
            if (fc.model or "").startswith("debate:bull:"):
                bull_p = fc.probability
        assert bull_p == 0.7
    finally:
        session.close()


def test_engine_budget_stop() -> None:
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)
        engine.settings = type(engine.settings)(
            **{**engine.settings.model_dump(), "debate_max_tokens_per_run": 1}
        )
        outcome = asyncio.run(engine.run(target="market:WTI", dry_run=False))
        assert outcome.status == "budget_stopped"
        assert outcome.run_id is not None
    finally:
        session.close()


def test_engine_dry_run_makes_no_calls() -> None:
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)
        fake = _FakeGateway({})
        engine.gateway = fake
        outcome = asyncio.run(engine.run(target="market:WTI", dry_run=True))
        assert outcome.status == "dry_run"
        assert fake.models_seen == []
        assert outcome.run_id is None
    finally:
        session.close()


# --- outcome: actual_bool for debate probability forecasts ---
def test_outcome_sets_actual_bool_from_reference() -> None:
    from domains.forecast.outcome import OutcomeEngine

    session = TestingSession()
    try:
        now = datetime.now(UTC).replace(microsecond=0)
        session.add(MarketObservation(
            symbol="WTI", asset_class="energy", value=100.0,
            unit="usd_per_bbl", currency="USD", source_name="test",
            observed_at=now - timedelta(days=40)))
        session.add(MarketObservation(
            symbol="WTI", asset_class="energy", value=110.0,
            unit="usd_per_bbl", currency="USD", source_name="test",
            observed_at=now + timedelta(days=1)))
        fc = Forecast(
            valid_from=now - timedelta(days=40), target_date=now,
            horizon="short", target="market:WTI", probability=0.7,
            expected_value=None, confidence=0.6, model="debate_consensus",
            status="active",
            evidence=json.dumps({"reference_price": 100.0}),
        )
        fc2 = Forecast(
            valid_from=now - timedelta(days=40), target_date=now,
            horizon="short", target="market:WTI", probability=0.7,
            expected_value=None, confidence=0.6, model="debate:bull:x",
            status="active", evidence=json.dumps({}),
        )
        session.add_all([fc, fc2])
        session.commit()
        out = OutcomeEngine(session).resolve_all(target="market:WTI")
        assert out.resolved == 2
        oc1 = session.execute(
            select(ForecastOutcome).where(ForecastOutcome.forecast_id == fc.id)
        ).scalars().one()
        oc2 = session.execute(
            select(ForecastOutcome).where(ForecastOutcome.forecast_id == fc2.id)
        ).scalars().one()
        assert oc1.actual_bool == "true"  # 110 > 100
        assert oc2.actual_bool is None  # بدون مرجع → تهی
    finally:
        session.close()


# --- API ---
def test_debate_api_requires_live(client: TestClient) -> None:
    res = client.post("/api/debate/run", json={"target": "market:WTI"})
    assert res.status_code == 422


def test_debate_api_dry_run_and_list(client: TestClient) -> None:
    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
    finally:
        session.close()
    res = client.post("/api/debate/run",
                      json={"target": "market:WTI", "dry_run": True})
    assert res.status_code == 200
    assert res.json()["status"] == "dry_run"
    listing = client.get("/api/debate/runs")
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)


def test_dry_run_calibrated_with_cost_ceiling() -> None:
    """Step 9: برآورد = خام × فاکتور کالیبراسیون + سقف دلاری از قیمت‌ها."""
    import asyncio

    from domains.debate.engine import CALIBRATION_FACTOR, DebateEngine

    session = TestingSession()
    try:
        _seed_prices(session)
        _seed_price(session)
        engine = DebateEngine(session)
        out = asyncio.run(engine.run(target="market:WTI", horizon_days=30, dry_run=True))
        assert out.status == "dry_run"
        assert out.total_tokens is not None and out.total_tokens > 0
        msg = out.errors[0]
        assert f"x{CALIBRATION_FACTOR}" in msg
        # سقف دلاری از قیمت fake-1 (1.0/2.0) آمده، نه حدس
        assert "cost ceiling" in msg
        assert "no price" not in msg
    finally:
        session.close()

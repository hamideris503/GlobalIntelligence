"""Offline GraphRAG synthesis evaluation harness — Step 1D.20.

هیچ provider واقعی و هیچ شبکه‌ای در این تست‌ها صدا زده نمی‌شود.
"""
from __future__ import annotations

import asyncio
import json

import jsonschema
import pytest

from backend.ai import budget
from backend.ai.gateway.gateway import AIGateway
from backend.ai.schemas.types import AIError, AIErrorKind
from backend.core.config import get_settings
from backend.database.models.entity import Entity, EntityRelationship
from domains.research import run_graphrag_eval as harness
from domains.research.graphrag import DEFAULT_LIMIT, GraphRAGService
from tests.conftest import TestingSession


def _forbid_real_provider(monkeypatch) -> None:
    """اگر مسیر واقعی Gateway صدا زده شود، تست فوراً شکست می‌خورد."""
    def _boom(*_a, **_k):
        raise AssertionError("real provider path must not be reached")

    monkeypatch.setattr(AIGateway, "generate", _boom)
    monkeypatch.setattr(AIGateway, "_provider", _boom)


# 1) حالت پیش‌فرض هیچ درخواست provider نمی‌فرستد
def test_default_sends_no_provider_request(monkeypatch) -> None:
    _forbid_real_provider(monkeypatch)
    report = harness.run_eval((10, 30, 50))
    assert report["mode"] == "offline"
    assert report["provider_calls"] == 0
    assert report["live_enabled"] is False
    assert all(s["provider_usage"] is None for s in report["samples"])


# 2) نمونه‌های ۱۰/۳۰/۵۰ درست ساخته می‌شوند
def test_required_sample_sizes_built() -> None:
    report = harness.run_eval()
    assert [s["edges"] for s in report["samples"]] == [10, 30, DEFAULT_LIMIT]
    for s in report["samples"]:
        assert s["nodes"] == s["edges"] + 1
        assert s["context_chars"] > 0
        assert s["input_chars"] > 0
        assert s["input_tokens_estimate"] > 0


# 3) محدودیت‌های فعلی context حفظ می‌شوند (سقف یال + برش ۴۰۰۰ کاراکتر)
def test_context_limits_preserved(monkeypatch) -> None:
    # برش ۴۰۰۰ کاراکتری در ورودی واقعی Gateway
    _forbid_real_provider(monkeypatch)
    sample = harness.evaluate_sample(3000)
    assert sample["context_truncated"] is True
    assert sample["input_chars"] < sample["context_chars"]
    assert sample["input_chars"] <= harness.PROMPT_CONTEXT_CHARS + 120

    # سقف یال در retrieve واقعی: ۶۰ یال → حداکثر DEFAULT_LIMIT
    session = TestingSession()
    try:
        ents = [
            Entity(type="organization", canonical_name=f"e{i}",
                   display_name=f"E{i}")
            for i in range(61)
        ]
        session.add_all(ents)
        session.flush()
        session.add_all(
            [EntityRelationship(from_entity_id=ents[0].id,
                                to_entity_id=ents[i].id,
                                relation="related_to", weight=0.5)
             for i in range(1, 61)]
        )
        session.commit()
        ctx = GraphRAGService(session).retrieve(entity_names=["E0"],
                                                limit=DEFAULT_LIMIT)
        assert len(ctx.edges) <= DEFAULT_LIMIT
        assert ctx.truncated is True
    finally:
        session.close()


# 4) پاسخ ساختگی نامعتبر یا ناقص به‌عنوان خروجی معتبر پذیرفته نمی‌شود
def test_invalid_synthetic_response_not_accepted(monkeypatch) -> None:
    _forbid_real_provider(monkeypatch)
    assert harness.is_valid_synth_output(harness.synthetic_response(10)) is True
    assert harness.is_valid_synth_output({}) is False
    assert harness.is_valid_synth_output({"summary": "s"}) is False
    assert harness.is_valid_synth_output({"summary": 1, "key_relations": []}) is False
    assert harness.is_valid_synth_output(
        {"summary": "s", "key_relations": "not-a-list"}) is False

    with pytest.raises(jsonschema.ValidationError):
        harness.validate_synth_output({"summary": "s"})

    bad = harness.evaluate_sample(10, response={"summary": "only"})
    assert bad["output_schema_valid"] is False
    assert harness.evaluate_sample(10)["output_schema_valid"] is True


# 5) usage ساختگی با usage واقعی اشتباه نمی‌شود
def test_synthetic_usage_not_reported_as_real() -> None:
    report = harness.run_eval((10,))
    s = report["samples"][0]
    assert s["usage_source"] == "synthetic"
    assert s["provider_usage"] is None
    assert s["synthetic"] is True
    assert "not real provider usage" in report["note"]


# 6) آزمون زنده بدون فعال‌سازی صریح و کامل قابل اجرا نیست
def test_live_option_refused_without_full_opt_in(monkeypatch, capsys) -> None:
    _forbid_real_provider(monkeypatch)
    # بدون فلگ: آفلاین و کد خروج ۰
    assert harness.main([]) == 0
    out = capsys.readouterr().out
    assert '"mode": "offline"' in out

    # فلگ تنها: رد صریح پیش از هر ارسال
    assert harness.main(["--allow-live-provider"]) == 2
    out = capsys.readouterr().out
    assert '"mode": "live"' in out
    assert "--live-provider" in out and "--acknowledge-cost" in out

    # بدون provider/model مشخص → توقف پیش از درخواست
    assert harness.main(["--allow-live-provider", "--acknowledge-cost"]) == 2
    # بدون تأیید هزینه → توقف
    assert harness.main(["--allow-live-provider", "--live-provider", "openai",
                         "--live-model", "m"]) == 2


def _live_mode_off(monkeypatch) -> None:
    import backend.core.mock_mode as mock_mode

    monkeypatch.setattr(mock_mode, "effective_mock_mode", lambda: False)


# provider mock یا ناشناخته رد می‌شود (پیش از هر ارسال)
def test_live_plan_rejects_bad_provider(monkeypatch) -> None:
    _live_mode_off(monkeypatch)
    for bad in (None, "", "mock", "no-such-provider", "cloudflare"):
        with pytest.raises(harness.LiveProbeRefused):
            harness.build_live_plan(provider=bad, model="m")
    with pytest.raises(harness.LiveProbeRefused):
        harness.build_live_plan(provider="openai", model="  ")
    plan = harness.build_live_plan(provider="openai", model="gpt-4o-mini")
    assert plan["chain"] == ["openai"] and plan["retries"] == 0
    assert plan["max_tokens"] == 2000 and plan["max_sends"] == 3
    assert plan["samples"] == [10, 30, 50]


def test_live_plan_refuses_mock_mode(monkeypatch) -> None:
    import backend.core.mock_mode as mock_mode

    monkeypatch.setattr(mock_mode, "effective_mock_mode", lambda: True)
    with pytest.raises(harness.LiveProbeRefused):
        harness.build_live_plan(provider="openai", model="m")


# سقف مؤثر دقیقاً ۲۰۰۰ و در payload واقعی حفظ می‌شود
def test_live_cap_pinned_and_preserved_in_payload(monkeypatch) -> None:
    _forbid_real_provider(monkeypatch)
    from backend.ai.providers.gemini import GeminiProvider
    from backend.ai.providers.openai import OpenAIProvider

    async def _run(request):
        inner_calls = {}

        class _Inner:
            async def structured_generate(self, req, schema):
                inner_calls["max_tokens"] = req.max_tokens
                from backend.ai.schemas.types import AIResponse

                return AIResponse(text="{}", provider="p", model="m")

        plan = {"provider": "openai", "model": "m"}
        capped = harness._CappedLiveGateway(
            _Inner(), OpenAIProvider(), {**plan, "max_tokens": 2000})
        req = harness._live_probe_request()
        assert req.max_tokens is None
        await capped.structured_generate(req, {})
        assert req.max_tokens == 2000
        assert inner_calls["max_tokens"] == 2000

        payload = OpenAIProvider()._payload(req)
        assert payload["max_tokens"] == 2000
        gen_payload = GeminiProvider()._payload(req)
        assert gen_payload["generationConfig"]["maxOutputTokens"] == 2000


def test_live_gateway_is_single_provider_no_retry(monkeypatch) -> None:
    _live_mode_off(monkeypatch)
    from backend.ai.providers.openai import OpenAIProvider

    plan = harness.build_live_plan(provider="openai", model="m")
    provider = OpenAIProvider()
    provider.api_key = "test-key"
    gw = harness.build_live_gateway(plan, provider)
    assert gw._max_retries == 0
    assert gw._route(harness._live_probe_request()).providers == ["openai"]


# محدودکننده‌ی HTTP: حداکثر ۳ ارسال؛ چهارمی پیش از شبکه رد می‌شود
def test_http_limiter_blocks_fourth_send_before_network() -> None:
    calls = []

    async def fake_post(*a, **k):
        calls.append((a, k))
        return "resp"

    class FakeClient:
        def __init__(self, *a, **k):
            self.post = fake_post

    limiter = harness.HttpSendLimiter(3)
    factory = limiter.wrap_client_factory(FakeClient)
    import asyncio

    async def go():
        for _ in range(3):
            client = factory()
            assert await client.post("http://x") == "resp"
        with pytest.raises(harness.LiveSendBudgetExceeded):
            await factory().post("http://x")

    asyncio.run(go())
    assert limiter.sends == 3
    assert len(calls) == 3  # ارسال چهارم هرگز به post واقعی نرسید


def test_send_limiter_installs_on_http_layer(monkeypatch) -> None:
    import backend.ai.providers.http_base as http_base

    limiter = harness.HttpSendLimiter(3)
    orig = harness.install_send_limiter(limiter)
    try:
        assert http_base.httpx.AsyncClient is not orig
    finally:
        harness.restore_send_limiter(orig)
    assert http_base.httpx.AsyncClient is orig


# خطای provider به retry خودکار منجر نمی‌شود (transport مصنوعی، بدون شبکه)
def test_live_wiring_single_send_on_provider_error(monkeypatch) -> None:
    _live_mode_off(monkeypatch)
    import httpx

    from backend.ai.providers.openai import OpenAIProvider
    from backend.ai.schemas.types import AIError, AIRequest, Message

    posts = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(request)
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    provider = OpenAIProvider()
    provider.api_key = "test-key"
    plan = harness.build_live_plan(provider="openai", model="m")
    gw = harness.build_live_gateway(plan, provider)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: real_client(*a, transport=transport, **k))
    with pytest.raises(AIError):
        import asyncio

        asyncio.run(gw.generate(AIRequest(messages=[Message.user("hi")],
                                          role="deep_analysis",
                                          task="graphrag_synthesize")))
    assert len(posts) == 1


# نمونه‌های ۱۰/۳۰/۵۰ قابل ثبت‌اند؛ usage/finish ناموجود و schema درست گزارش می‌شود
def test_live_evidence_fields() -> None:
    from backend.ai.schemas.types import AIUsage

    base = dict(run_id="r1", provider="openai", model="m", resolved_model="m2",
                edges=10, context_chars=100, cap=2000, sends_observed=1)
    full = harness.build_sample_evidence(
        **base, finish_reason="stop", mode="llm", stop_reason=None,
        usage=AIUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))
    assert full["usage_total"] == 15 and full["finish_reported"] is True
    assert full["truncated_output"] is False and full["schema_ok"] is True

    # usage=None هرگز صفر فرض نمی‌شود؛ finish ناموجود «گزارش‌نشده» است
    empty = harness.build_sample_evidence(
        **base, finish_reason=None, usage=None, mode="llm", stop_reason=None)
    assert empty["usage_total"] is None and empty["finish_reported"] is False
    assert empty["finish_reason"] is None

    # برش سقف توکن، خروجی کامل محسوب نمی‌شود
    cut = harness.build_sample_evidence(
        **base, finish_reason="length", usage=None, mode="failed",
        stop_reason="output_truncated")
    assert cut["truncated_output"] is True and cut["schema_ok"] is False


# بدون credential معتبر، پیش از ارسال متوقف می‌شود (بدون چاپ secret)
def test_live_no_credential_stops_before_send(monkeypatch, capsys) -> None:
    _forbid_real_provider(monkeypatch)
    _live_mode_off(monkeypatch)
    plan = harness.build_live_plan(provider="openai", model="m")
    monkeypatch.setattr(
        "backend.ai.providers.registry.build_provider_with_store",
        lambda name: _KeylessProvider())
    with pytest.raises(harness.LiveProbeRefused) as exc:
        harness.check_live_provider(plan)
    assert "credential" in str(exc.value)


class _KeylessProvider:
    name = "openai"
    default_model = "m"

    def configured(self) -> bool:
        return False


# 7) هیچ سقف عملیاتی جدیدی برای GraphRAG ثبت نمی‌شود
def test_no_new_operational_cap_registered(monkeypatch) -> None:
    _forbid_real_provider(monkeypatch)
    assert "graphrag_synthesize" not in (get_settings().ai_task_max_tokens or {})
    report = harness.run_eval((10, 30, 50))
    assert all(s["output_cap_effective"] is None for s in report["samples"])


# 8) رفتار عادی retrieval و mock در GraphRAG تغییر نمی‌کند
def test_normal_retrieval_and_mock_unchanged(monkeypatch) -> None:
    _forbid_real_provider(monkeypatch)
    settings_before = get_settings().mock_mode

    session = TestingSession()
    try:
        a = Entity(type="organization", canonical_name="a", display_name="A")
        b = Entity(type="organization", canonical_name="b", display_name="B")
        session.add_all([a, b])
        session.flush()
        session.add(EntityRelationship(from_entity_id=a.id, to_entity_id=b.id,
                                      relation="affects", weight=0.8))
        session.commit()
        service = GraphRAGService(session)
        ctx = service.retrieve(entity_names=["A"])
        assert len(ctx.edges) == 1
        out = asyncio.run(service.synthesize(ctx))
        assert out["mode"] == "extractive"
        assert "A affects B" in out["key_relations"]
    finally:
        session.close()

    # اجرای harness تنظیمات سراسری را تغییر نمی‌دهد
    harness.run_eval((10,))
    assert get_settings().mock_mode == settings_before


def test_estimate_input_matches_budget_estimator() -> None:
    # اطمینان از اینکه harness از همان تخمین‌گر بودجه‌ی پروژه استفاده می‌کند
    request_holder: dict = {}

    class _Capture:
        async def structured_generate(self, request, schema):
            from backend.ai.schemas.types import AIResponse

            request_holder["request"] = request
            return AIResponse(text="{}", provider="synthetic", model="synthetic",
                              structured=harness.synthetic_response(10))

    service = GraphRAGService(None)
    service._settings = service._settings.model_copy(update={"mock_mode": False})
    service.gateway = _Capture()
    asyncio.run(service.synthesize(harness.synthetic_context(10)))

    sample = harness.evaluate_sample(10)
    assert sample["input_tokens_estimate"] == budget.estimate_input_tokens(
        request_holder["request"])


def test_ai_error_budget_kind_available() -> None:
    # قرارداد fail-closed بودجه (بدون فعال‌سازی) دست‌نخورده است
    assert AIErrorKind.estimate.value == "estimate"
    assert AIErrorKind.budget.value == "budget"
    assert AIError("x", kind=AIErrorKind.budget).retryable is False


def test_text_fixture_traverses_real_synthesize_path(monkeypatch) -> None:
    # پاسخ معتبر از response.text (با structured=None) مسیر واقعی را طی می‌کند
    _forbid_real_provider(monkeypatch)
    body = json.dumps(harness.synthetic_response(10), ensure_ascii=False)
    sample = harness.evaluate_sample(10, response=None, text=body)
    assert sample["output_mode"] == "llm"
    assert sample["output_schema_valid"] is True
    assert sample["provider_usage"] is None
    assert sample["synthetic"] is True
    assert sample["output_cap_effective"] is None

    # متن نامعتبر → failure کنترل‌شده، نه موفقیت جعلی
    bad = harness.evaluate_sample(10, response=None, text="not json {{{")
    assert bad["output_mode"] == "failed"
    assert bad["output_schema_valid"] is False

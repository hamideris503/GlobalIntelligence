"""Offline GraphRAG synthesis evaluation harness — Step 1D.20.

هیچ provider واقعی و هیچ شبکه‌ای در این تست‌ها صدا زده نمی‌شود.
"""
from __future__ import annotations

import asyncio

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


# 6) آزمون زنده بدون فعال‌سازی صریح قابل اجرا نیست
def test_live_option_refused_without_bounded_tracing(monkeypatch, capsys) -> None:
    _forbid_real_provider(monkeypatch)
    # بدون فلگ: آفلاین و کد خروج ۰
    assert harness.main([]) == 0
    out = capsys.readouterr().out
    assert '"mode": "offline"' in out

    # با فلگ: صریحاً رد می‌شود و درخواست شبکه‌ای نمی‌رود
    assert harness.main(["--allow-live-provider"]) == 2
    out = capsys.readouterr().out
    assert '"mode": "live"' in out
    assert "not implemented" in out


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

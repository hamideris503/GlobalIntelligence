"""Tests for the AI Gateway & providers (Phase 5)."""
from __future__ import annotations

import asyncio

import pytest

from backend.ai.gateway.gateway import AIGateway
from backend.ai.providers.base import BaseProvider
from backend.ai.providers.registry import available_providers, build_provider
from backend.ai.routing.router import Route, resolve_route
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    Message,
    ProviderHealth,
)


def _req(text: str = "hello", **kw) -> AIRequest:
    return AIRequest(messages=[Message.user(text)], **kw)


def test_registry_lists_and_builds() -> None:
    names = available_providers()
    assert "mock" in names
    p = build_provider("mock")
    assert p.name == "mock"


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError):
        build_provider("does-not-exist")


def test_resolve_route_default_is_empty() -> None:
    """پیش‌فرض خالی است تا زنجیره از تنظیمات ساخته شود (نه mock ثابت)."""
    r = resolve_route("does-not-exist", None)
    assert isinstance(r, Route)
    assert r.providers == []


def test_mock_generate() -> None:
    provider = build_provider("mock")
    resp = asyncio.run(provider.generate(_req("hello world")))
    assert resp.provider == "mock"
    assert "hello" in resp.text


def test_mock_structured_output() -> None:
    provider = build_provider("mock")
    schema = {
        "type": "object",
        "required": ["topic", "score"],
        "properties": {"topic": {"type": "string"}, "score": {"type": "integer"}},
    }
    resp = asyncio.run(
        provider.structured_generate(_req("some text", task="extract"), schema)
    )
    assert resp.structured == {"topic": "mock", "score": 0}


def test_gateway_uses_mock_by_default() -> None:
    gateway = AIGateway()
    resp = asyncio.run(gateway.generate(_req("ping", role="fast_extraction")))
    assert resp.provider == "mock"


class _FailingProvider(BaseProvider):
    name = "failing"

    async def generate(self, request: AIRequest) -> AIResponse:
        raise AIError("boom", kind=AIErrorKind.provider_error, provider=self.name)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, healthy=False, detail="always fails")


def test_gateway_uses_mock_in_mock_mode() -> None:
    """در MOCK_MODE، Gateway همیشه mock را برمی‌گرداند."""
    gateway = AIGateway()
    assert gateway._settings.mock_mode is True
    resp = asyncio.run(gateway.generate(_req("ping", role="fast_extraction")))
    assert resp.provider == "mock"
    assert resp.is_mock is True


def test_gateway_no_mock_fallback_in_production() -> None:
    """در production، mock باید نادیده گرفته شود و در نبود Provider واقعی خطا بدهد."""
    gateway = AIGateway()
    # شبیه‌سازی production
    gateway._settings.mock_mode = False
    gateway._settings.ai_default_provider = "failing"
    gateway._providers["failing"] = _FailingProvider()

    with pytest.raises(AIError):
        asyncio.run(gateway.generate(_req("ping", role="fast_extraction")))


def test_gateway_real_provider_preferred_over_mock() -> None:
    """با Provider واقعی، mock نباید صدا زده شود."""
    gateway = AIGateway()
    gateway._settings.mock_mode = False
    gateway._settings.ai_default_provider = "mock"

    class _Realish(BaseProvider):
        name = "realish"

        async def generate(self, request: AIRequest) -> AIResponse:
            return AIResponse(text="real", provider=self.name, model="m")

    gateway._providers["realish"] = _Realish()
    gateway._settings.ai_default_provider = "realish"
    resp = asyncio.run(gateway.generate(_req("ping")))
    assert resp.provider == "realish"
    assert resp.is_mock is False


def test_ai_status_endpoint(client) -> None:
    """GET /api/ai/status: حالت Mock، ارائه‌دهندهٔ پیش‌فرض و نقش‌ها."""
    res = client.get("/api/ai/status")
    assert res.status_code == 200
    body = res.json()
    assert body["mock_mode"] is True
    assert isinstance(body["default_provider"], str)
    assert "fast_extraction" in body["roles"]
    assert "deep_analysis" in body["roles"]


def test_no_real_provider_fails_loudly(monkeypatch) -> None:
    """MOCK_MODE=false با پیش‌فرض mock: خطای صریح، نه خروجی ساختگی."""
    import asyncio

    from backend.ai.gateway import AIGateway
    from backend.ai.schemas.types import AIError, AIErrorKind, AIRequest, Message

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("AI_DEFAULT_PROVIDER", "mock")
    from backend.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(AIError) as exc_info:
            asyncio.run(AIGateway().generate(
                AIRequest(messages=[Message.user("hi")])))
        assert exc_info.value.kind == AIErrorKind.auth
        assert "no real provider" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


# --- finish_reason propagation (Step 1D.25; offline stubs, no network) ---
def test_response_without_finish_reason_defaults_to_none() -> None:
    resp = AIResponse(text="t", provider="p", model="m")
    assert resp.finish_reason is None


def test_response_preserves_finish_reason() -> None:
    resp = AIResponse(text="t", provider="p", model="m", finish_reason="length")
    assert resp.finish_reason == "length"


def test_structured_generate_keeps_finish_reason() -> None:
    gateway = AIGateway()
    gateway._settings.mock_mode = False
    gateway._settings.ai_default_provider = "finstub"

    class _FinStub(BaseProvider):
        name = "finstub"

        async def generate(self, request: AIRequest) -> AIResponse:
            from backend.ai.schemas.types import AIUsage

            return AIResponse(
                text='{"summary": "s", "key_relations": ["A rel B"]}',
                provider=self.name, model="m",
                usage=AIUsage(prompt_tokens=10, completion_tokens=5,
                              total_tokens=15),
                structured={"summary": "s", "key_relations": ["A rel B"]},
                finish_reason="stop")

    gateway._providers["finstub"] = _FinStub()
    resp = asyncio.run(gateway.structured_generate(
        _req("hi", task="probe"), {"type": "object"}))
    assert resp.finish_reason == "stop"
    assert resp.text.startswith('{"summary"')
    assert resp.usage.total_tokens == 15
    assert resp.model == "m"
    assert resp.structured == {"summary": "s", "key_relations": ["A rel B"]}


def test_provider_without_finish_reason_reports_none() -> None:
    gateway = AIGateway()
    gateway._settings.mock_mode = False
    gateway._settings.ai_default_provider = "nofin"

    class _NoFin(BaseProvider):
        name = "nofin"

        async def generate(self, request: AIRequest) -> AIResponse:
            return AIResponse(text="t", provider=self.name, model="m")

    gateway._providers["nofin"] = _NoFin()
    resp = asyncio.run(gateway.generate(_req("hi")))
    assert resp.finish_reason is None

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

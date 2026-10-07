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


def test_resolve_route_default() -> None:
    r = resolve_route("does-not-exist", None)
    assert isinstance(r, Route)
    assert r.providers == ["mock"]


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


def test_gateway_falls_back_to_mock() -> None:
    """اگر Provider اول شکست بخورد، Gateway باید به mock fallback کند."""
    gateway = AIGateway(routes={"fast_extraction": Route("fast_extraction", ["failing"])})
    gateway._providers["failing"] = _FailingProvider()
    resp = asyncio.run(gateway.generate(_req("ping", role="fast_extraction")))
    assert resp.provider == "mock"

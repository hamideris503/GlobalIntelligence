"""Tests for HTTP providers using httpx MockTransport (Phase 10 fix)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import backend.ai.providers.http_base as hb
from backend.ai.providers.openai import OpenAIProvider
from backend.ai.schemas.types import AIError, AIErrorKind, AIRequest, Message


class _TransportPatch:
    """جایگزینی AsyncClient با نسخه‌ی transportدار (بدون شبکه)."""

    def __init__(self, handler) -> None:
        self._transport = httpx.MockTransport(handler)
        self._orig = None

    def __enter__(self):
        self._orig = hb.httpx.AsyncClient
        transport = self._transport
        orig = self._orig

        def patched(*args, **kwargs):
            kwargs["transport"] = transport
            return orig(*args, **kwargs)

        hb.httpx.AsyncClient = patched
        return self

    def __exit__(self, *exc):
        hb.httpx.AsyncClient = self._orig


def _provider() -> OpenAIProvider:
    p = OpenAIProvider()
    p.api_key = "test-key"
    p._default_timeout = 5.0
    return p


def test_openai_provider_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"]
        return httpx.Response(
            200,
            json={
                "model": "gpt-test",
                "choices": [{"message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    with _TransportPatch(handler):
        resp = asyncio.run(_provider().generate(AIRequest(messages=[Message.user("hi")])))
    assert resp.text == "hello"
    assert resp.provider == "openai"
    assert resp.is_mock is False
    assert resp.usage.total_tokens == 5


def test_openai_provider_maps_429_to_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    with _TransportPatch(handler), pytest.raises(AIError) as exc:
        asyncio.run(_provider().generate(AIRequest(messages=[Message.user("hi")])))
    assert exc.value.kind == AIErrorKind.rate_limit
    assert exc.value.retryable is True


def test_provider_not_configured_raises_auth() -> None:
    p = OpenAIProvider()
    p.api_key = None
    with pytest.raises(AIError) as exc:
        asyncio.run(p.generate(AIRequest(messages=[Message.user("hi")])))
    assert exc.value.kind == AIErrorKind.auth

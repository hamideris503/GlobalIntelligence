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


def test_gemini_sets_json_mime_for_schema() -> None:
    """AUDIT-REPAIR: schema روی Gemini هم به MimeType ترجمه می‌شود."""
    from backend.ai.providers.gemini import GeminiProvider

    p = GeminiProvider()
    plain = p._payload(AIRequest(messages=[Message.user("hi")]))
    assert "responseMimeType" not in plain.get("generationConfig", {})
    with_schema = p._payload(
        AIRequest(messages=[Message.user("hi")], json_schema={"type": "object"})
    )
    assert with_schema["generationConfig"]["responseMimeType"] == "application/json"


def test_openrouter_sets_json_object_for_schema() -> None:
    """AUDIT-REPAIR: schema روی OpenRouter هم مثل OpenAI اعمال می‌شود."""
    from backend.ai.providers.openrouter import OpenRouterProvider

    p = OpenRouterProvider()
    plain = p._payload(AIRequest(messages=[Message.user("hi")]))
    assert "response_format" not in plain
    with_schema = p._payload(
        AIRequest(messages=[Message.user("hi")], json_schema={"type": "object"})
    )
    assert with_schema["response_format"] == {"type": "json_object"}


# --- finish_reason extraction (Step 1D.25; offline fixtures, no network) ---
def _openai_payload(finish="length", *, n_choices=1, usage=None):
    choices = [
        {"message": {"role": "assistant", "content": f"r{i}"},
         "finish_reason": finish}
        for i in range(n_choices)
    ]
    return {
        "model": "gpt-test",
        "choices": choices,
        "usage": usage if usage is not None else {
            "prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }


def test_openai_finish_reason_flows_to_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_payload("length"))

    with _TransportPatch(handler):
        resp = asyncio.run(_provider().generate(AIRequest(messages=[Message.user("hi")])))
    assert resp.finish_reason == "length"
    assert resp.text == "r0"
    assert resp.usage.total_tokens == 5
    assert resp.model == "gpt-test"


def test_openai_missing_finish_reason_is_none() -> None:
    payload = _openai_payload()
    del payload["choices"][0]["finish_reason"]
    text, usage, model, finish = OpenAIProvider()._parse(payload)
    assert finish is None
    assert text == "r0" and usage.total_tokens == 5


def test_openai_finish_from_selected_choice_only() -> None:
    payload = _openai_payload("stop", n_choices=2)
    payload["choices"][1]["finish_reason"] = "length"
    _, _, _, finish = OpenAIProvider()._parse(payload)
    assert finish == "stop"


def test_openai_invalid_finish_reason_not_fabricated() -> None:
    for bad in (123, ["length"], {"r": 1}):
        payload = _openai_payload(bad)
        text, _, _, finish = OpenAIProvider()._parse(payload)
        assert finish is None
        assert text == "r0"  # پاسخ معتبر خراب نمی‌شود


def test_openai_family_extracts_finish_reason() -> None:
    from backend.ai.providers.groq import GroqProvider
    from backend.ai.providers.openai_compatible import OpenAICompatibleProvider
    from backend.ai.providers.openrouter import OpenRouterProvider

    for cls in (GroqProvider, OpenRouterProvider):
        _, _, _, finish = cls()._parse(_openai_payload("stop"))
        assert finish == "stop"
    compat = OpenAICompatibleProvider(api_key="k",
                                      base_url="https://api.example.com/v1")
    _, _, _, finish = compat._parse(_openai_payload("stop"))
    assert finish == "stop"


def test_anthropic_stop_reason_extraction() -> None:
    from backend.ai.providers.anthropic import AnthropicProvider

    data = {"content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 4, "output_tokens": 2},
            "model": "claude-x", "stop_reason": "max_tokens"}
    text, usage, model, finish = AnthropicProvider()._parse(data)
    assert (text, model, finish) == ("hi", "claude-x", "max_tokens")
    assert usage.completion_tokens == 2

    del data["stop_reason"]
    assert AnthropicProvider()._parse(data)[3] is None
    data["stop_reason"] = 7
    assert AnthropicProvider()._parse(data)[3] is None


def test_gemini_finish_reason_extraction() -> None:
    from backend.ai.providers.gemini import GeminiProvider

    def payload(reason="MAX_TOKENS"):
        return {"candidates": [{"content": {"parts": [{"text": "hi"}]},
                                "finishReason": reason}],
                "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2,
                                  "totalTokenCount": 6}}

    text, usage, _, finish = GeminiProvider()._parse(payload())
    assert (text, finish) == ("hi", "MAX_TOKENS")
    assert usage.total_tokens == 6

    no_reason = payload()
    del no_reason["candidates"][0]["finishReason"]
    text, _, _, finish = GeminiProvider()._parse(no_reason)
    assert (text, finish) == ("hi", None)

    empty = GeminiProvider()._parse({"candidates": []})
    assert empty[0] == "" and empty[3] is None


def test_cloudflare_reports_no_finish_reason() -> None:
    from backend.ai.providers.cloudflare import CloudflareProvider

    text, usage, model, finish = CloudflareProvider()._parse(
        {"success": True, "result": {"response": "hi"}})
    assert (text, finish) == ("hi", None)
    assert usage.total_tokens is None  # برآورد usage در generate() پر می‌شود

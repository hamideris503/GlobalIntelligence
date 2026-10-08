"""Anthropic Provider (Messages API)."""
from __future__ import annotations

from typing import Any

from backend.ai.providers.http_base import HTTPProvider
from backend.ai.schemas.types import AIRequest, AIUsage
from backend.core.config import get_settings


class AnthropicProvider(HTTPProvider):
    name = "anthropic"
    api_key_env = "ANTHROPIC_API_KEY"

    def __init__(self) -> None:
        s = get_settings()
        self.api_key = getattr(s, "anthropic_api_key", None) or None
        self.base_url = getattr(s, "anthropic_base_url", "https://api.anthropic.com")
        self.default_model = getattr(s, "anthropic_model", "claude-3-5-haiku-latest")
        self._default_timeout = float(s.ai_request_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }

    def _endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/v1/messages"

    def _payload(self, request: AIRequest) -> dict[str, Any]:
        system_parts = [m.content for m in request.messages if m.role == "system"]
        convo = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role in ("user", "assistant")
        ]
        payload: dict[str, Any] = {
            "model": request.metadata.get("model", self.default_model),
            "messages": convo,
            "max_tokens": request.max_tokens or 1024,
            "temperature": request.temperature,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        return payload

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str]:
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        usage = data.get("usage", {}) or {}
        return (
            text,
            AIUsage(
                prompt_tokens=usage.get("input_tokens"),
                completion_tokens=usage.get("output_tokens"),
                total_tokens=(usage.get("input_tokens") or 0)
                + (usage.get("output_tokens") or 0),
            ),
            data.get("model", self.default_model),
        )

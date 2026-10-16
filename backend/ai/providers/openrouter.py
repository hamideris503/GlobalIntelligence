"""OpenRouter Provider (OpenAI-compatible)."""
from __future__ import annotations

from typing import Any

from backend.ai.providers.http_base import HTTPProvider
from backend.ai.schemas.types import AIRequest, AIUsage
from backend.core.config import get_settings


class OpenRouterProvider(HTTPProvider):
    name = "openrouter"
    api_key_env = "OPENROUTER_API_KEY"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 default_model: str | None = None) -> None:
        s = get_settings()
        self.api_key = api_key or getattr(s, "openrouter_api_key", None) or None
        self.base_url = base_url or getattr(s, "openrouter_base_url", "https://openrouter.ai/api/v1")
        self.default_model = default_model or getattr(s, "openrouter_model", "openai/gpt-4o-mini")
        self._default_timeout = float(s.ai_request_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _endpoint(self, request: AIRequest | None = None) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _payload(self, request: AIRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.metadata.get("model", self.default_model),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.json_schema is not None:
            # AUDIT-REPAIR: مثل OpenAI (سازگار) — قبلاً schema نادیده گرفته می‌شد
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str, str | None]:
        first = data["choices"][0]
        choice = first["message"]
        text = choice.get("content") or ""
        usage = data.get("usage", {}) or {}
        finish = first.get("finish_reason")
        return (
            text,
            AIUsage(
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            ),
            data.get("model", self.default_model),
            finish if isinstance(finish, str) else None,
        )

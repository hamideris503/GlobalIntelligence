"""Groq Provider (OpenAI-compatible).

مستندات رسمی: https://console.groq.com/docs/api-reference
- POST https://api.groq.com/openai/v1/chat/completions
- احراز هویت: Authorization: Bearer $GROQ_API_KEY
- structured: response_format {"type": "json_object"} (یا json_schema در مدل‌های پشتیبانی‌شده)
- usage: prompt_tokens/completion_tokens/total_tokens
- لیست مدل‌ها: GET {base}/models
"""
from __future__ import annotations

from typing import Any

from backend.ai.providers.http_base import HTTPProvider
from backend.ai.schemas.types import AIRequest, AIUsage
from backend.core.config import get_settings


class GroqProvider(HTTPProvider):
    name = "groq"
    api_key_env = "GROQ_API_KEY"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 default_model: str | None = None) -> None:
        s = get_settings()
        self.api_key = api_key or getattr(s, "groq_api_key", None) or None
        self.base_url = (base_url or getattr(s, "groq_base_url", None)
                         or "https://api.groq.com/openai/v1")
        self.default_model = default_model or "openai/gpt-oss-20b"
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
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str]:
        choice = data["choices"][0]["message"]
        text = choice.get("content") or ""
        usage = data.get("usage", {}) or {}
        return (
            text,
            AIUsage(
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            ),
            data.get("model", self.default_model),
        )

    async def list_models(self) -> list[str]:
        """لیست مدل‌ها از API رسمی (برای تب مدل‌ها؛ cache سمت router)."""
        import httpx

        async with httpx.AsyncClient(timeout=self._default_timeout) as client:
            resp = await client.get(
                f"{self.base_url.rstrip('/')}/models", headers=self._headers()
            )
            resp.raise_for_status()
            data = resp.json()
        return [m.get("id", "") for m in (data.get("data") or []) if m.get("id")]

"""OpenAI-compatible custom Provider (هر شرکت دیگری با base_url).

قرارداد: OpenAI chat/completions (مثل openrouter.py). base_url فقط https و
غیرخصوصی (اعتبارسنجی ضد-SSRF در backend.ai.credentials).
"""
from __future__ import annotations

from typing import Any

from backend.ai.credentials import validate_base_url
from backend.ai.providers.http_base import HTTPProvider
from backend.ai.schemas.types import AIRequest, AIUsage
from backend.core.config import get_settings


class OpenAICompatibleProvider(HTTPProvider):
    name = "openai_compatible"
    api_key_env = ""

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 default_model: str | None = None) -> None:
        s = get_settings()
        self.api_key = api_key or None
        if not base_url:
            raise ValueError("openai_compatible requires base_url")
        self.base_url = validate_base_url(base_url)
        self.default_model = default_model or "default"
        self._default_timeout = float(s.ai_request_timeout_seconds)

    def configured(self) -> bool:
        return bool(self.api_key and self.base_url)

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

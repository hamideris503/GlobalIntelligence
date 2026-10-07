"""Google Gemini Provider (generateContent API)."""
from __future__ import annotations

from typing import Any

from backend.ai.providers.http_base import HTTPProvider
from backend.ai.schemas.types import AIRequest, AIUsage
from backend.core.config import get_settings


class GeminiProvider(HTTPProvider):
    name = "gemini"
    api_key_env = "GEMINI_API_KEY"

    def __init__(self) -> None:
        s = get_settings()
        self.api_key = getattr(s, "gemini_api_key", None) or None
        self.base_url = getattr(
            s, "gemini_base_url", "https://generativelanguage.googleapis.com"
        )
        self.default_model = getattr(s, "gemini_model", "gemini-1.5-flash")

    def _endpoint(self) -> str:
        model = self.default_model
        return (
            f"{self.base_url.rstrip('/')}/v1beta/models/{model}:generateContent"
            f"?key={self.api_key}"
        )

    def _payload(self, request: AIRequest) -> dict[str, Any]:
        # Gemini نقش system را جدا می‌گیرد
        system_parts = [m.content for m in request.messages if m.role == "system"]
        contents = [
            {
                "role": "user" if m.role == "user" else "model",
                "parts": [{"text": m.content}],
            }
            for m in request.messages
            if m.role in ("user", "assistant")
        ]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": request.temperature},
        }
        if request.max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
        return payload

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str]:
        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {}) or {}
        return (
            text,
            AIUsage(
                prompt_tokens=usage.get("promptTokenCount"),
                completion_tokens=usage.get("candidatesTokenCount"),
                total_tokens=usage.get("totalTokenCount"),
            ),
            self.default_model,
        )

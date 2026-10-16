"""Cloudflare Workers AI Provider.

مستندات رسمی: https://developers.cloudflare.com/workers-ai/get-started/rest-api/
- POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{model}
- احراز هویت: Authorization: Bearer {API_TOKEN} + Account ID جدا (فیلد extra).
- پاسخ: {"result": {"response": text}, "success": bool, "errors": [...]}.
- usage توکن از API برنمی‌گردد → برآورد chars/4 با برچسب estimate (مستند، ADR-STEP8).
"""
from __future__ import annotations

from typing import Any

from backend.ai.providers.http_base import HTTPProvider
from backend.ai.schemas.types import AIRequest, AIUsage
from backend.core.config import get_settings


def estimate_tokens(text: str) -> int:
    """برآورد خشن توکن (تخمینی؛ فقط وقتی usage واقعی نیست)."""
    return max(1, len(text) // 4)


class CloudflareProvider(HTTPProvider):
    name = "cloudflare"
    api_key_env = "CLOUDFLARE_API_TOKEN"

    def __init__(self, *, api_key: str | None = None, account_id: str | None = None,
                 default_model: str | None = None) -> None:
        s = get_settings()
        self.api_key = api_key or getattr(s, "cloudflare_api_token", None) or None
        self.account_id = account_id or getattr(s, "cloudflare_account_id", None) or None
        self.default_model = default_model or "@cf/meta/llama-3.1-8b-instruct"
        self._default_timeout = float(s.ai_request_timeout_seconds)

    def configured(self) -> bool:
        return bool(self.api_key and self.account_id)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _endpoint(self, request: AIRequest | None = None) -> str:
        model = self._request_model(request)
        return (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            f"/ai/run/{model}"
        )

    def _payload(self, request: AIRequest) -> dict[str, Any]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        return {"messages": messages}

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str, str | None]:
        if not data.get("success", False):
            errors = data.get("errors") or []
            raise ValueError(f"cloudflare errors: {str(errors)[:200]}")
        result = data.get("result") or {}
        text = result.get("response") or ""
        # usage واقعی از API برنمی‌گردد؛ در generate() با برآورد پر می‌شود.
        # finish reason هم گزارش نمی‌شود → None (جعل نمی‌شود).
        return text, AIUsage(), self.default_model, None

    async def generate(self, request: AIRequest):  # type: ignore[override]
        from backend.ai.schemas.types import AIResponse

        prompt_chars = sum(len(m.content) for m in request.messages)
        resp: AIResponse = await super().generate(request)
        prompt_est = estimate_tokens("".join(m.content for m in request.messages))
        comp_est = estimate_tokens(resp.text)
        resp.usage.prompt_tokens = prompt_est
        resp.usage.completion_tokens = comp_est
        resp.usage.total_tokens = prompt_est + comp_est
        if isinstance(resp.raw, dict):
            resp.raw["token_estimate"] = True
            resp.raw["prompt_chars"] = prompt_chars
        return resp

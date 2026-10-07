"""Provider پایه‌ی مبتنی بر HTTP (OpenAI-compatible و مشابه‌ها)."""
from __future__ import annotations

import time
from typing import Any

import httpx

from backend.ai.providers.base import BaseProvider
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    AIUsage,
    ProviderHealth,
)


class HTTPProvider(BaseProvider):
    """پایه‌ی مشترک Providerهای HTTP. زیرکلاس‌ها فقط endpoint/headers/پارس را می‌دهند."""

    name: str = "http"
    base_url: str = ""
    api_key: str | None = None
    api_key_env: str = ""
    default_model: str = ""

    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _endpoint(self) -> str:
        raise NotImplementedError

    def _payload(self, request: AIRequest) -> dict[str, Any]:
        raise NotImplementedError

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str]:
        """(text, usage, model) را برمی‌گرداند."""
        raise NotImplementedError

    async def generate(self, request: AIRequest) -> AIResponse:
        if not self.configured():
            raise AIError(
                f"provider '{self.name}' is not configured (missing API key)",
                kind=AIErrorKind.auth,
                provider=self.name,
                retryable=False,
            )

        started = time.perf_counter()
        timeout = httpx.Timeout(request.metadata.get("timeout", 60.0))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    self._endpoint(),
                    headers=self._headers(),
                    json=self._payload(request),
                )
        except httpx.TimeoutException as exc:
            raise AIError(str(exc), kind=AIErrorKind.timeout, provider=self.name,
                          retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIError(str(exc), kind=AIErrorKind.connection, provider=self.name,
                          retryable=True) from exc

        if resp.status_code == 429:
            raise AIError("rate limited", kind=AIErrorKind.rate_limit,
                          provider=self.name, retryable=True)
        if resp.status_code in (401, 403):
            raise AIError("auth failed", kind=AIErrorKind.auth,
                          provider=self.name, retryable=False)
        if resp.status_code >= 500:
            raise AIError(f"provider error {resp.status_code}",
                          kind=AIErrorKind.provider_error, provider=self.name,
                          retryable=True)
        if resp.status_code >= 400:
            raise AIError(f"bad request {resp.status_code}: {resp.text[:300]}",
                          kind=AIErrorKind.bad_request, provider=self.name,
                          retryable=False)

        try:
            data = resp.json()
            text, usage, model = self._parse(data)
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"invalid provider output: {exc}",
                          kind=AIErrorKind.invalid_output, provider=self.name,
                          retryable=False) from exc

        latency = (time.perf_counter() - started) * 1000
        return AIResponse(
            text=text,
            provider=self.name,
            model=model or self.default_model,
            usage=usage,
            latency_ms=latency,
            raw=data,
            model_version=model or self.default_model,
            prompt_version=request.metadata.get("prompt_version", "v0"),
        )

    async def health(self) -> ProviderHealth:
        if not self.configured():
            return ProviderHealth(
                provider=self.name, healthy=False,
                detail=f"not configured ({self.api_key_env} missing)",
            )
        return ProviderHealth(provider=self.name, healthy=True, detail="configured")

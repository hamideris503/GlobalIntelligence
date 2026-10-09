"""AI Gateway — لایه‌ی مستقل بین Application و Providerها (بند 10-13).

مسئول: انتخاب Provider/Model، fallback، retry، timeout، logging،
cost/token tracking، model/prompt version tracking.
هیچ Providerی در منطق اصلی hard-code نمی‌شود.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.ai.providers.base import AIProvider
from backend.ai.providers.registry import build_provider
from backend.ai.routing.router import Route, resolve_route
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    ProviderHealth,
)
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class AIGateway:
    """Gateway یکپارچه برای فراخوانی مدل‌ها با fallback/retry."""

    def __init__(self, routes: dict[str, Route] | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._routes = routes
        self._providers: dict[str, AIProvider] = {}
        self._max_retries = settings.ai_max_retries

    # --- provider cache ---
    def _provider(self, name: str) -> AIProvider:
        if name not in self._providers:
            self._providers[name] = build_provider(name)
        return self._providers[name]

    # --- route resolution ---
    def _route(self, request: AIRequest) -> Route:
        if self._routes is not None:
            role = request.role or request.task
            if role and role in self._routes:
                return self._routes[role]
        return resolve_route(request.role, request.task)

    def set_routes(self, routes: dict[str, Route]) -> None:
        """جایگزینی زنجیره‌ها در runtime (Adaptive AI Router، Phase 37)."""
        self._routes = dict(routes)

    async def _call_with_retry(
        self, provider: AIProvider, request: AIRequest
    ) -> AIResponse:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await provider.generate(request)
            except AIError as exc:
                last_exc = exc
                if not exc.retryable:
                    raise
                if attempt < self._max_retries:
                    backoff = 0.5 * (2 ** attempt)
                    logger.warning(
                        "provider %s retryable error (%s); retrying in %.1fs",
                        provider.name, exc.kind, backoff,
                    )
                    await asyncio.sleep(backoff)
        assert last_exc is not None
        raise last_exc

    async def generate(self, request: AIRequest) -> AIResponse:
        """تولید پاسخ؛ در صورت شکست Provider، به Provider بعدی fallback می‌کند.

        رفتار زنجیره:
        - اگر MOCK_MODE فعال باشد → فقط mock (توسعه/آفلاین).
        - در غیر این صورت → زنجیره‌ی نقش، سپس AI_DEFAULT_PROVIDER.
          mock هرگز در production صدا زده نمی‌شود.
        """
        route = self._route(request)
        chain = list(route.providers)

        if not chain:
            default = self._settings.ai_default_provider
            chain = [default] if default else []

        if self._settings.mock_mode:
            chain = ["mock"]
        else:
            # حذف mock در production
            chain = [p for p in chain if p != "mock"]
            if not chain:
                raise AIError(
                    "no real provider configured (MOCK_MODE=false and no provider)",
                    kind=AIErrorKind.auth,
                    retryable=False,
                )

        errors: list[str] = []
        for name in chain:
            provider = self._provider(name)
            try:
                started = time.perf_counter()
                response = await self._call_with_retry(provider, request)
                response.is_mock = name == "mock"
                logger.info(
                    "ai.generate | role=%s task=%s provider=%s model=%s mock=%s latency_ms=%.1f",
                    request.role, request.task, response.provider, response.model,
                    response.is_mock,
                    response.latency_ms or ((time.perf_counter() - started) * 1000),
                )
                return response
            except AIError as exc:
                errors.append(f"{name}:{exc.kind}")
                logger.warning("provider %s failed (%s): %s", name, exc.kind, exc)
                continue

        raise AIError(
            f"all providers failed: {'; '.join(errors)}",
            kind=AIErrorKind.provider_error,
            retryable=False,
        )

    async def structured_generate(
        self, request: AIRequest, schema: dict[str, Any]
    ) -> AIResponse:
        req = AIRequest(
            messages=request.messages,
            task=request.task,
            role=request.role,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            json_schema=schema,
            metadata=request.metadata,
        )
        return await self.generate(req)

    async def provider_health(self) -> list[ProviderHealth]:
        from backend.ai.providers.registry import available_providers

        results: list[ProviderHealth] = []
        for name in available_providers():
            try:
                results.append(await self._provider(name).health())
            except Exception as exc:  # noqa: BLE001
                results.append(ProviderHealth(provider=name, healthy=False, detail=str(exc)))
        return results


_gateway: AIGateway | None = None


def get_gateway() -> AIGateway:
    """نمونه‌ی singleton از Gateway."""
    global _gateway
    if _gateway is None:
        _gateway = AIGateway()
    return _gateway

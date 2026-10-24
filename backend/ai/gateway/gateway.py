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
from backend.ai.providers.registry import build_provider_with_store
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

# --- قاعده‌ی انتخاب خطای نهایی زنجیره (ثابت، مستند، مستقل از ترتیب شکست) ---
# وقتی هیچ providerی پاسخ نداد، علت گزارش‌شده باید همان چیزی باشد که واقعاً
# مانع شد، نه یک «provider_error» عمومی. اولویت (کم‌هزینه‌ترین راه بازگشت
# برای فراخوان اول):
#   1. bad_request     → درخواست از سمت provider رد شد؛ بدون اصلاح درخواست، retry بی‌فایده
#   2. estimate        → سقف خروجی نامعلوم (پیکربندی)
#   3. auth            → اعتبارنامه/پیکربندی provider
#   4. rate_limit      → موقت، با Retry-After واقعی provider («بعداً دوباره تلاش کن»)
#   5. timeout         → 504
#   6. connection      → 502
#   7. invalid_output  → پاسخ غیرقابل‌استفاده‌ی provider (502)
#   8. provider_error  → شکست عمومی provider (502)
#   9. quota_exhausted → تنها وقتی هیچ علت فنی دیگری نیست: سهمیه‌ی رایگان امروز
#      تمام است → free_unavailable (503). فقط همین یک حالت free_unavailable می‌سازد.
# provider/retry_after از نخستین شکست هم‌نوع در ترتیب زنجیره می‌آید؛ نوع خطا
# وابسته به ترتیب شکست نیست. خطاهای سیاست (not_allowed) هرگز به این‌جا نمی‌رسند
# چون پیش از HTTP و بیرون از حلقه fallback raise می‌شوند.
_CHAIN_FAILURE_ORDER: tuple[AIErrorKind, ...] = (
    AIErrorKind.bad_request,
    AIErrorKind.estimate,
    AIErrorKind.auth,
    AIErrorKind.rate_limit,
    AIErrorKind.timeout,
    AIErrorKind.connection,
    AIErrorKind.invalid_output,
    AIErrorKind.provider_error,
    AIErrorKind.quota_exhausted,
)


def _chain_failure(failures: list[AIError]) -> AIError:
    """خطای نهایی زنجیره بر اساس `_CHAIN_FAILURE_ORDER`."""
    summary = "; ".join(f"{f.provider or 'unknown'}:{f.kind.value}" for f in failures)
    for kind in _CHAIN_FAILURE_ORDER:
        chosen = next((f for f in failures if f.kind == kind), None)
        if chosen is None:
            continue
        if kind == AIErrorKind.quota_exhausted:
            return AIError(
                f"no usable free provider quota: {summary}",
                kind=AIErrorKind.free_unavailable,
                provider=chosen.provider, retryable=False)
        return AIError(
            f"all providers failed [{kind.value}]: {summary}",
            kind=kind, provider=chosen.provider,
            retryable=chosen.retryable, retry_after=chosen.retry_after)
    return AIError(f"all providers failed: {summary}",
                   kind=AIErrorKind.provider_error, retryable=False)


class AIGateway:
    """Gateway یکپارچه برای فراخوانی مدل‌ها با fallback/retry."""

    def __init__(self, routes: dict[str, Route] | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._routes = routes
        self._providers: dict[str, AIProvider] = {}
        self._max_retries = settings.ai_max_retries
        from backend.ai import credentials_store as store

        self._cred_version = store.get_version()

    # --- provider cache ---
    def _provider(self, name: str) -> AIProvider:
        # Step 8: اگر تنظیمات عوض شده، کش را دور بریز (بدون ری‌استارت)
        from backend.ai import credentials_store as store

        if store.get_version() != self._cred_version:
            self._providers = {}
            self._cred_version = store.get_version()
        if name not in self._providers:
            self._providers[name] = build_provider_with_store(name)
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
        self, provider: AIProvider, request: AIRequest,
        budget_key: str | None = None,
    ) -> AIResponse:
        from backend.ai import budget as _budget

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            key = f"{budget_key}:{provider.name}:{attempt}" if budget_key else None
            if key is not None:
                cap = _budget.resolve_output_cap(request)
                if cap is None:
                    raise AIError(
                        "ai budget estimate unavailable",
                        kind=AIErrorKind.estimate,
                        provider=provider.name, retryable=False)
                est_in = _budget.estimate_input_tokens(request)
                allowed = _budget.reserve(
                    day=_budget.utc_day(), task=request.task,
                    provider=provider.name,
                    model=getattr(provider, "default_model", None),
                    request_key=key, estimate=est_in + cap,
                    input_est=est_in, output_cap=cap,
                    budget=_budget.budget_limit() or 0)
                if not allowed:
                    raise AIError(
                        "ai budget exceeded", kind=AIErrorKind.budget,
                        provider=provider.name, retryable=False)
            try:
                resp = await provider.generate(request)
            except AIError as exc:
                if key is not None:
                    # نامعلوم/ناموفق محافظه‌کارانه روی رزرو می‌ماند (صفر فرض نشود)
                    _budget.settle(key, actual=None, status="failed")
                last_exc = exc
                if not exc.retryable:
                    raise
                if attempt < self._max_retries:
                    backoff = 0.5 * (2 ** attempt)
                    if exc.retry_after and exc.retry_after > 0:
                        backoff = min(exc.retry_after, 60.0)
                    logger.warning(
                        "provider %s retryable error (%s); retrying in %.1fs",
                        provider.name, exc.kind, backoff,
                    )
                    await asyncio.sleep(backoff)
                continue
            if key is not None:
                total = resp.usage.total_tokens if resp.usage else None
                _budget.settle(
                    key, actual=total,
                    status="settled" if total is not None else "unknown")
            return resp
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

        from backend.ai import credentials_store as _store
        from backend.core.mock_mode import effective_mock_mode

        effective_mock = effective_mock_mode()
        effective_default = _store.effective_default_provider()

        if not chain:
            chain = [effective_default] if effective_default else []

        if effective_mock:
            chain = ["mock"]
        else:
            # حذف mock در production
            chain = [p for p in chain if p != "mock"]
            # Step 8: force_provider از نگاشت agent (اولویت) + fallback به زنجیره
            forced = request.metadata.get("force_provider")
            if isinstance(forced, str) and forced and forced != "mock":
                chain = [forced] + [p for p in chain if p != forced]
            # The screening fallback must not reach a Kev/Laya endpoint
            # directly: those runtimes are owned by LocalRuntimeSupervisor
            # and are only invoked by the local-screening orchestrator.
            if request.metadata.get("exclude_local_providers"):
                chain = [p for p in chain if p not in ("kev", "laya")]
            if not chain:
                raise AIError(
                    "no real provider configured (MOCK_MODE=false and no provider)",
                    kind=AIErrorKind.auth,
                    retryable=False,
                )

        failures: list[AIError] = []
        import uuid as _uuid

        from backend.ai import budget as _budget
        from backend.ai import free_policy as _policy

        use_budget = _budget.is_enabled()
        request_key = f"{request.task or 'task'}:{_uuid.uuid4().hex[:12]}"
        for name in chain:
            # Free-Only: هر نامزد پیش از build و هر مدل پیش از HTTP بررسی
            # می‌شود؛ نامجاز → توقف فوری، بدون fallback به بعدی.
            # نام نمایشی DB ابتدا به kind واقعی adapter resolve می‌شود.
            try:
                provider = self._provider(name)
            except ValueError as exc:
                raise AIError(
                    f"provider not allowed: {name}",
                    kind=AIErrorKind.provider_not_allowed,
                    provider=name, retryable=False) from exc
            kind = getattr(provider, "name", None) or name
            _policy.check_provider(kind, mock_mode=effective_mock)
            _policy.check_model(
                kind,
                request.metadata.get("model") or getattr(provider, "default_model", None),
                mock_mode=effective_mock)
            try:
                started = time.perf_counter()
                response = await self._call_with_retry(
                    provider, request,
                    budget_key=(request_key if use_budget
                                and not getattr(provider, "is_local", False) else None))
                response.is_mock = name == "mock"
                logger.info(
                    "ai.generate | role=%s task=%s provider=%s model=%s mock=%s latency_ms=%.1f",
                    request.role, request.task, response.provider, response.model,
                    response.is_mock,
                    response.latency_ms or ((time.perf_counter() - started) * 1000),
                )
                return response
            except AIError as exc:
                if exc.kind == AIErrorKind.budget:
                    raise
                # خودِ خطا نگه داشته می‌شود تا kind/retryable/retry_after/provider
                # تا لایه‌ی API حفظ شوند (انتخاب نهایی در _chain_failure).
                failures.append(exc)
                logger.warning("provider %s failed (%s): %s", name, exc.kind, exc)
                continue

        raise _chain_failure(failures)

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

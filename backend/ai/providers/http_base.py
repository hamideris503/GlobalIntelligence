"""Provider پایه‌ی مبتنی بر HTTP (OpenAI-compatible و مشابه‌ها)."""
from __future__ import annotations

import json
import time
from typing import Any

import httpcore
import httpx
from domains.news.source_verify import (
    _pin_pool,
    pinned_ip,
    target_allowed,
)

from backend.ai.providers.base import BaseProvider
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    AIUsage,
    ProviderHealth,
)

_DAILY_QUOTA_MARKERS = frozenset({
    "quota_exceeded", "quota exceeded", "daily quota", "day quota",
    "requests per day", "per day", "free_model_daily", "rpd",
})


def _looks_like_daily_quota(body: str) -> bool:
    """نشانه‌ی اتمام سهمیه‌ی روزانه در بدنه‌ی خطا (نه محدودیت موقتی)."""
    lowered = (body or "").lower()
    return any(m in lowered for m in _DAILY_QUOTA_MARKERS)


def _parse_retry_after(headers) -> float | None:
    """ثانیه‌های Retry-After هدر؛ نامعتبر/منفی/غایب → None."""
    try:
        value = float(headers.get("retry-after", ""))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # سقف بدنه‌ی پاسخ (محافظت حافظه)
DISCOVER_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # سقف فهرست مدل‌ها (سبک)


async def _read_limited_body(resp, provider_name: str) -> bytes:
    """خوانش جریانی بدنه با سقف؛ بیش از سقف → خطای کنترل‌شده."""
    total = 0
    chunks = []
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise AIError("response too large", kind=AIErrorKind.invalid_output,
                          provider=provider_name, retryable=False)
        chunks.append(chunk)
    return b"".join(chunks)


def read_limited_body_sync(resp, limit: int) -> bytes:
    """نسخه‌ی همگام خوانش محدود بدنه (endpointهای مدیریتی)؛ بیش از سقف → ValueError."""
    total = 0
    chunks = []
    for chunk in resp.iter_bytes():
        total += len(chunk)
        if total > limit:
            raise ValueError(f"response exceeds {limit} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


class _AIPinnedAsyncBackend(httpcore.AsyncNetworkBackend):
    """Backend اتصال AI: pin به IP تأییدشده، بدون تغییر SNI/Host/TLS."""

    def __init__(self, inner: httpcore.AsyncNetworkBackend, *,
                 allow_private: bool = False) -> None:
        self._inner = inner
        self._allow_private = allow_private

    async def connect_tcp(self, host: str, port: int, timeout: float | None = None,
                          local_address: str | None = None,
                          socket_options=None) -> httpcore.AsyncNetworkStream:  # noqa: ANN001
        target = pinned_ip(host, allow_private=self._allow_private)
        return await self._inner.connect_tcp(
            target, port, timeout=timeout, local_address=local_address,
            socket_options=socket_options)

    async def connect_unix_socket(self, path: str, timeout: float | None = None,
                                  socket_options=None) -> httpcore.AsyncNetworkStream:  # noqa: ANN001
        return await self._inner.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class GuardedTransport(httpx.AsyncHTTPTransport):
    """Transport AI: اعتبارسنجی مقصد در مسیر ارسال + pin اتصال به IP تأییدشده.

    - پیش از هر درخواست، `target_allowed` میزبان را بررسی می‌کند (scheme، userinfo،
      DNS، IPهای ممنوع). رد ⇒ _BlockedDestinationError قبل از هر بایت.
    - اتصال واقعی به همان IP تأییدشده pin می‌شود (نه resolve دوباره).
    - درخواست بازنویسی نمی‌شود: SNI، Host header و اعتبارسنجی TLS استاندارد HTTPX.
    - proxy/uds/positional args پشتیبانی نمی‌شوند: مسیر pin را دور می‌زنند.
    - trust_env=False در AsyncClient: متغیرهای محیطی پروکسی/CA نادیده گرفته می‌شوند.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        if args or kwargs.get("proxy") is not None or kwargs.get("uds") is not None:
            raise ValueError("proxy/uds/positional args unsupported: would bypass IP pinning")
        super().__init__(**kwargs)  # type: ignore[arg-type]
        _pin_pool(self._pool, _AIPinnedAsyncBackend)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        ok, reason = target_allowed(str(request.url))
        if not ok:
            raise _BlockedDestinationError(
                f"blocked non-public AI destination: {reason}")
        return await super().handle_async_request(request)


class _BlockedDestinationError(Exception):
    """مقصد در سطح اتصال رد شد؛ هیچ بایت‌ای (از جمله کلید) ارسال نشده است."""


class HTTPProvider(BaseProvider):
    """پایه‌ی مشترک Providerهای HTTP. زیرکلاس‌ها فقط endpoint/headers/پارس را می‌دهند."""

    name: str = "http"
    base_url: str = ""
    api_key: str | None = None
    api_key_env: str = ""
    default_model: str = ""
    _default_timeout: float = 60.0

    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _request_model(self, request: AIRequest | None) -> str:
        """مدل درخواستی از metadata (override سازگار با عقب) یا پیش‌فرض Provider."""
        if request is not None:
            override = request.metadata.get("model")
            if isinstance(override, str) and override.strip():
                return override.strip()
        return self.default_model

    def _endpoint(self, request: AIRequest | None = None) -> str:
        raise NotImplementedError

    def _payload(self, request: AIRequest) -> dict[str, Any]:
        raise NotImplementedError

    def _parse(self, data: dict[str, Any]) -> tuple[str, AIUsage, str, str | None]:
        """(text, usage, model, finish_reason) را برمی‌گرداند."""
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
        # timeout از metadata درخواست یا تنظیمات برنامه (نه ۶۰ ثانیه‌ی ثابت)
        default_timeout = float(
            request.metadata.get("timeout")
            or getattr(self, "_default_timeout", 60.0)
        )
        timeout = httpx.Timeout(default_timeout)
        try:
            # redirect دنبال نمی‌شود (پین به endpoint اعتبارسنجی‌شده)؛ بدنه
            # با سقف خوانده می‌شود تا پاسخ غول‌پیکر حافظه را پر نکند.
            # transport مقصد را در مسیر واقعی ارسال دوباره بررسی می‌کند.
            # trust_env=False یعنی متغیرهای محیطی پروکسی و CA سفارشی روی
            # اتصال اثر ندارند (پروکسی env نمی‌تواند ترافیک/کلید را منحرف
            # کند و CA مهاجم نمی‌تواند MITM بی‌صدا بسازد)؛ در استقرار عادی
            # بدون پروکسی هیچ تغییری در رفتار ایجاد نمی‌شود.
            async with httpx.AsyncClient(timeout=timeout,
                                         follow_redirects=False,
                                         transport=GuardedTransport(
                                             trust_env=False)) as client:
                async with client.stream(
                    "POST",
                    self._endpoint(request),
                    headers=self._headers(),
                    json=self._payload(request),
                ) as resp:
                    status = resp.status_code
                    headers = resp.headers
                    body = await _read_limited_body(resp, self.name)
        except httpx.TimeoutException as exc:
            raise AIError(str(exc), kind=AIErrorKind.timeout, provider=self.name,
                          retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIError(str(exc), kind=AIErrorKind.connection, provider=self.name,
                          retryable=True) from exc

        text = body.decode("utf-8", errors="replace")
        if status == 429:
            if _looks_like_daily_quota(text):
                raise AIError("daily quota exhausted", kind=AIErrorKind.quota_exhausted,
                              provider=self.name, retryable=False)
            raise AIError("rate limited", kind=AIErrorKind.rate_limit,
                          provider=self.name, retryable=True,
                          retry_after=_parse_retry_after(headers))
        if status in (401, 403):
            raise AIError("auth failed", kind=AIErrorKind.auth,
                          provider=self.name, retryable=False)
        if status >= 500:
            raise AIError(f"provider error {status}",
                          kind=AIErrorKind.provider_error, provider=self.name,
                          retryable=True)
        if status >= 400:
            # متن بدنه عمداً در خطا نمی‌آید (ممکن است محتوای بازتابی باشد).
            raise AIError(f"bad request {status}",
                          kind=AIErrorKind.bad_request, provider=self.name,
                          retryable=False)

        try:
            data = json.loads(body)
            text, usage, model, finish_reason = self._parse(data)
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"invalid provider output: {exc}",
                          kind=AIErrorKind.invalid_output, provider=self.name,
                          retryable=False) from exc

        latency = (time.perf_counter() - started) * 1000
        resolved_model = model or self._request_model(request)
        return AIResponse(
            text=text,
            provider=self.name,
            model=resolved_model,
            usage=usage,
            latency_ms=latency,
            finish_reason=finish_reason,
            raw=data,
            model_version=resolved_model,
            prompt_version=request.metadata.get("prompt_version", "v0"),
        )

    async def health(self) -> ProviderHealth:
        if not self.configured():
            return ProviderHealth(
                provider=self.name, healthy=False,
                detail=f"not configured ({self.api_key_env} missing)",
            )
        return ProviderHealth(provider=self.name, healthy=True, detail="configured")

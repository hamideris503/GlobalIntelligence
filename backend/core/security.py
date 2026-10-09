"""Security middlewares (Phase 44).

- `SecurityHeadersMiddleware`: هدرهای امنیتی پایه روی همه‌ی پاسخ‌ها.
- `RateLimitMiddleware`: محدودیت نرخ پنجره‌ی لغزان درون‌حافظه‌ای (v1:
  تک‌فرایندی؛ production چندکارگری به Redis نیاز دارد — فازهای ops).

هر دو بدون وابستگی خارجی و قابل آزمون مستقل‌اند.
"""
from __future__ import annotations

import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """افزودن هدرهای امنیتی به هر پاسخ."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """محدودیت نرخ ساده: N درخواست در هر ۶۰ ثانیه برای هر IP.

    مسیرهای exempt (مثل health) محدود نمی‌شوند. پاسخ 429 به‌صورت JSON.
    """

    def __init__(
        self,
        app,
        *,
        per_minute: int = 600,
        exempt_paths: tuple[str, ...] = ("/health", "/health/db", "/"),
    ) -> None:
        super().__init__(app)
        self.per_minute = max(1, per_minute)
        self.exempt_paths = exempt_paths
        self._hits: dict[str, deque[float]] = {}

    def _client_key(self, request: Request) -> str:
        if request.client is not None:
            return request.client.host
        return "unknown"

    def _allowed(self, key: str, now: float) -> bool:
        window_start = now - 60.0
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        if len(self._hits) > 10000:
            # پاک‌سازی دوره‌ای حافظه (قدیمی‌ترین‌ها)
            for old_key in list(self._hits)[:1000]:
                old = self._hits[old_key]
                while old and old[0] <= window_start:
                    old.popleft()
                if not old:
                    del self._hits[old_key]
        return True

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        if not self._allowed(self._client_key(request), time.monotonic()):
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded; retry in a minute"},
            )
        return await call_next(request)


__all__ = [
    "SECURITY_HEADERS",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
]

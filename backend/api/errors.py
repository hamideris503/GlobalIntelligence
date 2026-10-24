"""نگاشت خطاهای ساختاریافته‌ی AI Gateway به پاسخ HTTP (تک‌منبع).

قبل از این، هر `AIError` که از endpoint بیرون می‌زد به 500 خام تبدیل می‌شد.
اینجا هر kind به وضعیت متناسب با معنای واقعی‌اش نگاشت می‌شود:

- 403 `provider_not_allowed` / `model_not_allowed`: درخواست خارج از فهرست
  Free-Only (شامل مدل مسدود یا تأیید منقضی). دائمی: هیچ‌وقت retryable نیست و
  هیچ‌وقت `Retry-After` نمی‌گیرد.
- 400 `bad_request` / 422 `estimate`: خود درخواست قابل سرو نیست.
- 429 `rate_limit` / `quota_exhausted` / `budget`: سهمیه/سقف مصرف. تفکیک‌شان با
  `kind`، `retryable` و `Retry-After` است: هدر و فیلد `retry_after` فقط برای
  `rate_limit` و فقط با مقدار واقعیِ برگشته از provider می‌آید (ساختگی نه).
  سقف‌های روزانه‌ی quota/budget زمان ریستشان را این لایه نمی‌داند → بدون هدر.
- 502 `auth`/`connection`/`provider_error`/`invalid_output`، 504 `timeout`:
  شکست provider یا سمت Gateway.
- 503 `free_unavailable`: همین حالا هیچ provider رایگانی قابل استفاده نیست.
- 500 `unknown`: خطای پیش‌بینی‌نشده.

پیام‌ها از `SAFE_MESSAGES` می‌آید، نه از `str(exc)`: بدنه‌ی provider، کلید،
stack trace و جزئیات اتصال هرگز به کلاینت نمی‌رسد (متن خام فقط لاگ می‌شود).
قالب پاسخ FastAPI (`{"detail": ...}`) حفظ شده تا کلاینت‌های فعلی، از جمله
`apps/web/src/api.ts`، بدون تغییر کار کنند؛ فیلدهای ساختاریافته اضافه‌اند.
"""
from __future__ import annotations

import math
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.ai.schemas.types import AIError, AIErrorKind
from backend.core.logging import get_logger

logger = get_logger(__name__)

# پیام‌های امن برای نمایش به کلاینت (endpoint تست اتصال هم همین‌ها را می‌دهد).
SAFE_MESSAGES: dict[AIErrorKind, str] = {
    AIErrorKind.auth: "authentication failed (check the API key)",
    AIErrorKind.rate_limit: "rate limited; retry later",
    AIErrorKind.quota_exhausted: "free daily quota exhausted; try again later",
    AIErrorKind.free_unavailable: "no usable free provider available",
    AIErrorKind.provider_not_allowed: "provider is not allowed by free-only policy",
    AIErrorKind.model_not_allowed: "model is not verified for free use",
    AIErrorKind.estimate: "output cap unknown; cannot estimate",
    AIErrorKind.budget: "token budget exhausted",
    AIErrorKind.timeout: "connection timed out",
    AIErrorKind.connection: "cannot reach the provider",
    AIErrorKind.bad_request: "request rejected (check model name)",
    AIErrorKind.provider_error: "provider error; retry later",
    AIErrorKind.invalid_output: "provider returned an unusable response",
    AIErrorKind.unknown: "unexpected ai error",
}

# fallback برای exceptionهای غیر-AI (مثلاً در endpoint تست اتصال)
DEFAULT_MESSAGE = SAFE_MESSAGES[AIErrorKind.provider_error]

AI_ERROR_STATUS: dict[AIErrorKind, int] = {
    AIErrorKind.provider_not_allowed: 403,
    AIErrorKind.model_not_allowed: 403,
    AIErrorKind.bad_request: 400,
    AIErrorKind.estimate: 422,
    AIErrorKind.rate_limit: 429,
    AIErrorKind.quota_exhausted: 429,
    AIErrorKind.budget: 429,
    AIErrorKind.free_unavailable: 503,
    AIErrorKind.auth: 502,
    AIErrorKind.connection: 502,
    AIErrorKind.provider_error: 502,
    AIErrorKind.invalid_output: 502,
    AIErrorKind.timeout: 504,
    AIErrorKind.unknown: 500,
}


def ai_error_response(exc: AIError) -> JSONResponse:
    """پاسخ ساختاریافته‌ی یک AIError (بدنه‌ی امن، Retry-After صادقانه)."""
    kind = exc.kind if isinstance(exc.kind, AIErrorKind) else AIErrorKind.unknown
    status = AI_ERROR_STATUS[kind]
    body: dict[str, Any] = {
        "detail": SAFE_MESSAGES[kind],
        "kind": kind.value,
        "retryable": bool(exc.retryable),
    }
    if exc.provider:
        body["provider"] = exc.provider
    headers: dict[str, str] = {}
    # فقط خطای موقتِ نرخ با مقدار واقعی provider؛ هدر برای fetch در مرورگر
    # قابل خواندن نیست (CORS آن را expose نکرده)، پس در بدنه هم می‌آید.
    if (kind == AIErrorKind.rate_limit and exc.retryable
            and exc.retry_after and exc.retry_after > 0):
        seconds = str(int(math.ceil(exc.retry_after)))
        headers["Retry-After"] = seconds
        body["retry_after"] = int(seconds)
    return JSONResponse(status_code=status, content=body, headers=headers)


async def ai_error_handler(request: Request, exc: AIError) -> JSONResponse:
    """فقط برای AIError ثبت می‌شود؛ بقیه‌ی exceptionها رفتار پیش‌فرض را دارند."""
    response = ai_error_response(exc)
    logger.warning(
        "ai error | path=%s kind=%s provider=%s status=%d",
        request.url.path, exc.kind, exc.provider, response.status_code,
    )
    return response

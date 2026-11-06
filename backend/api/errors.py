"""قرارداد یکنواخت خطای API (مرحله ۲) + نگاشت خطاهای AI Gateway (تک‌منبع).

هر پاسخ خطا، هم‌زمان دو شکل دارد:

.. code-block:: json

    {"error": {"code": "FORBIDDEN", "message": "...", "details": {}, "request_id": "..."},
     "detail": "..."}

`detail` قدیمی حفظ می‌شود تا n8n و کلاینت‌های موجود نشکنند؛ `error` شکل
قابل‌اعتماد و ماشین‌خوان برای UI است (`error.code`, `error.message`,
`error.details.fields` در ۴۲۲, `X-Request-ID`).

نگاشت پیش‌فرض status→code در `STATUS_CODES` است؛ هرجا معنای دقیق‌تری هست
(مثلاً کلید API نامعتبر) از `ApiError` با `code` صریح استفاده می‌شود.

نگاشت خطاهای ساختاریافته‌ی AI Gateway:

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
"""
from __future__ import annotations

import math
import re
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.ai.schemas.types import AIError, AIErrorKind
from backend.core.logging import get_logger, request_id_var

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
# فقط شناسه‌های ساده پذیرفته می‌شوند (کاراکتر کنترلی/هدر تزریقی نه).
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
INTERNAL_MESSAGE = "internal server error"
DB_UNAVAILABLE_MESSAGE = "database unavailable"

STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL",
    502: "UPSTREAM_ERROR",
    503: "DB_UNAVAILABLE",
    504: "UPSTREAM_TIMEOUT",
}


class ApiError(StarletteHTTPException):
    """HTTPException با code/details صریح؛ هندلر پیش‌فرض آن را به پاکت تبدیل می‌کند."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.details = details or {}


def get_request_id(request: Request | None) -> str:
    if request is not None:
        value = getattr(request.state, "request_id", None)
        if value:
            return str(value)
    return request_id_var.get()


def error_body(
    code: str,
    message: str,
    *,
    request_id: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """بدنه‌ی یکنواخت؛ `detail` قدیمی هم برای سازگاری هست."""
    return {
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        },
    }


class RequestIDMiddleware(BaseHTTPMiddleware):
    """`X-Request-ID` ورودی را می‌پذیرد یا می‌سازد و در پاسخ/لاگ می‌گذارد."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


# --- handlers ---------------------------------------------------------------

def _json(
    status_code: int,
    body: dict[str, Any],
    request_id: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """پاسخ JSON با `X-Request-ID` (هندلرها بیرون از میان‌افزار هم اجرا می‌شوند)."""
    merged = dict(headers or {})
    if request_id:
        merged.setdefault(REQUEST_ID_HEADER, request_id)
    return JSONResponse(status_code=status_code, content=body, headers=merged)

async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = getattr(exc, "code", None) or STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    detail = exc.detail
    message = detail if isinstance(detail, str) else "request failed"
    details = dict(getattr(exc, "details", None) or {})
    if not isinstance(detail, str):
        details.setdefault("detail", jsonable_encoder(detail))
    headers = dict(exc.headers or {})
    if exc.status_code >= 500:
        logger.error(
            "http error | path=%s status=%d code=%s", request.url.path, exc.status_code, code
        )
    return _json(
        exc.status_code,
        error_body(code, message, request_id=get_request_id(request), details=details),
        get_request_id(request),
        headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = jsonable_encoder(exc.errors())
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body") or "body"
        fields.setdefault(loc, str(err.get("msg", "invalid")))
    body = error_body(
        "VALIDATION_ERROR",
        "request validation failed",
        request_id=get_request_id(request),
        details={"fields": fields},
    )
    body["detail"] = errors  # همان شکل قبلی FastAPI
    return _json(422, body, get_request_id(request))


async def db_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    logger.error(
        "db unavailable | path=%s rid=%s",
        request.url.path,
        get_request_id(request),
        exc_info=exc,
    )
    return _json(
        503,
        error_body(
            "DB_UNAVAILABLE",
            DB_UNAVAILABLE_MESSAGE,
            request_id=get_request_id(request),
        ),
        get_request_id(request),
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # متن/stacktrace فقط در لاگ می‌ماند؛ کلاینت پیام ثابت می‌گیرد.
    logger.exception(
        "unhandled error | path=%s rid=%s", request.url.path, get_request_id(request)
    )
    return _json(
        500,
        error_body("INTERNAL", INTERNAL_MESSAGE, request_id=get_request_id(request)),
        get_request_id(request),
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(DBAPIError, db_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)


# --- AI Gateway errors ------------------------------------------------------

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


def ai_error_response(exc: AIError, request_id: str = "") -> JSONResponse:
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
    details = {k: body[k] for k in ("kind", "retryable", "provider", "retry_after") if k in body}
    body["request_id"] = request_id
    body["error"] = {
        "code": f"AI_{kind.value.upper()}",
        "message": SAFE_MESSAGES[kind],
        "details": details,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status, content=body, headers=headers)


async def ai_error_handler(request: Request, exc: AIError) -> JSONResponse:
    """فقط برای AIError ثبت می‌شود؛ بقیه‌ی exceptionها هندلرهای عمومی دارند."""
    request_id = get_request_id(request)
    response = ai_error_response(exc, request_id=request_id)
    if request_id:
        response.headers.setdefault(REQUEST_ID_HEADER, request_id)
    logger.warning(
        "ai error | path=%s kind=%s provider=%s status=%d rid=%s",
        request.url.path, exc.kind, exc.provider, response.status_code, request_id,
    )
    return response

"""قرارداد خطای لایه‌ی API (`backend/api/errors.py`) — آزمون خالص نگاشت.

FastAPI هر `AIError` را 500 خام می‌کرد. حالا نگاشت در یک جا است و این‌جا
وضعیت هر kind، معنای retry و عدم نشت پیام خام بررسی می‌شود. رفتار HTTP واقعی
روی `/api/ai/chat` در `tests/test_fullstack_integration.py` تست می‌شود.
"""
from __future__ import annotations

import json

import pytest

from backend.ai.schemas.types import AIError, AIErrorKind
from backend.api.errors import (
    AI_ERROR_STATUS,
    SAFE_MESSAGES,
    ai_error_handler,
    ai_error_response,
)
from backend.main import app

ALLOWED_STATUSES = {400, 403, 422, 429, 500, 502, 503, 504}


def _res(kind: AIErrorKind, **kwargs) -> tuple[int, dict, dict]:
    response = ai_error_response(AIError("raw internal message", kind=kind, **kwargs))
    return (
        response.status_code,
        json.loads(response.body),
        {k.lower(): v for k, v in response.headers.items()},
    )


def test_every_kind_has_a_status_and_a_safe_message() -> None:
    assert set(AI_ERROR_STATUS) == set(AIErrorKind) == set(SAFE_MESSAGES)
    assert set(AI_ERROR_STATUS.values()) <= ALLOWED_STATUSES
    assert len(set(AI_ERROR_STATUS.values())) > 1  # یک status ثابت برای همه نیست


def test_policy_rejections_are_403_and_never_retryable() -> None:
    for kind in (AIErrorKind.provider_not_allowed, AIErrorKind.model_not_allowed):
        status, body, headers = _res(kind, provider="groq")
        assert status == 403  # نه 500
        assert (body["kind"], body["retryable"]) == (kind.value, False)
        assert body["detail"] == SAFE_MESSAGES[kind] and body["provider"] == "groq"
        assert "retry-after" not in headers and "retry_after" not in body
    # دائمی: حتی اگر (به‌اشتباه) مقدار retry داشته باشد، پیشنهاد retry نمی‌شود
    status, body, headers = _res(AIErrorKind.model_not_allowed, retryable=True,
                                 retry_after=60)
    assert (status, "retry-after" not in headers, "retry_after" not in body) == (
        403, True, True)


@pytest.mark.parametrize(("kind", "status"), [
    (AIErrorKind.bad_request, 400),
    (AIErrorKind.estimate, 422),
    (AIErrorKind.rate_limit, 429),
    (AIErrorKind.quota_exhausted, 429),
    (AIErrorKind.budget, 429),
    (AIErrorKind.auth, 502),
    (AIErrorKind.connection, 502),
    (AIErrorKind.provider_error, 502),
    (AIErrorKind.invalid_output, 502),
    (AIErrorKind.free_unavailable, 503),
    (AIErrorKind.timeout, 504),
    (AIErrorKind.unknown, 500),
])
def test_status_per_kind(kind: AIErrorKind, status: int) -> None:
    got, body, _ = _res(kind)
    assert got == status
    assert body["kind"] == kind.value


def test_retry_after_only_for_a_real_retryable_rate_limit() -> None:
    # مقدار واقعی provider → هدر و فیلد بدنه (برای مرورگر که هدر را نمی‌خواند)
    status, body, headers = _res(AIErrorKind.rate_limit, retryable=True, retry_after=30)
    assert (status, headers["retry-after"], body["retry_after"]) == (429, "30", 30)
    # کسری → گرد به بالا (هدر باید عدد صحیح باشد)، بدون مقدار ساختگی
    _, body, headers = _res(AIErrorKind.rate_limit, retryable=True, retry_after=1.2)
    assert (headers["retry-after"], body["retry_after"]) == ("2", 2)
    # نبود/صفر/منفی → هیچ مقداری ساخته نمی‌شود
    for value in (None, 0, -5):
        _, body, headers = _res(AIErrorKind.rate_limit, retryable=True, retry_after=value)
        assert "retry-after" not in headers and "retry_after" not in body
    # سقف روزانه (quota/budget): زمان ریست معلوم نیست → بدون Retry-After
    for kind in (AIErrorKind.quota_exhausted, AIErrorKind.budget):
        status, body, headers = _res(kind, retryable=True, retry_after=60)
        assert (status, body["retryable"]) == (429, True)
        assert "retry-after" not in headers and "retry_after" not in body


def test_free_unavailable_is_distinct_from_a_rate_limit() -> None:
    rate = _res(AIErrorKind.rate_limit, retryable=True, retry_after=5)
    free = _res(AIErrorKind.free_unavailable, provider="groq")
    quota = _res(AIErrorKind.quota_exhausted)
    assert rate[0] == 429 and rate[1]["retryable"] is True
    assert free[0] == 503 and free[1]["retryable"] is False
    assert quota[0] == 429 and quota[1]["retryable"] is False
    assert {rate[1]["kind"], free[1]["kind"], quota[1]["kind"]} == {
        "rate_limit", "free_unavailable", "quota_exhausted"}


def test_response_never_echoes_the_raw_message() -> None:
    leaked = "fake-key-0123456789"
    raw = (f'{leaked} {{"error": {{"message": "provider body"}}}} '
           "Traceback (most recent call last)")
    for kind in AIErrorKind:
        response = ai_error_response(AIError(raw, kind=kind, provider="groq"))
        text = response.body.decode()
        assert leaked not in text
        assert "provider body" not in text and "Traceback" not in text
        body = json.loads(text)
        assert body["detail"] in SAFE_MESSAGES.values()
        assert set(body) <= {"detail", "kind", "retryable", "provider", "retry_after"}
        assert isinstance(body["detail"], str) and body["detail"]  # کلاینت چیزی برای نمایش دارد


def test_unknown_kind_attribute_falls_back_to_unknown() -> None:
    exc = AIError("boom")
    exc.kind = "not-a-real-kind"
    assert ai_error_response(exc).status_code == 500


def test_only_aierror_is_handled() -> None:
    """هندلر فقط برای AIError ثبت شده؛ خطاهای غیرمرتبط رفتار پیش‌فرض را دارند."""
    assert app.exception_handlers[AIError] is ai_error_handler
    assert Exception not in app.exception_handlers

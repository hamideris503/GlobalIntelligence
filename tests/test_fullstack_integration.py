"""Full-stack integration: real app + real gateway + real Free-Only policy.

The browser suite (`apps/web/e2e/fullstack.spec.ts`) drives the real UI against
the real app over HTTP, but that server pins MOCK_MODE=true, so the policy gate
itself is unreachable there. These tests close that gap: real gateway, real
provider adapters, transport stubbed with `httpx.MockTransport` (the project's
existing offline pattern; async calls go through asyncio.run, as the rest of
the suite does). Every test runs under an autouse guard that fails on any
non-loopback socket connect or DNS lookup, so "no network" is enforced rather
than assumed. No live provider, no real key, shared test DB only.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import socket
from collections.abc import Callable, Iterator
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.ai import free_policy
from backend.ai.gateway.gateway import AIGateway, get_gateway
from backend.ai.routing.router import Route
from backend.ai.schemas.types import AIError, AIErrorKind, AIRequest, Message
from backend.api.errors import SAFE_MESSAGES
from backend.core.config import get_settings
from backend.database.session import get_db
from backend.main import app

PROVIDER, MODEL = "groq", "openai/gpt-oss-20b"  # sole allow-listed pair
FAKE_GROQ_KEY = "test-fake-groq-key-0123456789"
_LOOPBACK = ("127.0.0.1", "::1", "localhost", "")


@pytest.fixture(autouse=True)
def _no_outbound(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail-closed guard: any non-loopback connection or DNS attempt fails the test."""
    attempts: list[str] = []
    real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo

    def connect(self, address):  # noqa: ANN001
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in _LOOPBACK:
            attempts.append(f"connect {host}")
            raise OSError(f"outbound connection blocked: {host}")
        return real_connect(self, address)

    def getaddrinfo(host, *args, **kwargs):  # noqa: ANN001
        if isinstance(host, str) and host not in _LOOPBACK:
            attempts.append(f"dns {host}")
            raise OSError(f"DNS lookup blocked: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield
    assert attempts == [], f"real outbound traffic attempted: {attempts}"


class _Stub:
    """Canned provider transport (httpx.MockTransport); records what was sent."""

    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def install(self, monkeypatch: pytest.MonkeyPatch) -> _Stub:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self._responder(request)

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient

        def factory(*args, **kwargs):  # noqa: ANN001
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return self


def _chat_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "model": MODEL,
        "choices": [{"message": {"role": "assistant", "content": "e2e stub answer"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    })


def _real_gateway(monkeypatch: pytest.MonkeyPatch) -> AIGateway:
    """Gateway with MOCK_MODE off, a fake key and a single-provider chain."""
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    get_settings.cache_clear()
    gw = AIGateway()
    gw.set_routes({"e2e": Route(role="e2e", providers=[PROVIDER])})
    return gw


def _req(**metadata: object) -> AIRequest:
    return AIRequest(messages=[Message.user("ping")], role="e2e", metadata=dict(metadata))


# --- environment isolation ---
def test_routers_use_the_temporary_test_database() -> None:
    """The session the app hands to routers is the isolated test DB, not the real one."""
    assert get_settings().app_env != "production"
    override = app.dependency_overrides[get_db]
    session = next(iter(override()))
    try:
        assert "sqlite" in str(session.get_bind().url)
    finally:
        session.close()


# --- scenario 10: an allow-listed pair passes policy and reaches the transport ---
def test_allowlisted_pair_passes_policy_and_reaches_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    response = asyncio.run(_real_gateway(monkeypatch).generate(_req()))

    assert response.is_mock is False  # a real (stubbed) provider answer, not mock
    assert (response.provider, response.model) == (PROVIDER, MODEL)
    assert response.text == "e2e stub answer"
    assert response.finish_reason == "stop"
    assert response.usage.total_tokens == 10

    (request,) = stub.requests
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_GROQ_KEY}"
    assert json.loads(request.content)["model"] == MODEL


# --- scenario 9 + security: the gate runs before any HTTP, with no fallback ---
@pytest.mark.parametrize(("metadata", "kind"), [
    ({"model": "gpt-4o-mini"}, AIErrorKind.model_not_allowed),
    ({"model": "llama-3.3-70b-versatile"}, AIErrorKind.model_not_allowed),
    ({"force_provider": "openai"}, AIErrorKind.model_not_allowed),  # known, unverified
    ({"force_provider": "not-a-real-provider"}, AIErrorKind.provider_not_allowed),
])
def test_policy_rejects_before_any_http(
    metadata: dict[str, object], kind: AIErrorKind, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    with pytest.raises(AIError) as exc:
        asyncio.run(_real_gateway(monkeypatch).generate(_req(**metadata)))

    assert exc.value.kind == kind
    assert not exc.value.retryable
    assert stub.requests == []  # nothing was sent


def test_expired_verification_blocks_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    future = date.today() + timedelta(days=free_policy.REVIEW_DAYS_DEFAULT + 1)
    monkeypatch.setattr(free_policy, "_utc_today", lambda: future)

    with pytest.raises(AIError) as exc:
        asyncio.run(_real_gateway(monkeypatch).generate(_req()))

    assert exc.value.kind == AIErrorKind.model_not_allowed
    assert "expired" in str(exc.value)
    assert stub.requests == []


# --- security: exhausted quota stops; nothing deleted, no fallback ---
def test_daily_quota_exhaustion_has_no_fallback_and_keeps_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_id = client.post(
        "/api/settings/providers", json={"name": "E2E Quota", "kind": "groq"}).json()["id"]
    model_id = client.post(
        "/api/settings/models",
        json={"provider_id": provider_id, "model_name": "quota-probe"}).json()["id"]

    def quota(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "30"},
                              json={"error": {"message": "daily quota exceeded"}})

    stub = _Stub(quota).install(monkeypatch)
    with pytest.raises(AIError) as exc:
        asyncio.run(_real_gateway(monkeypatch).generate(_req()))

    assert exc.value.kind == AIErrorKind.free_unavailable
    assert len(stub.requests) == 1  # no retry, no fallback to another provider

    models = client.get("/api/settings/models").json()
    assert [m["id"] for m in models] == [model_id]
    assert models[0]["enabled"] is False

# --- the same gateway path over the chat HTTP contract (stubbed transport) ---
def test_chat_route_passes_through_gateway_policy_and_transport(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    get_settings.cache_clear()

    res = client.post("/api/ai/chat", json={
        "provider": PROVIDER,
        "model": MODEL,
        "messages": [{"role": "user", "content": "ping"}],
    })

    assert res.status_code == 200
    body = res.json()
    assert body["is_mock"] is False  # a (stubbed) provider answer, not a mock one
    assert (body["provider"], body["model"]) == (PROVIDER, MODEL)
    assert body["text"] == "e2e stub answer"
    assert len(stub.requests) == 1


# NOTE: the mock-flag and unknown-provider contracts of /api/ai/chat are already
# pinned by tests/test_ai_chat.py; here we only add what it cannot reach.


# --- API-level error contract: a structured AIError becomes a real status ---
def _real_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """MOCK_MODE off + a fake key: the real gateway path (transport stays stubbed).

    Without the in-provider backoff sleep; the retry loop itself is pinned in
    tests/test_ai_budget.py and is not what these tests measure.
    """
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    monkeypatch.setenv("AI_MAX_RETRIES", "0")
    get_settings.cache_clear()


def _post_chat(client: TestClient, **payload: object):
    return client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "ping"}], **payload})


def test_off_list_model_over_http_is_403_not_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model="gpt-4o-mini")

    assert res.status_code == 403  # نه 500 عمومی
    body = res.json()
    assert body["kind"] == AIErrorKind.model_not_allowed.value
    assert body["detail"] == SAFE_MESSAGES[AIErrorKind.model_not_allowed]
    assert body["retryable"] is False
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert stub.requests == []  # پیش از هر HTTP رد شد
    assert FAKE_GROQ_KEY not in res.text and "Traceback" not in res.text


def test_expired_verification_over_http_is_403_before_any_http(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    _real_mode(monkeypatch)
    future = date.today() + timedelta(days=free_policy.REVIEW_DAYS_DEFAULT + 1)
    monkeypatch.setattr(free_policy, "_utc_today", lambda: future)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 403
    assert res.json()["kind"] == AIErrorKind.model_not_allowed.value
    assert stub.requests == []


def test_blocked_model_over_http_is_403_before_any_http(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub(_chat_ok).install(monkeypatch)
    _real_mode(monkeypatch)
    monkeypatch.setattr(
        free_policy, "FREE_ALLOWLIST",
        tuple(dataclasses.replace(e, status="disabled", disabled_reason="blocked for e2e")
              if e.provider == PROVIDER else e
              for e in free_policy.FREE_ALLOWLIST))

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 403
    assert res.json()["detail"] == SAFE_MESSAGES[AIErrorKind.model_not_allowed]
    assert stub.requests == []


def test_quota_exhaustion_over_http_is_503_and_keeps_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_id = client.post("/api/settings/providers",
                              json={"name": "E2E 503", "kind": "groq"}).json()["id"]

    def quota(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "30"},
                              json={"error": {"message": "daily quota exceeded"}})

    stub = _Stub(quota).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 503  # نه 429 (محدودیت نرخ نیست) و نه 500
    body = res.json()
    assert body["kind"] == AIErrorKind.free_unavailable.value
    assert body["retryable"] is False
    # سقف روزانه: زمان ریست معلوم نیست → بدون Retry-After ساختگی
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert len(stub.requests) == 1  # بدون retry و بدون fallback
    # داده‌ای حذف/غیرفعال نشده و ردیفی به دیتابیس دیگر نرفته است
    providers = client.get("/api/settings/providers").json()
    row = next(p for p in providers if p["id"] == provider_id)
    assert row["enabled"] is True


def test_upstream_auth_failure_over_http_is_auth_and_hides_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key SECRET-BODY"}})

    stub = _Stub(unauthorized).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 502  # شکست سمت provider → نه 500
    body = res.json()
    # معنای اصلی حفظ می‌شود: کلید/اعتبارنامه‌ی provider، نه provider_error عمومی
    assert body["kind"] == AIErrorKind.auth.value
    assert body["detail"] == SAFE_MESSAGES[AIErrorKind.auth]
    assert body["provider"] == PROVIDER
    assert body["retryable"] is False
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert len(stub.requests) == 1  # auth قابل retry نیست
    assert "SECRET-BODY" not in res.text
    assert FAKE_GROQ_KEY not in res.text and "Traceback" not in res.text


# --- Gateway → API: هر kind معنای خودش را تا پاسخ HTTP حفظ می‌کند ---
def _rate_limited(seconds: str = "7") -> Callable[[httpx.Request], httpx.Response]:
    """429 موقت (بدون نشانه‌ی سهمیه‌ی روزانه) با Retry-After واقعی."""
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": seconds},
                              json={"error": {"message": "too many requests"}})
    return responder


def _upstream_5xx(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": {"message": "upstream boom"}})


def test_rate_limit_over_http_keeps_429_and_the_real_retry_after(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider 429 با Retry-After معتبر → API همان معنا را می‌دهد (نه 502)."""
    stub = _Stub(_rate_limited("7")).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 429  # نه 502 provider_error
    body = res.json()
    assert body["kind"] == AIErrorKind.rate_limit.value
    assert body["retryable"] is True
    assert body["retry_after"] == 7  # مقدار واقعی provider
    assert res.headers["retry-after"] == "7"
    assert len(stub.requests) == 1  # retry غیرفعال در تنظیمات تست
    assert FAKE_GROQ_KEY not in res.text and "Traceback" not in res.text


def test_rate_limit_ignores_an_unusable_retry_after(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry-After نامعتبر/تاریخی → هیچ مقدار ساختگی ساخته نمی‌شود."""
    stub = _Stub(_rate_limited("Wed, 21 Oct 2026 07:28:00 GMT")).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 429
    body = res.json()
    assert body["kind"] == AIErrorKind.rate_limit.value
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert len(stub.requests) == 1


def test_timeout_over_http_is_504(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out SECRET-TIMEOUT", request=request)

    stub = _Stub(slow).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 504  # نه 502 و نه 500
    body = res.json()
    assert body["kind"] == AIErrorKind.timeout.value
    assert body["provider"] == PROVIDER
    assert body["retryable"] is True
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert len(stub.requests) == 1
    assert "SECRET-TIMEOUT" not in res.text  # متن خام فقط لاگ می‌شود
    assert FAKE_GROQ_KEY not in res.text and "Traceback" not in res.text


def test_connection_failure_over_http_is_502_without_leaks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused SECRET-CONN", request=request)

    stub = _Stub(unreachable).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 502
    body = res.json()
    assert body["kind"] == AIErrorKind.connection.value
    assert body["retryable"] is True
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert len(stub.requests) == 1
    assert "SECRET-CONN" not in res.text
    assert FAKE_GROQ_KEY not in res.text and "Traceback" not in res.text


def test_unusable_provider_output_over_http_is_502_without_leaks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def garbage(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>SECRET-BODY</html>")

    stub = _Stub(garbage).install(monkeypatch)
    _real_mode(monkeypatch)

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 502
    body = res.json()
    assert body["kind"] == AIErrorKind.invalid_output.value
    assert body["detail"] == SAFE_MESSAGES[AIErrorKind.invalid_output]
    assert body["retryable"] is False
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert len(stub.requests) == 1  # پاسخ نامعتبر retry نمی‌شود
    assert "SECRET-BODY" not in res.text
    assert FAKE_GROQ_KEY not in res.text and "Traceback" not in res.text


def test_internal_budget_over_http_is_429_and_not_a_provider_quota(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """بودجه‌ی داخلی پروژه ≠ سهمیه‌ی provider: پیش از هر HTTP تمام می‌شود."""
    from backend.ai import budget as budget_module
    from tests.conftest import TestingSession

    stub = _Stub(_chat_ok).install(monkeypatch)
    _real_mode(monkeypatch)
    monkeypatch.setenv("AI_DAILY_TOKEN_BUDGET", "1")  # فقط در همین تست، بر temp DB
    get_settings.cache_clear()
    budget_module.set_session_factory(TestingSession)  # conftest آن را ریست می‌کند

    res = _post_chat(client, provider=PROVIDER, model=MODEL)

    assert res.status_code == 429
    body = res.json()
    assert body["kind"] == AIErrorKind.budget.value  # نه quota_exhausted/free_unavailable
    assert body["kind"] != AIErrorKind.free_unavailable.value
    assert body["retryable"] is False
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert stub.requests == []  # بودجه پیش از provider بررسی/صدا زده می‌شود


# --- زنجیره‌ی چند-provider: انتخاب خطای نهایی ثابت و مستقل از ترتیب شکست ---
def _by_host(handlers: dict[str, Callable[[httpx.Request], httpx.Response]]):
    def responder(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        for marker, handler in handlers.items():
            if marker in host:
                return handler(request)
        raise AssertionError(f"unexpected host in stubbed transport: {host}")
    return responder


@pytest.mark.parametrize("order", [["groq", "gemini"], ["gemini", "groq"]])
def test_chain_error_priority_is_fixed_regardless_of_failure_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, order: list[str],
) -> None:
    """قاعده‌ی مستند `_CHAIN_FAILURE_ORDER`: rate_limit بر provider_error مقدم است.

    هر دو provider مجاز واقعی‌اند و هر دو پیش از HTTP از policy عبور می‌کنند؛
    فقط ترتیب زنجیره عوض می‌شود. نتیجه‌ی نهایی باید یکی باشد.
    """
    _real_mode(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    get_settings.cache_clear()
    monkeypatch.setattr(
        free_policy, "FREE_ALLOWLIST",
        tuple(dataclasses.replace(e, status="active", disabled_reason="")
              if e.provider == "gemini" else e
              for e in free_policy.FREE_ALLOWLIST))

    stub = _Stub(_by_host({"groq": _rate_limited("7"), "googleapis": _upstream_5xx}))
    stub.install(monkeypatch)
    get_gateway().set_routes({"chat": Route("chat", list(order))})

    res = _post_chat(client)  # بدون provider/model ⇒ مدل پیش‌فرض مجاز هر provider

    assert res.status_code == 429  # نه 502؛ علت غالب محدودیت نرخ است
    body = res.json()
    assert body["kind"] == AIErrorKind.rate_limit.value
    assert body["provider"] == "groq"
    assert body["retry_after"] == 7 and res.headers["retry-after"] == "7"
    assert len(stub.requests) == 2  # هر دو provider دقیقاً یک بار

"""Tests for AI chat endpoint (Step 8): user-selected provider/model, text chat.

The endpoint must take its session from the standard `get_db` dependency (which
`tests/conftest.py` overrides with the in-memory test DB), never from the
process-wide `get_session_factory()`/engine. The autouse fixture below fails the
test if the chat path asks for that configured engine/factory or opens a
non-loopback socket, so this suite proves isolation instead of assuming it.
"""
from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import backend.database.session as session_module
from backend.ai.schemas.types import AIErrorKind
from backend.core.config import get_settings
from backend.database.models.ai_settings import AIProviderRow
from backend.database.session import get_db
from backend.main import app
from tests.conftest import TestingSession

_LOOPBACK = ("127.0.0.1", "::1", "localhost", "")
FAKE_KEY = "test-fake-key-abcdef123456"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed: no configured engine/factory, no outbound socket."""

    def boom(*_args, **_kwargs):
        raise AssertionError("chat built a session/engine outside the get_db dependency")

    monkeypatch.setattr(session_module, "get_engine", boom)
    monkeypatch.setattr(session_module, "get_session_factory", boom)

    real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo

    def connect(self, address):  # noqa: ANN001
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in _LOOPBACK:
            raise AssertionError(f"outbound connection attempted: {host}")
        return real_connect(self, address)

    def getaddrinfo(host, *args, **kwargs):  # noqa: ANN001
        if isinstance(host, str) and host not in _LOOPBACK:
            raise AssertionError(f"DNS lookup attempted: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


def _chat(client: TestClient, **payload: object):
    return client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "user", "content": "hi"}], **payload},
    )


def _add_provider(name: str, *, enabled: bool = True, kind: str = "groq") -> str:
    """Write a provider into the shared test DB (same DB the fixture hands out)."""
    with TestingSession() as session:
        session.add(AIProviderRow(name=name, kind=kind, enabled=enabled))
        session.commit()
    return name


# --- existing API contract (unchanged by the session fix) ---
def test_chat_mock_and_validation(client: TestClient) -> None:
    # MOCK_MODE=true در تست‌ها → پاسخ mock با پرچم صادقانه
    res = client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "سلام"}],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["is_mock"] is True
    assert body["text"]

    # پیام خالی رد می‌شود
    bad = client.post("/api/ai/chat", json={"messages": []})
    assert bad.status_code == 422

    # provider ناشناس رد می‌شود
    unk = client.post("/api/ai/chat", json={
        "provider": "no-such-provider",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert unk.status_code == 422


def test_chat_accepts_known_env_provider(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-fake-env-key-1234567890")
    from backend.core.config import get_settings

    get_settings.cache_clear()
    try:
        res = client.post("/api/ai/chat", json={
            "provider": "groq",
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert res.status_code == 200  # mock ولی provider پذیرفته شد
    finally:
        get_settings.cache_clear()


# --- the fix: the provider lookup runs on the injected test DB ---
def test_chat_reads_providers_from_the_test_database(client: TestClient) -> None:
    name = _add_provider("Chat DB Provider")
    assert _chat(client, provider=name).status_code == 200  # only the test DB knows it

    disabled = _add_provider("Chat DB Disabled", enabled=False)
    assert _chat(client, provider=disabled).status_code == 422  # enabled flag honoured

    with TestingSession() as session:  # written and read through the same DB
        row = session.execute(
            select(AIProviderRow).where(AIProviderRow.name == name)
        ).scalar_one()
        assert row.enabled is True


def test_chat_uses_the_session_from_the_dependency(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = _add_provider("Chat Session Provider")

    yielded: list[Session] = []

    def override():
        session = TestingSession()
        yielded.append(session)
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, override)

    queried: list[Session] = []
    real_execute = Session.execute

    def execute(self, *args, **kwargs):  # noqa: ANN001
        queried.append(self)
        return real_execute(self, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", execute)

    assert _chat(client, provider=name).status_code == 200
    assert queried and queried[0] is yielded[0]


def test_chat_session_is_closed_when_the_request_ends(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = _add_provider("Chat Closed Session Provider")

    yielded: list[Session] = []

    def override():
        session = TestingSession()
        yielded.append(session)
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, override)

    closed: list[Session] = []
    real_close = Session.close

    def close(self):  # noqa: ANN001
        closed.append(self)
        return real_close(self)

    monkeypatch.setattr(Session, "close", close)

    assert _chat(client, provider=name).status_code == 200
    assert yielded and yielded[0] in closed  # the request-scoped session was closed


# --- the gateway and its Free-Only policy still gate the chat path ---
def test_chat_off_list_model_is_a_403_policy_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """رد سیاست باید 403 ساختاریافته باشد، نه 500 (backend/api/errors.py)."""
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    get_settings.cache_clear()
    try:
        res = _chat(client, provider="groq", model="gpt-4o-mini")
    finally:
        get_settings.cache_clear()

    assert res.status_code == 403
    body = res.json()
    assert body["kind"] == AIErrorKind.model_not_allowed.value
    assert body["retryable"] is False
    assert "retry_after" not in body and "retry-after" not in res.headers
    assert isinstance(body["detail"], str) and body["detail"]
    # the autouse guard proves no request was attempted (no socket, no engine)


def test_chat_db_outage_falls_back_to_env_providers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DB error must not turn a configured provider into a 5xx (existing contract)."""
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    get_settings.cache_clear()

    def broken(self, *args, **kwargs):  # noqa: ANN001
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(Session, "execute", broken)
    try:
        assert _chat(client, provider="groq").status_code == 200  # env fallback
        assert _chat(client, provider="no-such-provider").status_code == 422
    finally:
        get_settings.cache_clear()

"""WP-07.1 — Provider Draft-first و گیت تست اتصال.

قواعدی که این تست‌ها قفل می‌کنند:

1. `POST /api/settings/providers` همیشه Draft می‌سازد (`enabled=False`)، حتی اگر
   کلاینت `enabled=true` بفرستد؛ مدل پیش‌فرض هم Draft است.
2. `PUT {enabled:true}` بدون شاهد تست موفق → 422 با پیام روشن.
3. تست اتصال روی Draft مجاز است و در صورت موفقیت، همان درخواست Provider را
   فعال می‌کند (گذار Draft → فعال با شاهد، بدون دور زدن سیاست).
4. سیاست Free روی مسیر تست هم اعمال می‌شود (مدل تأییدنشده → 200 با `ok=False`،
   Provider همچنان Draft).
5. چرخش کلید، شاهد تست را باطل و Provider را به Draft برمی‌گرداند.

تمام HTTP با `httpx.MockTransport` جعل می‌شود؛ هیچ درخواست شبکه‌ای یا هزینه‌ای
انجام نمی‌شود.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.database.models.ai_settings import AIModelRow, AIProviderRow
from tests.conftest import TestingSession

FAKE_KEY = "gsk-test-key-not-real-0000"
POLICY_MODEL = "openai/gpt-oss-20b"  # تنها جفت active در free allowlist
EV = {
    "source_url": "https://example.com/pricing",
    "limits": "10/day",
    "account_prereqs": "no card",
    "privacy_notes": "none",
    "confirm": True,
}


class _Stub:
    """Canned transport برای فراخوانی واقعی Gateway در مسیر تست اتصال."""

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


@pytest.fixture(autouse=True)
def _wire_credentials_store():
    """factory ذخیره‌ساز اعتبارنامه را به DB تست وصل می‌کند.

    در production این کار در `lifespan` انجام می‌شود؛ TestClient بدون context
    مدیر، lifespan را اجرا نمی‌کند، پس اینجا صریح وصل (و در پایان برگردانده) می‌شود.
    """
    from backend.ai import credentials_store as store

    previous = store._factory
    store.set_session_factory(TestingSession)
    yield
    store._factory = previous


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch):
    """حالت Real (بدون mock) برای مسیر تست اتصال؛ هیچ درخواست شبکه‌ای نمی‌رود."""
    monkeypatch.setenv("MOCK_MODE", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _chat_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "model": POLICY_MODEL,
        "choices": [{"message": {"role": "assistant", "content": "OK"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    })


def _create_provider(client: TestClient, name: str = "DraftProvider") -> dict:
    res = client.post("/api/settings/providers",
                      json={"name": name, "kind": "groq", "api_key": FAKE_KEY,
                            "enabled": True})
    assert res.status_code == 200, res.text
    return res.json()


def _row(pid: str) -> AIProviderRow:
    session = TestingSession()
    try:
        row = session.get(AIProviderRow, uuid.UUID(pid))
        assert row is not None
        return row
    finally:
        session.close()


def _policy_model_verified(client: TestClient, pid: str) -> str:
    res = client.post("/api/settings/models",
                      json={"provider_id": pid, "model_name": POLICY_MODEL})
    assert res.status_code == 200, res.text
    mid = res.json()["id"]
    assert client.post(f"/api/settings/models/{mid}/verify", json=EV).status_code == 200
    assert client.put(f"/api/settings/models/{mid}", json={"enabled": True}).status_code == 200
    return mid


def test_new_provider_is_draft_even_if_client_asks_enabled(client: TestClient) -> None:
    body = _create_provider(client)
    assert body["enabled"] is False
    assert body["last_test_status"] is None
    row = _row(body["id"])
    assert row.enabled is False
    assert row.api_key_encrypted, "کلید باید ذخیره شود (write-only)"


def test_default_model_created_as_draft(client: TestClient) -> None:
    res = client.post("/api/settings/providers",
                      json={"name": "WithModel", "kind": "groq", "api_key": FAKE_KEY,
                            "default_model": POLICY_MODEL})
    assert res.status_code == 200, res.text
    pid = res.json()["id"]
    session = TestingSession()
    try:
        model = session.query(AIModelRow).filter(
            AIModelRow.provider_id == uuid.UUID(pid)).one()
        assert model.model_name == POLICY_MODEL
        assert model.enabled is False, "مدل Provider جدید نباید فعال باشد"
    finally:
        session.close()


def test_activation_without_test_is_rejected(client: TestClient) -> None:
    pid = _create_provider(client)["id"]
    res = client.put(f"/api/settings/providers/{pid}", json={"enabled": True})
    assert res.status_code == 422
    assert "connectivity test" in res.text
    assert _row(pid).enabled is False


def test_successful_connectivity_test_promotes_draft(client: TestClient, real_mode,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    pid = _create_provider(client)["id"]
    _policy_model_verified(client, pid)

    stub = _Stub(_chat_ok).install(monkeypatch)
    res = client.post(f"/api/settings/providers/{pid}/test", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["provider"] == "DraftProvider"
    assert body["total_tokens"] == 6
    assert len(stub.requests) == 1, "تست باید دقیقاً یک تلاش باشد"

    row = _row(pid)
    assert row.enabled is True, "تست موفق باید Provider را فعال کند"
    assert row.last_test_status == "ok"

    # اکنون فعال‌سازی/غیرفعال‌سازی دستی مجاز است.
    assert client.put(f"/api/settings/providers/{pid}",
                      json={"enabled": False}).status_code == 200


def test_policy_is_enforced_on_draft_test_path(client: TestClient, real_mode,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    pid = _create_provider(client, name="PolicyDraft")["id"]
    res = client.post("/api/settings/models",
                      json={"provider_id": pid, "model_name": "made-up-model"})
    assert res.status_code == 200, res.text
    mid = res.json()["id"]
    client.post(f"/api/settings/models/{mid}/verify", json=EV)
    client.put(f"/api/settings/models/{mid}", json={"enabled": True})

    stub = _Stub(_chat_ok).install(monkeypatch)
    res = client.post(f"/api/settings/providers/{pid}/test",
                      json={"model": "made-up-model"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert "not verified" in (body["error"] or "")
    assert stub.requests == [], "سیاست باید پیش از هر HTTP رد کند"
    row = _row(pid)
    assert row.enabled is False
    assert row.last_test_status == "fail"


def test_key_rotation_returns_provider_to_draft(client: TestClient, real_mode,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    pid = _create_provider(client, name="RotateMe")["id"]
    _policy_model_verified(client, pid)
    _Stub(_chat_ok).install(monkeypatch)
    assert client.post(f"/api/settings/providers/{pid}/test", json={}).json()["ok"] is True
    assert _row(pid).enabled is True

    rotated = client.post(f"/api/settings/providers/{pid}/key",
                          json={"api_key": "gsk-rotated-key-1111"})
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["enabled"] is False
    row = _row(pid)
    assert row.last_test_status is None
    assert row.last_tested_at is None

    # بدون تست جدید، فعال‌سازی دوباره رد می‌شود.
    assert client.put(f"/api/settings/providers/{pid}",
                      json={"enabled": True}).status_code == 422

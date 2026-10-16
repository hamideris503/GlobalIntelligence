"""Tests for AI chat endpoint (Step 8): user-selected provider/model, text chat."""
from __future__ import annotations

from fastapi.testclient import TestClient


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

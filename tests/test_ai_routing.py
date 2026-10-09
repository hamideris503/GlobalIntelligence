"""Tests for Adaptive AI Router (Phase 37)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.ai.gateway import get_gateway
from backend.database.models.provider_run_stat import ProviderRunStat
from domains.ai_routing.router import AdaptiveRouter, smoothed_rate
from tests.conftest import TestingSession


def _record(
    task: str, provider: str, calls: int, successes: int, latency: float = 100.0
) -> None:
    session = TestingSession()
    try:
        router = AdaptiveRouter(session)
        for i in range(calls):
            router.record(
                task=task,
                provider=provider,
                model=f"{provider}-m",
                success=i < successes,
                latency_ms=latency,
            )
    finally:
        session.close()


# --- pure tests ---
def test_smoothed_rate() -> None:
    assert smoothed_rate(1, 1) < smoothed_rate(99, 100)  # لاپلاس: نمونه‌ی بزرگ می‌برد
    assert smoothed_rate(0, 0) == 0.5


# --- router tests ---
def test_record_upserts_monthly() -> None:
    session = TestingSession()
    try:
        router = AdaptiveRouter(session)
        router.record(task="t", provider="p", model="m", success=True)
        router.record(task="t", provider="p", model="m", success=False)
        rows = session.query(ProviderRunStat).all()
        assert len(rows) == 1
        assert rows[0].calls == 2
        assert rows[0].successes == 1 and rows[0].failures == 1
    finally:
        session.close()


def test_suggest_orders_by_smoothed_success() -> None:
    _record("cls", "steady", calls=100, successes=99, latency=500.0)
    _record("cls", "lucky", calls=1, successes=1, latency=10.0)
    _record("cls", "bad", calls=10, successes=2, latency=50.0)
    session = TestingSession()
    try:
        suggestion = AdaptiveRouter(session).suggest(task="cls")
        assert [s.provider for s in suggestion.scores] == ["steady", "lucky", "bad"]
        assert suggestion.providers == ["steady", "lucky", "bad"]
    finally:
        session.close()


def test_suggest_keeps_static_tail() -> None:
    _record("cls", "steady", calls=5, successes=5)
    session = TestingSession()
    try:
        suggestion = AdaptiveRouter(session).suggest(
            task="cls", static_order=["steady", "newbie"]
        )
        assert suggestion.providers == ["steady", "newbie"]
    finally:
        session.close()


def test_suggest_empty_task() -> None:
    session = TestingSession()
    try:
        suggestion = AdaptiveRouter(session).suggest(
            task="never-seen", static_order=["a", "b"]
        )
        assert suggestion.providers == ["a", "b"]
        assert suggestion.scores == []
    finally:
        session.close()


def test_build_routes_injects_gateway() -> None:
    from backend.ai.schemas.types import AIRequest, Message

    _record("cls", "steady", calls=5, successes=5)
    session = TestingSession()
    try:
        routes = AdaptiveRouter(session).build_routes(["cls"])
        gateway = get_gateway()
        old = gateway._routes
        gateway.set_routes(routes)
        try:
            route = gateway._route(
                AIRequest(messages=[Message.user("hi")], task="cls")
            )
            assert route.providers == ["steady"]
        finally:
            gateway._routes = old
    finally:
        session.close()


# --- API tests ---
def test_ai_routing_api(client: TestClient) -> None:
    res = client.post(
        "/api/ai-routing/record",
        json={"task": "cls", "provider": "gemini", "model": "flash",
              "success": True, "latency_ms": 120.0},
    )
    assert res.status_code == 200
    assert res.json()["calls"] == 1

    bad = client.post(
        "/api/ai-routing/record",
        json={"task": "", "provider": "x", "model": "y"},
    )
    assert bad.status_code == 422

    stats = client.get("/api/ai-routing/stats?task=cls")
    assert stats.status_code == 200
    assert len(stats.json()) == 1

    routes = client.get("/api/ai-routing/routes?tasks=cls")
    assert routes.status_code == 200
    assert routes.json()["cls"]["providers"] == ["gemini"]

    applied = client.post("/api/ai-routing/apply?tasks=cls")
    assert applied.status_code == 200
    assert applied.json()["applied"] is True
    # gateway singleton برگردانده شود تا تست‌های دیگر آلوده نشوند
    get_gateway().set_routes({})

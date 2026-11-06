"""F-15 — اعمال خودکار زنجیرهٔ تطبیقی در startup.

قواعد آزموده‌شده: پیش‌فرض خاموش، فقط task دارای شاهد اعمال می‌شود، و task بدون
آمار زنجیرهٔ خالی نمی‌گیرد.
"""
from __future__ import annotations

from backend.ai.adaptive_bootstrap import (
    DEFAULT_TASKS,
    apply_adaptive_routes,
    build_effective_routes,
    parse_tasks,
)
from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from domains.ai_routing.router import AdaptiveRouter
from tests.conftest import TestingSession


def _record(task: str, provider: str, *, calls: int = 3, successes: int | None = None) -> None:
    session = TestingSession()
    try:
        router = AdaptiveRouter(session)
        good = calls if successes is None else successes
        for i in range(calls):
            router.record(
                task=task, provider=provider, model="m1",
                success=i < good, latency_ms=100.0,
            )
    finally:
        session.close()


def _gateway_routes(gateway) -> object:  # noqa: ANN001
    return gateway._routes


def test_disabled_by_default() -> None:
    assert get_settings().adaptive_routing_enabled is False


def test_parse_tasks_strips_dedupes_and_defaults() -> None:
    assert parse_tasks(" a, b ,a,,") == ["a", "b"]
    assert parse_tasks("") == list(DEFAULT_TASKS)
    assert parse_tasks(None) == list(DEFAULT_TASKS)


def test_effective_routes_skip_tasks_without_evidence() -> None:
    _record("cls", "steady")
    session = TestingSession()
    try:
        effective = build_effective_routes(session, ["cls", "no_stats_task"])
        assert effective == {"cls": ["steady"]}
    finally:
        session.close()


def test_apply_injects_gateway_and_keeps_static_for_unknown_task() -> None:
    _record("cls", "steady")
    session = TestingSession()
    gateway = get_gateway()
    old = _gateway_routes(gateway)
    try:
        applied = apply_adaptive_routes(session, ["cls", "no_stats_task"])
        assert applied == {"cls": ["steady"]}

        routed = gateway._route(AIRequest(messages=[Message.user("hi")], task="cls"))
        assert routed.providers == ["steady"]

        untouched = gateway._route(
            AIRequest(messages=[Message.user("hi")], task="no_stats_task")
        )
        assert untouched.providers != ["steady"]
    finally:
        gateway._routes = old
        session.close()


def test_apply_is_noop_without_any_statistics() -> None:
    session = TestingSession()
    gateway = get_gateway()
    old = _gateway_routes(gateway)
    try:
        assert apply_adaptive_routes(session, ["cls"]) == {}
        assert _gateway_routes(gateway) is old  # هیچ set_routes رخ نداد
    finally:
        gateway._routes = old
        session.close()

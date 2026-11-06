"""بند ۲.۷ — پین‌کردن revision پیکربندی در زمان اجرا.

منبع حقیقت: `ConfigurationInstance(kind="source", slug=<Source.name>)`.
"""
from __future__ import annotations

import asyncio
import json

from backend.configuration.runtime import pinned_payload, resolve_source_plan
from backend.database.models.configuration import ConfigurationInstance, ConfigurationRevision
from backend.database.models.source import Source
from source_bot.metrics import BotMetrics
from source_bot.runner import run_source
from tests.conftest import TestingSession

LIVE_FEED = "https://live.example.com/feed.xml"
PINNED_FEED = "https://pinned.example.com/feed.xml"


def _source(name: str = "PinnedSrc") -> Source:
    return Source(
        name=name, domain="pin.local", type="rss",
        collection_method="rss", feed_url=LIVE_FEED, active=True,
    )


def _pin(session, source: Source, payload: dict, *, status: str = "active") -> int:  # noqa: ANN001
    instance = ConfigurationInstance(
        kind="source", slug=source.name, latest_revision=1,
        active_revision=1 if status == "active" else None,
    )
    session.add(instance)
    session.flush()
    session.add(
        ConfigurationRevision(
            instance_id=instance.id, revision_number=1, status=status,
            payload_json=json.dumps(payload), actor="test",
        )
    )
    session.commit()
    return 1


def test_pinned_revision_overrides_live_row() -> None:
    session = TestingSession()
    try:
        source = _source()
        session.add(source)
        session.commit()
        _pin(session, source, {
            "name": source.name, "type": "rss", "collection_method": "rss",
            "feed_url": PINNED_FEED,
        })

        plan, revision = resolve_source_plan(session, source)
        assert revision == 1
        assert plan.adapter == "rss"
        assert plan.url == PINNED_FEED
        assert pinned_payload(session, source.name)[0] == 1
    finally:
        session.close()


def test_without_pin_live_row_is_used() -> None:
    session = TestingSession()
    try:
        source = _source("NoPinSrc")
        session.add(source)
        session.commit()

        plan, revision = resolve_source_plan(session, source)
        assert revision is None
        assert plan.url == LIVE_FEED
    finally:
        session.close()


def test_non_active_revision_is_not_pinned() -> None:
    session = TestingSession()
    try:
        source = _source("ArchivedPinSrc")
        session.add(source)
        session.commit()
        _pin(session, source, {
            "name": source.name, "type": "rss", "collection_method": "rss",
            "feed_url": PINNED_FEED,
        }, status="archived")

        plan, revision = resolve_source_plan(session, source)
        assert revision is None
        assert plan.url == LIVE_FEED
    finally:
        session.close()


def test_unusable_pin_falls_back_to_live_row() -> None:
    """پیکربندی پین‌شده‌ای که به skip برسد اجرا را متوقف نمی‌کند."""
    session = TestingSession()
    try:
        source = _source("BrokenPinSrc")
        session.add(source)
        session.commit()
        _pin(session, source, {
            "name": source.name, "type": "rss", "collection_method": "rss",
        })

        plan, revision = resolve_source_plan(session, source)
        assert revision is None
        assert plan.url == LIVE_FEED
    finally:
        session.close()


def test_ingestion_run_records_the_pinned_revision(monkeypatch) -> None:  # noqa: ANN001
    session = TestingSession()
    try:
        source = _source("RunPinSrc")
        session.add(source)
        session.commit()
        _pin(session, source, {
            "name": source.name, "type": "rss", "collection_method": "rss",
            "feed_url": PINNED_FEED,
        })

        captured: list[str | None] = []

        async def _fake_fetch(plan, settings):  # noqa: ANN001, ANN202
            captured.append(plan.url)
            return [], plan.url or "", {}

        monkeypatch.setattr("source_bot.runner._fetch_plan", _fake_fetch)

        metrics = BotMetrics()
        asyncio.run(run_source(session, source, metrics))

        assert captured == [PINNED_FEED]  # fetch روی پیکربندی پین‌شده انجام شد
        assert metrics.by_source[source.name].config_revision == 1
        assert metrics.as_dict()["by_source"][source.name]["config_revision"] == 1
    finally:
        session.close()

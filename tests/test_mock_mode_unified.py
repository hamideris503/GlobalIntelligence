"""Unified mock-mode semantics (Phase A) — one resolver, consistent consumers.

Matrix: env x DB-override. No production contact (sqlite only, no network).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.core.mock_mode import effective_mock_mode
from backend.database.models.source import Source
from domains.news.fetchers import MockFetcher, RSSFetcher
from tests.conftest import TestingSession


def _env(monkeypatch, mock: str):
    monkeypatch.setenv("MOCK_MODE", mock)
    get_settings.cache_clear()


def _override(monkeypatch, value: str | None):
    """Simulate the DB-override layer without a real database override table."""
    import backend.ai.credentials_store as store

    if value is None:
        def _raise():
            raise RuntimeError("no override store")
        monkeypatch.setattr(store, "effective_mock_mode", _raise)
    else:
        want = value.strip().lower() in ("1", "true", "yes", "on")
        monkeypatch.setattr(store, "effective_mock_mode", lambda: want)


@pytest.mark.parametrize(
    ("env", "override", "expected"),
    [
        ("true", "true", True),
        ("true", "false", False),   # override wins over env
        ("false", "true", True),    # override wins over env
        ("false", "false", False),
        ("true", None, True),       # missing override -> env
        ("false", None, False),
    ],
)
def test_effective_mock_matrix(monkeypatch, env, override, expected):
    _env(monkeypatch, env)
    import backend.ai.credentials_store as store

    if override is None:
        monkeypatch.setattr(store, "effective_mock_mode",
                            lambda: (_ for _ in ()).throw(RuntimeError("no store")))
    else:
        want = override.strip().lower() in ("1", "true", "yes", "on")
        monkeypatch.setattr(store, "effective_mock_mode", lambda: want)
    assert effective_mock_mode() is expected
    get_settings.cache_clear()


def test_override_read_failure_falls_back_to_env(monkeypatch):
    _env(monkeypatch, "true")
    _override(monkeypatch, None)
    assert effective_mock_mode() is True
    _env(monkeypatch, "false")
    assert effective_mock_mode() is False
    get_settings.cache_clear()


def test_select_fetcher_follows_unified_mode(monkeypatch):
    from domains.news.ingestion import select_fetcher

    _env(monkeypatch, "true")
    _override(monkeypatch, None)
    assert isinstance(select_fetcher(), MockFetcher)
    _override(monkeypatch, "false")  # operator override beats env
    assert isinstance(select_fetcher(), RSSFetcher)
    get_settings.cache_clear()


def test_guard_and_gateway_agree(monkeypatch):
    """Engine guard + gateway chain + fetch selection agree under override."""
    import json

    from backend.database.models.article import Article
    from backend.database.models.document import Document
    from domains.news.classifier import ArticleClassifier

    _env(monkeypatch, "true")
    _override(monkeypatch, "false")
    db = TestingSession()
    src = Source(name="AgreeSrc", domain="e.local", type="rss", active=True)
    db.add(src)
    db.commit()
    doc = Document(source_id=src.id, title="t", raw_text="real body text here",
                   doc_metadata=json.dumps({"mock": True}))
    db.add(doc)
    db.commit()
    art = Article(document_id=doc.id, title="t", summary="t",
                  classification_status="pending")
    db.add(art)
    db.commit()
    import asyncio

    out = asyncio.run(ArticleClassifier(db).classify_pending(limit=10))
    assert out.skipped == 1  # guard active: override false beats env true
    assert isinstance(__import__("domains.news.ingestion", fromlist=["select_fetcher"]).select_fetcher(),
                      RSSFetcher)  # fetch agrees
    db.close()
    get_settings.cache_clear()


def test_bot_fetch_ignores_mock_settings(monkeypatch):
    """Source Bot real-fetch path is independent of mock settings (unchanged)."""
    import asyncio

    from domains.news.fetchers import RawItem
    from source_bot import runner as runner_module
    from source_bot.metrics import BotMetrics
    from source_bot.runner import run_source

    _env(monkeypatch, "true")
    _override(monkeypatch, "true")

    async def fake_fetch(plan, settings):
        return ([RawItem(title="Bot item", url="https://example.test/b1",
                         raw_text="bot body text " * 20)], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    db = TestingSession()
    src = Source(name="BotSrc", collection_method="rss", type="rss",
                 feed_url="https://example.test/rss")
    db.add(src)
    db.commit()
    from source_bot.config import BotSettings

    settings = BotSettings()
    settings.ai_enabled = False
    metrics = BotMetrics()
    asyncio.run(run_source(db, src, metrics, settings))
    assert metrics.stored == 1 and metrics.fetched == 1
    db.close()
    get_settings.cache_clear()


def test_dev_behavior_unchanged_by_default(client: TestClient):
    """Default test env (MOCK_MODE=true, no override) keeps old behavior."""
    assert effective_mock_mode() is True
    from domains.news.ingestion import select_fetcher

    assert isinstance(select_fetcher(), MockFetcher)

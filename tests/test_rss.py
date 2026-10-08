"""Tests for RSS/Atom parsing (Phase 10 fix — P1/P0-2)."""
from __future__ import annotations

from pathlib import Path

from domains.news.fetchers import RSSFetcher

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_rss_items() -> None:
    content = (FIXTURES / "sample_feed.xml").read_bytes()
    items = RSSFetcher().parse(content, limit=10)
    assert len(items) == 2
    fed = items[0]
    assert fed.title == "Fed holds rates"
    assert fed.url == "https://example.local/fed"
    # content:encoded باید ترجیح داده شود
    assert "Fed" in (fed.raw_text or "")
    assert fed.published_at is not None
    assert fed.raw_payload is not None  # نسخه‌ی خام اصلی


def test_parse_atom_prefers_alternate_link() -> None:
    content = (FIXTURES / "sample_atom.xml").read_bytes()
    items = RSSFetcher().parse(content, limit=10)
    assert len(items) == 1
    assert items[0].url == "https://example.local/ecb"


def test_parse_respects_limit() -> None:
    content = (FIXTURES / "sample_feed.xml").read_bytes()
    items = RSSFetcher().parse(content, limit=1)
    assert len(items) == 1

"""Tests for RSS/Atom parsing (Phase 10 fix — P1/P0-2)."""
from __future__ import annotations

import json
from pathlib import Path

from backend.database.models.document import provenance_of
from domains.news.fetchers import (
    RSS_SUMMARY_ONLY,
    SOURCE_PROVIDED_ONLY,
    TEXT_STATUS,
    RSSFetcher,
)

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


def test_parse_marks_text_status_per_content_type() -> None:
    """content:encoded = متنِ منبع (نه full-text)؛ summary = فقط خلاصه."""
    items = RSSFetcher().parse((FIXTURES / "sample_feed.xml").read_bytes(), limit=5)
    assert items[0].metadata[TEXT_STATUS] == SOURCE_PROVIDED_ONLY
    assert items[1].metadata[TEXT_STATUS] == RSS_SUMMARY_ONLY


def test_parse_summary_marks_real_provenance() -> None:
    item = RSSFetcher().parse((FIXTURES / "sample_atom.xml").read_bytes(), limit=1)[0]
    assert item.metadata["mock"] is False
    assert item.metadata[TEXT_STATUS] == RSS_SUMMARY_ONLY
    assert provenance_of(json.dumps(item.metadata)) == "real"

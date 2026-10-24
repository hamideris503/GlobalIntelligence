"""Full-text RSS enrichment + provenance — offline (fixtures/mocks only)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import MockFetcher, RawItem, RSSFetcher
from source_bot.adapters.html import HtmlAdapter, HtmlResult
from source_bot.fulltext import (
    EXTRACTION_FAILED,
    FULL_TEXT,
    REASON_EXTRACTION,
    SUMMARY_ONLY,
    TEXT_REASON,
    TEXT_STATUS,
    article_allowlist,
    enrich_rss_items,
    host_allowed,
)
from tests.conftest import TestingSession

SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Rates held</title><link>https://articles.example/1</link>
<description>short rss summary</description><guid>g1</guid></item>
</channel></rss>"""

ARTICLE_HTML = (
    "<html><head><title>Rates held</title></head><body><article><h1>Rates held</h1><p>"
    + ("The central bank kept its policy rate unchanged after the meeting. " * 8)
    + "</p></article></body></html>"
)


class _Source:
    def __init__(self, **kw) -> None:
        self.endpoint_config = None
        self.domain = None
        self.homepage_url = None
        self.canonical_url = None
        self.__dict__.update(kw)


def _item(url="https://articles.example/1", text="short rss summary",
          payload='{"summary": "short rss summary"}'):
    return RawItem(title="Rates held", url=url, raw_text=text, raw_payload=payload)


def _long(n=400):
    return ("full article body " * (n // 18)).strip()


ROBOTS_ALLOW = "User-agent: *\nAllow: /\n"


async def _robots_allow(url: str) -> str:  # noqa: ANN202
    """seam آفلاین: robots.txt همه‌جا اجازه می‌دهد (بدون درخواست واقعی)."""
    return ROBOTS_ALLOW


# --- provenance ---

def test_rss_parse_marks_real_provenance():
    from backend.database.models.document import provenance_of

    item = RSSFetcher().parse(SAMPLE_RSS, limit=5)[0]
    assert item.metadata["mock"] is False
    assert provenance_of(json.dumps(item.metadata)) == "real"


def test_mock_fetcher_marks_mock_provenance():
    from backend.database.models.document import provenance_of

    item = asyncio.run(MockFetcher().fetch(url=None, limit=1))[0]
    assert item.metadata["mock"] is True
    assert provenance_of(json.dumps(item.metadata)) == "mock"


def test_missing_flag_remains_unknown():
    from backend.database.models.document import provenance_of

    assert provenance_of('{"guid": "g1"}') == "unknown"


# --- allowlist ---

def test_allowlist_from_source_record_and_env(monkeypatch):
    monkeypatch.setenv("SOURCE_BOT_ARTICLE_DOMAINS", "env.example")
    src = _Source(
        domain="publisher.example",
        homepage_url="https://home.example/about",
        canonical_url="https://canon.example/x",
        endpoint_config=json.dumps({"article_domains": ["bbc.co.uk", "https://extra.example/a"]}),
        feed_url="https://should-be-ignored.example/rss",
    )
    hosts = article_allowlist(src)
    assert {"bbc.co.uk", "extra.example", "env.example", "publisher.example",
            "home.example", "canon.example"} <= set(hosts)
    assert "should-be-ignored.example" not in hosts


def test_subdomain_allowed_but_lookalike_rejected():
    allowed = ("bbc.co.uk",)
    assert host_allowed("www.bbc.co.uk", allowed) is True
    assert host_allowed("bbc.co.uk", allowed) is True
    assert host_allowed("evilbbc.co.uk", allowed) is False
    assert host_allowed("bbc.co.uk.evil.com", allowed) is False


# --- enrichment ---

def test_success_replaces_text_once_and_keeps_rss_payload():
    calls: list[str] = []

    async def fetch(url: str) -> HtmlResult:
        calls.append(url)
        return HtmlResult([RawItem(title="t", url=url, raw_text=_long())], "ok")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert calls == ["https://articles.example/1"]          # دقیقاً یک GET
    assert item.raw_text == _long()
    assert item.raw_payload == '{"summary": "short rss summary"}'  # خلاصه/پیلود حفظ شد
    assert item.metadata[TEXT_STATUS] == FULL_TEXT
    assert item.metadata["full_text_chars"] == len(_long())


def test_fetch_error_falls_back_to_summary():
    async def fetch(url: str) -> HtmlResult:
        raise RuntimeError("boom")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert item.raw_text == "short rss summary"
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY


def test_empty_extraction_falls_back_to_summary():
    async def fetch(url: str) -> HtmlResult:
        return HtmlResult([], "empty")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert item.raw_text == "short rss summary"
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY


def test_shorter_extraction_keeps_summary():
    async def fetch(url: str) -> HtmlResult:
        return HtmlResult([RawItem(title="t", url=url, raw_text="tiny")], "ok")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert item.raw_text == "short rss summary"
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY


def test_disallowed_host_makes_no_request():
    calls: list[str] = []

    async def fetch(url: str) -> HtmlResult:
        calls.append(url)
        return HtmlResult([RawItem(title="t", url=url, raw_text=_long())], "ok")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=("other.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert calls == []
    assert item.raw_text == "short rss summary"
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY


def test_invalid_or_private_url_makes_no_request():
    calls: list[str] = []

    async def fetch(url: str) -> HtmlResult:
        calls.append(url)
        return HtmlResult([], "ok")

    for bad in ("file:///etc/passwd", "http://127.0.0.1/a", "http://localhost/a"):
        item = _item(url=bad)
        asyncio.run(enrich_rss_items([item], allowed_hosts=("127.0.0.1", "localhost", ""),
                                     delay=0, fetch=fetch, robots_fetch=_robots_allow))
        assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY
    assert calls == []


def test_one_failure_does_not_break_other_items():
    seen: list[str] = []

    async def fetch(url: str) -> HtmlResult:
        seen.append(url)
        if url.endswith("/2"):
            raise RuntimeError("one bad article")
        return HtmlResult([RawItem(title="t", url=url, raw_text=_long())], "ok")

    items = [_item(url=f"https://articles.example/{i}") for i in (1, 2, 3)]
    asyncio.run(enrich_rss_items(items, allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert len(seen) == 3
    assert [i.metadata[TEXT_STATUS] for i in items] == [FULL_TEXT, SUMMARY_ONLY, FULL_TEXT]
    assert items[0].raw_text == _long() and items[2].raw_text == _long()
    assert items[1].raw_text == "short rss summary"


def test_no_text_and_failure_marks_extraction_failed():
    async def fetch(url: str) -> HtmlResult:
        return HtmlResult([], "empty")

    item = _item(text=None)
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert item.metadata[TEXT_STATUS] == EXTRACTION_FAILED


def test_failed_extraction_keeps_prior_source_provided_status():
    """content:encoded فید نباید با شکست استخراج به «فقط خلاصه» تنزل پیدا کند."""
    from domains.news.fetchers import SOURCE_PROVIDED_ONLY

    async def fetch(url: str) -> HtmlResult:
        return HtmlResult([], "empty")

    item = _item()
    item.metadata[TEXT_STATUS] = SOURCE_PROVIDED_ONLY
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=fetch, robots_fetch=_robots_allow))
    assert item.metadata[TEXT_STATUS] == SOURCE_PROVIDED_ONLY
    assert item.metadata[TEXT_REASON] == REASON_EXTRACTION


def test_no_allowlist_is_a_noop():
    calls: list[str] = []

    async def fetch(url: str) -> HtmlResult:
        calls.append(url)
        return HtmlResult([], "ok")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=(), delay=0, fetch=fetch, robots_fetch=_robots_allow))
    assert calls == []
    assert TEXT_STATUS not in item.metadata


def test_blocked_target_from_guard_keeps_summary(monkeypatch):
    from domains.news.source_verify import BlockedTarget
    from source_bot.adapters import html as html_module

    async def blocked(client, url, **kw):  # noqa: ANN001
        raise BlockedTarget("private_ip")

    monkeypatch.setattr(html_module, "safe_get", blocked)
    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=HtmlAdapter().fetch_url,
                                 robots_fetch=_robots_allow))
    assert item.raw_text == "short rss summary"
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY


# --- runner integration (offline DB) ---

@pytest.fixture(autouse=True)
def _isolated_stop(tmp_path, monkeypatch):
    from source_bot import runner as runner_module

    monkeypatch.setattr(runner_module, "STOP_PATH", str(tmp_path / "source_bot.stop"))


def _db_source(db, name="ft-src"):
    src = Source(name=name, domain=f"{name}.test", collection_method="rss", type="rss",
                 feed_url=f"https://{name}.test/rss", active=True)
    db.add(src)
    db.commit()
    return src


def _wire(monkeypatch, items):
    from source_bot import runner as runner_module

    async def fake_fetch(plan, settings):  # noqa: ANN001
        return (list(items), "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")


def test_enrichment_runs_after_items_cap(monkeypatch):
    from source_bot import runner as runner_module

    db = TestingSession()
    try:
        _db_source(db)
        items = [RawItem(title=f"t{i}", url=f"https://ft-src.test/{i}",
                         raw_text=f"body number {i}", raw_payload=f'{{"i": {i}}}')
                 for i in range(5)]
        _wire(monkeypatch, items)
        seen: list[list[str]] = []

        async def spy(batch, **kw):  # noqa: ANN001
            seen.append([it.url for it in batch])

        monkeypatch.setattr(runner_module, "enrich_rss_items", spy)
        metrics = asyncio.run(runner_module.run_once(source_name="ft-src",
                                                     max_items_per_source=3, db=db))
        assert metrics.stored == 3
        assert seen == [[f"https://ft-src.test/{i}" for i in range(3)]]  # فقط منتخب‌ها
        assert db.query(Document).count() == 3
    finally:
        db.close()


def test_enriched_text_reaches_storage_and_priority(monkeypatch):
    from backend.database.models.document import provenance_of
    from source_bot import runner as runner_module

    db = TestingSession()
    try:
        _db_source(db, "ft-prio")
        parsed = RSSFetcher().parse(
            SAMPLE_RSS.replace(b"https://articles.example/1", b"https://ft-prio.test/1"),
            limit=5)
        _wire(monkeypatch, parsed)

        async def spy(batch, **kw):  # noqa: ANN001
            for it in batch:
                it.raw_text = ("full article body " * 20).strip()   # >200 ⇒ COMPLETE (+5)
                it.metadata[TEXT_STATUS] = FULL_TEXT

        monkeypatch.setattr(runner_module, "enrich_rss_items", spy)
        metrics = asyncio.run(runner_module.run_once(source_name="ft-prio", db=db))
        doc = db.query(Document).one()
        meta = json.loads(doc.doc_metadata)
        assert metrics.stored == 1
        assert doc.raw_text == ("full article body " * 20).strip()
        assert meta[TEXT_STATUS] == FULL_TEXT
        assert provenance_of(doc.doc_metadata) == "real"      # mock:false از پارس واقعی
        assert doc.priority_score == 25.0 and doc.ingestion_priority == "P3"
    finally:
        db.close()


def test_single_http_download_then_trafilatura(monkeypatch):
    from source_bot.adapters import html as html_module

    calls: list[str] = []

    async def fake_safe_get(client, url, **kw):  # noqa: ANN001
        calls.append(url)
        return httpx.Response(200, content=ARTICLE_HTML.encode("utf-8"),
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(html_module, "safe_get", fake_safe_get)
    result = asyncio.run(HtmlAdapter().fetch_url("https://articles.example/1"))
    assert calls == ["https://articles.example/1"]
    assert result.status == "ok" and len(result.items) == 1
    assert result.items[0].raw_text and len(result.items[0].raw_text) > 100
    assert "<html" not in result.items[0].raw_text.lower()   # HTML خام ذخیره نمی‌شود

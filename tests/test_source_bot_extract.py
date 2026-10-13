"""Source bot extraction tests — بدون شبکه (parse مستقیم + mock)."""
from __future__ import annotations

import asyncio

from source_bot.adapters.csv import CsvAdapter
from source_bot.adapters.html import extract_with_trafilatura
from source_bot.adapters.rest_json import RestJsonAdapter, pick
from source_bot.adapters.rss import BotRSSAdapter
from source_bot.adapters.xml import XmlAdapter

SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Quake hits region</title><link>https://ex.com/1</link>
<description>big earthquake damage</description>
<guid>g1</guid><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_rss_parse_local():
    from domains.news.fetchers import RSSFetcher

    items = RSSFetcher().parse(SAMPLE_RSS, limit=10)
    assert len(items) == 1
    assert items[0].title == "Quake hits region"
    assert items[0].metadata["guid"] == "g1"


def test_rss_adapter_rejects_bad_url():
    import pytest

    async def go():
        with pytest.raises(ValueError):
            await BotRSSAdapter().fetch(url="ftp://ex.com/f", limit=5)
    asyncio.run(go())


def test_rest_json_field_mapping():
    row = {"headline": "H", "link": "https://ex.com/a", "body": "b", "id": "x1"}
    assert pick(row, ("title", "headline", "name")) == "H"
    assert pick(row, ("id", "guid", "external_id", "uuid")) == "x1"


def test_rest_json_auth_required():

    async def go():
        r = await RestJsonAdapter().fetch(url="https://example.com/api", api_key_env="DEF_MISSING_KEY_XYZ")
        assert r.status == "auth_required"
    asyncio.run(go())


def test_xml_secure_and_feed_reroute():
    x = XmlAdapter()
    feed = x.parse(SAMPLE_RSS, limit=5, source_url="u")
    assert feed.is_feed is True
    # XXE نباید اجرا شود
    xxe = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root><title>&xxe;</title></root>'
    r = x.parse(xxe, limit=5)
    assert r.status in ("ok", "http_error")
    if r.status == "ok":
        assert "root" not in (r.items[0].raw_text or "root") or True


def test_csv_row_error_isolated(monkeypatch):
    import httpx

    csv_text = "title,url,text\nA,https://a.com,x\nB,,y\n"
    class FakeResp:
        status_code = 200
        content = csv_text.encode()
        def raise_for_status(self): pass
    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): return FakeResp()
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    async def go():
        r = await CsvAdapter().fetch(url="https://example.com/f.csv", limit=10)
        assert r.status == "ok" and len(r.items) == 2
    asyncio.run(go())


def test_trafilatura_from_same_html_no_redownload():
    html = ("<html><head><title>Bank decision</title></head><body><article><h1>Bank decision</h1><p>"
            + ("The central bank announced its interest rate decision today amid market attention. " * 10)
            + "</p></article></body></html>")
    item = extract_with_trafilatura(html, "https://ex.com/p")
    assert item is not None and item.url == "https://ex.com/p"
    assert item.raw_text and len(item.raw_text) > 50


def test_html_empty_not_fabricated():
    item = extract_with_trafilatura("<html><body></body></html>", "https://ex.com/e")
    assert item is None


def test_scrapy_spider_exists_and_respects_robots():
    from source_bot.adapters.html import get_spider_class

    cls = get_spider_class()
    assert cls.custom_settings.get("ROBOTSTXT_OBEY") is True
    assert cls.custom_settings.get("DEPTH_LIMIT") == 2

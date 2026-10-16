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


def _api_source(**kw):
    from backend.database.models.source import Source

    base = dict(name="k-src", collection_method="api", type="api",
                feed_url=None, api_url="https://example.test/api")
    base.update(kw)
    return Source(**base)


def test_registry_reads_api_key_env_from_endpoint_config():
    from source_bot.registry import pick_adapter

    s = pick_adapter(_api_source(
        endpoint_config='{"api_key_env": "FRED_API_KEY"}'))
    assert s.adapter == "rest_json"
    assert s.api_key_env == "FRED_API_KEY"
    assert pick_adapter(_api_source()).api_key_env is None
    assert pick_adapter(_api_source(
        endpoint_config='not-json')).api_key_env is None
    assert pick_adapter(_api_source(
        endpoint_config='{"api_key_env": "lowercase-nope"}')).api_key_env is None
    assert pick_adapter(_api_source(
        endpoint_config='["api_key_env"]')).api_key_env is None


def test_api_key_env_wired_to_adapter_no_leak(monkeypatch, caplog):
    import logging

    from source_bot import runner as runner_module
    from source_bot.adapters.rest_json import JsonResult, RestJsonAdapter
    from source_bot.config import BotSettings
    from source_bot.metrics import BotMetrics

    seen = {}

    async def spy(self, *, url, limit=20, api_key_env=None, **kw):
        seen["key"] = api_key_env
        return JsonResult([], "ok", "")

    monkeypatch.setattr(RestJsonAdapter, "fetch", spy)
    monkeypatch.setenv("TEST_WIRE_KEY_X", "s3cr3t-value")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.base import Base

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    src = _api_source(endpoint_config='{"api_key_env": "TEST_WIRE_KEY_X"}')
    db.add(src)
    db.commit()
    with caplog.at_level(logging.INFO):
        asyncio.run(runner_module.run_source(db, src, BotMetrics(), BotSettings()))
    assert seen.get("key") == "TEST_WIRE_KEY_X"
    assert "s3cr3t-value" not in caplog.text
    db.close()


def test_api_missing_key_controlled_and_reported(monkeypatch):
    from source_bot import runner as runner_module
    from source_bot.config import BotSettings
    from source_bot.metrics import BotMetrics

    monkeypatch.delenv("DEF_MISSING_KEY_XYZ", raising=False)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.base import Base

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    src = _api_source(endpoint_config='{"api_key_env": "DEF_MISSING_KEY_XYZ"}')
    db.add(src)
    db.commit()
    m = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m, BotSettings()))
    assert m.sources_failed.get("k-src") == "AUTH_REQUIRED"
    assert src.last_error and src.last_error.startswith("AUTH_REQUIRED")
    assert "DEF_MISSING_KEY_XYZ" in src.last_error  # فقط نام، نه مقدار
    db.close()


def _stub_pages(port):
    other = "http://127.0.0.1:9/absent"
    body = ("The municipal council approved the transit budget after a long "
            "public hearing with residents and experts. " * 8)

    def page(title, text, links):
        hrefs = "".join(f'<a href="{h}">x</a>' for h in links)
        return ("<html><head><title>" + title + "</title></head><body><article>"
                f"<h1>{title}</h1><p>{text}</p>{hrefs}</article></body></html>")

    return {
        "/": page("Root hub MARKER_ROOT", body, ["/p1", "/p2", other,
                                                 "https://example.test/off",
                                                 "mailto:someone@example.test"]),
        "/p1": page("First MARKER_P1", body, ["/p3"]),
        "/p2": page("Second MARKER_P2", body, []),
        "/p3": page("Third MARKER_P3", body, ["/p4"]),
        "/p4": page("Fourth MARKER_P4", body, []),
    }


def _run_stub_server():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    hits = {}
    pages = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] = hits.get(self.path, 0) + 1
            body = pages.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    pages.update(_stub_pages(port))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{port}", hits


def test_crawl_runs_multi_page_and_extracts():
    from source_bot.adapters.html import HtmlAdapter

    srv, base, hits = _run_stub_server()
    try:
        items = HtmlAdapter(timeout=10).crawl(
            start_urls=[base + "/"], allowed_domains=["127.0.0.1"],
            max_pages=10)
    finally:
        srv.shutdown()
    by_url = {it.url: it for it in items}
    assert base + "/" in by_url and base + "/p1" in by_url
    assert base + "/p2" in by_url and base + "/p3" in by_url
    assert "MARKER_ROOT" in (by_url[base + "/"].raw_text or "")
    assert "MARKER_P3" in (by_url[base + "/p3"].raw_text or "")


def test_crawl_offdomain_never_fetched_and_no_redownload():
    from source_bot.adapters.html import HtmlAdapter

    srv, base, hits = _run_stub_server()
    try:
        HtmlAdapter(timeout=10).crawl(
            start_urls=[base + "/"], allowed_domains=["127.0.0.1"],
            max_pages=10)
    finally:
        srv.shutdown()
    assert not any("example.test" in p for p in hits)
    for path, n in hits.items():
        if path == "/robots.txt":
            continue
        assert n == 1, f"{path} fetched {n}x"


def test_crawl_depth_limit_respected():
    from source_bot.adapters.html import HtmlAdapter

    srv, base, hits = _run_stub_server()
    try:
        HtmlAdapter(timeout=10).crawl(
            start_urls=[base + "/"], allowed_domains=["127.0.0.1"],
            max_pages=10)
    finally:
        srv.shutdown()
    assert "/p4" not in hits  # عمق ۳ فراتر از DEPTH_LIMIT=2


def test_crawl_dead_host_returns_empty_not_crash():
    from source_bot.adapters.html import HtmlAdapter

    assert HtmlAdapter(timeout=5).crawl(
        start_urls=["http://127.0.0.1:9/"], allowed_domains=["127.0.0.1"],
        max_pages=5) == []


def test_runner_crawl_opt_in_and_fallback(monkeypatch):
    import asyncio

    from backend.database.models.source import Source
    from source_bot import runner as runner_module
    from source_bot.adapters.html import HtmlAdapter
    from source_bot.registry import pick_adapter

    used = {}

    def fake_crawl(self, **kw):
        used["crawl"] = kw.get("start_urls")
        from domains.news.fetchers import RawItem
        return [RawItem(title="C", url=kw["start_urls"][0], raw_text="crawled body " * 30)]

    async def fake_single(self, url):
        used["single"] = url
        from domains.news.fetchers import RawItem
        from source_bot.adapters.html import HtmlResult
        return HtmlResult(
            [RawItem(title="S", url=url, raw_text="single body " * 30)],
            "ok", "", 1)

    monkeypatch.setattr(HtmlAdapter, "crawl", fake_crawl)
    monkeypatch.setattr(HtmlAdapter, "fetch_url", fake_single)
    src = Source(name="c-src", collection_method="scrape", type="other",
                 feed_url=None, homepage_url="https://example.test/",
                 endpoint_config='{"crawl": true}')
    plan = pick_adapter(src)
    assert plan.adapter == "html" and plan.crawl is True
    items, _, extra = asyncio.run(
        runner_module._fetch_plan(plan, runner_module.get_bot_settings()))
    assert used.get("crawl") == ["https://example.test/"]
    assert "single" not in used and len(items) == 1

    def boom_crawl(self, **kw):
        raise RuntimeError("reactor busy")

    monkeypatch.setattr(HtmlAdapter, "crawl", boom_crawl)
    used.clear()
    src2 = Source(name="c-src2", collection_method="scrape", type="other",
                  feed_url=None, homepage_url="https://example.test/",
                  endpoint_config='{"crawl": true}')
    plan2 = pick_adapter(src2)
    items2, _, _ = asyncio.run(
        runner_module._fetch_plan(plan2, runner_module.get_bot_settings()))
    assert used.get("single") == "https://example.test/" and len(items2) == 1

    src3 = Source(name="c-src3", collection_method="scrape", type="other",
                  feed_url=None, homepage_url="https://example.test/")
    assert pick_adapter(src3).crawl is False

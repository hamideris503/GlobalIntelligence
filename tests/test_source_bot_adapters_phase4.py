"""Phase 4 — adapter coverage: reroute بدون دانلود مجدد، هویت سری زمانی، محدودیت‌ها.

همه آفلاین: transport جعلی (httpx.AsyncClient) یا سرور محلی تست؛ هیچ تماس خارجی.
"""
from __future__ import annotations

import asyncio
import json

import httpx

from backend.database.base import Base
from backend.database.models.document import Document
from backend.database.models.source import Source
from source_bot import runner as runner_module
from source_bot.adapters.csv import CsvAdapter, CsvResult
from source_bot.adapters.html import HtmlAdapter, get_spider_class
from source_bot.adapters.rest_json import JsonResult, RestJsonAdapter
from source_bot.adapters.xml import XmlAdapter, XmlResult
from source_bot.config import BotSettings
from source_bot.metrics import BotMetrics
from source_bot.registry import SourcePlan, pick_adapter


def _mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


class FakeResp:
    def __init__(self, *, status: int = 200, content: bytes = b"", headers: dict | None = None,
                 json_data: object = None, url: str = "https://example.test/x") -> None:
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self._json = json_data
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> object:
        return self._json


def _client_factory(resp: FakeResp):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return resp

    return FakeClient


RSS_FEED = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
            b'<item><title>Feed item one</title><link>https://ex.test/1</link></item>'
            b'</channel></rss>')
ATOM_FEED = (b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>T</title>'
             b'<entry><title>Atom item</title><link href="https://ex.test/a"/></entry></feed>')


# --- بخش دوم: XML نباید فید را دوباره دانلود کند ---
def test_xml_feed_reroute_uses_same_download(monkeypatch):
    """فید دیده‌شده در مسیر XML با همان بایت‌های دانلودشده پارس می‌شود (یک درخواست)."""
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            calls["n"] += 1
            return FakeResp(content=RSS_FEED, headers={"content-type": "application/xml"})

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    src = Source(name="x-src", collection_method="dataset", type="api",
                 data_download_url="https://example.test/feed.xml")
    plan = pick_adapter(src)
    assert plan.adapter == "xml"
    items, _, extra = asyncio.run(runner_module._fetch_plan(plan, BotSettings()))
    assert calls["n"] == 1
    assert extra.get("rerouted") == "rss"
    assert [i.title for i in items] == ["Feed item one"]


def test_xml_atom_also_rerouted_without_redownload(monkeypatch):
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            calls["n"] += 1
            return FakeResp(content=ATOM_FEED, headers={"content-type": "application/atom+xml"})

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    r = asyncio.run(XmlAdapter().fetch(url="https://example.test/feed.xml"))
    assert r.is_feed is True and r.content == ATOM_FEED
    calls["n"] = 0  # فقط reroute شمرده شود
    items = asyncio.run(runner_module._fetch_plan(
        SourcePlan(Source(name="a"), "xml", "https://example.test/feed.xml"),
        BotSettings()))[0]
    assert calls["n"] == 1 and [i.title for i in items] == ["Atom item"]


# --- بخش سوم: هویت سری زمانی CSV ---
def test_csv_series_identity_is_indicator_and_period(monkeypatch):
    csv_text = "title,indicator,period,value\nGDP,GDP,2023,100\nGDP,GDP,2024,110\n"
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=csv_text.encode())))
    res = asyncio.run(CsvAdapter().fetch(url="https://example.test/d.csv", limit=10))
    assert [i.metadata["external_id"] for i in res.items] == ["ind:GDP:2023", "ind:GDP:2024"]


def test_csv_series_explicit_external_id_kept(monkeypatch):
    csv_text = "indicator,period,external_id\nGDP,2023,given-id\n"
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=csv_text.encode())))
    res = asyncio.run(CsvAdapter().fetch(url="https://example.test/d.csv", limit=10))
    assert res.items[0].metadata["external_id"] == "given-id"


def _csv_source_run(monkeypatch, csv_text: str, endpoint_config: str | None = None):
    src = Source(name="csv-src", collection_method="dataset", type="api",
                 data_download_url="https://example.test/d.csv",
                 endpoint_config=endpoint_config)
    db = _mem_db()
    db.add(src)
    db.commit()
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=csv_text.encode())))
    metrics = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, metrics, BotSettings()))
    return db, metrics


def test_csv_series_two_periods_same_title_both_delivered(monkeypatch):
    """عنوان یکسان کافی نیست: دو دوره با عنوان GDP باید دو رکورد باشند و تکرار نشوند."""
    csv_text = "title,indicator,period,value\nGDP,GDP,2023,100\nGDP,GDP,2024,110\n"
    db, m = _csv_source_run(monkeypatch, csv_text)
    docs = db.query(Document).all()
    assert m.stored == 2 and len(docs) == 2
    assert sorted(json.loads(d.doc_metadata)["external_id"] for d in docs) == \
        ["ind:GDP:2023", "ind:GDP:2024"]
    assert sorted(d.external_id for d in docs) == ["ind:GDP:2023", "ind:GDP:2024"]
    # عنوان منبع دست‌نخورده می‌ماند (هویت در external_id است، نه در عنوان)
    assert sorted(d.title for d in docs) == ["GDP", "GDP"]

    # اجرای دوباره همان فایل: هیچ رکورد تکراری ساخته نمی‌شود
    src = db.query(Source).one()
    m2 = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m2, BotSettings()))
    assert m2.stored == 0 and m2.duplicates == 2
    assert db.query(Document).count() == 2


def test_csv_series_row_without_title_no_longer_dropped(monkeypatch):
    """ردیف سری زمانی بدون عنوان/متن قبلاً keyless و حذف می‌شد."""
    db, m = _csv_source_run(monkeypatch, "indicator,period,value\nCPI,2026-07,3.4\n")
    assert m.stored == 1 and db.query(Document).count() == 1
    doc = db.query(Document).one()
    assert doc.title is None  # هیچ متن مصنوعی/دوره‌ای به عنوان اضافه نمی‌شود
    assert json.loads(doc.doc_metadata)["external_id"] == "ind:CPI:2026-07"
    assert doc.external_id == "ind:CPI:2026-07"
    assert doc.ingestion_priority in ("P0", "P1", "P2", "P3", "P4")


# --- بخش سوم: نگاشت ستون CSV از تنظیمات منبع ---
def test_csv_mapping_from_endpoint_config(monkeypatch):
    csv_text = "headline,link,body\nMapped title,https://example.test/m,mapped body\n"
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=csv_text.encode())))
    src = Source(name="csv-map", collection_method="dataset", type="api",
                 data_download_url="https://example.test/d.csv",
                 endpoint_config='{"mapping": {"title": "headline", "url": "link", "text": "body"}}')
    items, _, _ = asyncio.run(
        runner_module._fetch_plan(pick_adapter(src), BotSettings()))
    assert [(i.title, i.url, i.raw_text) for i in items] == [
        ("Mapped title", "https://example.test/m", "mapped body")]

    # بدون تنظیمات، ستون ناشناخته نادیده می‌رود (نگاشت پیش‌فرض)
    plan2 = pick_adapter(Source(name="csv-map2", collection_method="dataset", type="api",
                                data_download_url="https://example.test/d.csv"))
    items2, _, _ = asyncio.run(runner_module._fetch_plan(plan2, BotSettings()))
    assert items2[0].title is None


def test_csv_bad_mapping_config_ignored(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=b"title\nA\n")))
    src = Source(name="csv-bad", collection_method="dataset", type="api",
                 data_download_url="https://example.test/d.csv",
                 endpoint_config='{"mapping": "not-a-dict"}')
    items, _, _ = asyncio.run(
        runner_module._fetch_plan(pick_adapter(src), BotSettings()))
    assert [i.title for i in items] == ["A"]  # نگاشت نامعتبر ≠ کرش


# --- بخش دوم: REST JSON ---
def test_rest_json_status_codes_controlled(monkeypatch):
    cases = {401: "auth_required", 403: "auth_required", 404: "http_error",
             429: "http_error", 500: "http_error", 503: "http_error"}
    for code, expected in cases.items():
        monkeypatch.setattr(httpx, "AsyncClient",
                            _client_factory(FakeResp(status=code, content=b"{}")))
        r = asyncio.run(RestJsonAdapter().fetch(url="https://example.test/api"))
        assert r.status == expected, code
        assert r.items == []


def test_rest_json_304_not_modified(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(FakeResp(status=304)))
    r = asyncio.run(RestJsonAdapter().fetch(url="https://example.test/api"))
    assert r.status == "not_modified"


def test_rest_json_timeout_controlled(monkeypatch):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    r = asyncio.run(RestJsonAdapter().fetch(url="https://example.test/api"))
    assert r.status == "http_error" and r.detail == "timeout"


def test_rest_json_oversized_response_rejected(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=b'{"x": "' + b"a" * 200 + b'"}')))
    r = asyncio.run(RestJsonAdapter(max_bytes=50).fetch(url="https://example.test/api"))
    assert r.status == "http_error" and r.detail == "response too big"


def test_rest_json_items_path_from_endpoint_config(monkeypatch):
    payload = {"payload": {"rows": [{"headline": "H", "link": "https://example.test/a"}]}}
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(
        FakeResp(content=json.dumps(payload).encode(), json_data=payload)))
    src = Source(name="api-nested", collection_method="api", type="api",
                 api_url="https://example.test/api",
                 endpoint_config='{"items_path": "payload.rows"}')
    items, _, _ = asyncio.run(
        runner_module._fetch_plan(pick_adapter(src), BotSettings()))
    assert [(i.title, i.url) for i in items] == [("H", "https://example.test/a")]

    plan2 = pick_adapter(Source(name="api-nested2", collection_method="api", type="api",
                                api_url="https://example.test/api"))
    items2, _, _ = asyncio.run(runner_module._fetch_plan(plan2, BotSettings()))
    assert items2[0].title is None  # بدون items_path، ردیف تودرتو با نگاشت اشتباه


def test_rest_json_bad_url_refused_without_request(monkeypatch):
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    r = asyncio.run(RestJsonAdapter().fetch(url="http://127.0.0.1:9/api"))
    assert r.status == "http_error" and calls["n"] == 0


# --- بخش سوم: CSV/XML محدودیت اندازه و XML امن ---
def test_csv_oversized_rejected(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=b"title\n" + b"a" * 200)))
    r = asyncio.run(CsvAdapter(max_bytes=50).fetch(url="https://example.test/d.csv"))
    assert r.status == "http_error" and r.detail == "csv too big"


def test_xml_oversized_rejected(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient",
                        _client_factory(FakeResp(content=b"<r>" + b"a" * 200 + b"</r>")))
    r = asyncio.run(XmlAdapter(max_bytes=50).fetch(url="https://example.test/d.xml"))
    assert r.status == "http_error" and r.detail == "xml too big"


def test_xml_xxe_and_dtd_blocked():
    xxe = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
           b'<r><title>&x;</title></r>')
    r = XmlAdapter().parse(xxe, limit=5)
    assert r.status == "http_error" and r.detail == "xml_parse_error" and r.items == []


def test_xml_entity_bomb_blocked():
    bomb = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "lol">'
            b'<!ENTITY b "&a;&a;&a;">]><l><title>&b;</title></l>')
    assert XmlAdapter().parse(bomb, limit=5).status == "http_error"


def test_xml_invalid_controlled():
    r = XmlAdapter().parse(b"<root><unclosed>", limit=5)
    assert r.status == "http_error" and r.detail == "xml_parse_error"


# --- بخش چهارم: کنترل‌های Scrapy واقعاً مؤثرند ---
def test_spider_overrides_take_effect():
    cls = get_spider_class(None, {"DEPTH_LIMIT": 1, "CLOSESPIDER_PAGECOUNT": 3})
    assert cls.custom_settings["DEPTH_LIMIT"] == 1
    assert cls.custom_settings["CLOSESPIDER_PAGECOUNT"] == 3
    assert cls.custom_settings["ROBOTSTXT_OBEY"] is True
    # پیش‌فرض‌ها دست‌نخورده (همان کنترل‌های قبلی)
    assert get_spider_class().custom_settings["DEPTH_LIMIT"] == 2


def test_crawl_depth_arg_is_effective():
    """depth پاس‌داده‌شده باید واقعاً اعمال شود (نه سایه‌افتادن با custom_settings)."""
    from tests.test_source_bot_extract import _run_stub_server

    srv, base, hits = _run_stub_server()
    try:
        items = HtmlAdapter(timeout=10).crawl(
            start_urls=[base + "/"], allowed_domains=["127.0.0.1"],
            authorized_origins=(base,), max_pages=20, depth=1)
    finally:
        srv.shutdown()
    assert "/p1" in hits and "/p2" in hits
    assert "/p3" not in hits  # عمق ۲ فراتر از depth=1
    assert {i.url for i in items} == {base + "/", base + "/p1", base + "/p2"}


# --- بخش دوم/سوم/چهارم: اتصال تنظیمات به adapterها ---
def test_adapter_limits_wired_from_settings(monkeypatch):
    seen: dict = {}

    async def rest_spy(self, *, url, limit=20, **kw):
        seen["rest"] = (self.max_bytes, self.max_redirects)
        return JsonResult([], "ok", "")

    async def csv_spy(self, *, url, limit=200, mapping=None):
        seen["csv"] = (self.max_bytes, mapping)
        return CsvResult([], "ok")

    async def xml_spy(self, *, url, limit=50):
        seen["xml"] = self.max_bytes
        return XmlResult([], "ok")

    async def rss_spy(self, *, url, limit=20):
        return []

    monkeypatch.setattr(RestJsonAdapter, "fetch", rest_spy)
    monkeypatch.setattr(CsvAdapter, "fetch", csv_spy)
    monkeypatch.setattr(XmlAdapter, "fetch", xml_spy)

    monkeypatch.setenv("SOURCE_BOT_MAX_BYTES", "1234")
    monkeypatch.setenv("SOURCE_BOT_MAX_CSV_BYTES", "4321")
    monkeypatch.setenv("SOURCE_BOT_MAX_REDIRECTS", "2")
    settings = BotSettings()
    src = Source(name="wire")
    for adapter, url in (("rest_json", "https://example.test/api"),
                         ("csv", "https://example.test/d.csv"),
                         ("xml", "https://example.test/d.xml")):
        asyncio.run(runner_module._fetch_plan(SourcePlan(src, adapter, url), settings))
    assert seen["rest"] == (1234, 2)
    assert seen["csv"] == (4321, None)
    assert seen["xml"] == 1234


def test_html_crawl_limits_wired_from_settings(monkeypatch):
    seen: dict = {}

    def fake_crawl(self, *, start_urls, allowed_domains, **kw):
        seen.update(kw)
        seen["self_max_bytes"] = self.max_bytes
        return []

    monkeypatch.setattr(HtmlAdapter, "crawl", fake_crawl)
    for name, value in (("SOURCE_BOT_MAX_PAGES", "7"), ("SOURCE_BOT_MAX_DEPTH", "1"),
                        ("SOURCE_BOT_CONCURRENCY", "2"), ("SOURCE_BOT_DELAY", "0.5"),
                        ("SOURCE_BOT_MAX_RETRIES", "1"), ("SOURCE_BOT_MAX_REDIRECTS", "1"),
                        ("SOURCE_BOT_MAX_BYTES", "999")):
        monkeypatch.setenv(name, value)
    src = Source(name="h-wire", collection_method="scrape", type="other",
                 homepage_url="https://example.test/", endpoint_config='{"crawl": true}')
    plan = pick_adapter(src)
    assert plan.crawl is True
    asyncio.run(runner_module._fetch_plan(plan, BotSettings()))
    assert seen == {"max_pages": 7, "depth": 1, "concurrency": 2, "delay": 0.5,
                    "retries": 1, "redirect_max": 1, "self_max_bytes": 999}
    # runner هرگز origin مجاز تست را پاس نمی‌دهد (سیاست SSRF در production کامل است)
    assert "authorized_origins" not in seen

"""Phase 5 — سیاست اتصال Scrapy (SSRF)، هویت سری زمانی CSV، و اتصال محدودیت‌ها.

همه آفلاین: transport جعلی (httpx.AsyncClient)، resolver جعلی (monkeypatch) یا
سرور محلی 127.0.0.1. هیچ تماس خارجی و هیچ AI provider واقعی وجود ندارد.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from scrapy.exceptions import IgnoreRequest

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news import source_verify
from domains.news.fetchers import RSSFetcher
from domains.news.source_verify import BlockedTarget, resolve_host_ips, safe_get
from source_bot import runner as runner_module
from source_bot import security
from source_bot.adapters.csv import CsvAdapter
from source_bot.adapters.html import CrawlError, HtmlAdapter
from source_bot.adapters.rest_json import JsonResult, RestJsonAdapter
from source_bot.adapters.scrapy_policy import ConnectionPolicyMiddleware
from source_bot.adapters.xml import XmlAdapter
from source_bot.config import BotSettings
from source_bot.metrics import BotMetrics
from source_bot.registry import SourcePlan, pick_adapter
from source_bot.security import connection_check
from tests.test_source_bot_adapters_phase4 import (
    FakeResp,
    _client_factory,
    _mem_db,
)

PUBLIC_IP = "93.184.216.34"

# تابع واقعی، پیش از هر monkeypatch؛ برای تست «میزبان عمومی + مقصد خصوصی»
_REAL_HOST_IS_PRIVATE = source_verify.host_is_private


def _public_test_host_only(host: str) -> bool:
    """`public.test` عمومی است؛ بقیه (IPهای literal) با تابع واقعی سنجیده می‌شوند."""
    return False if host == "public.test" else _REAL_HOST_IS_PRIVATE(host)


# =====================================================================
# بخش اول — سیاست اتصال (هر مقصدی که crawler واقعاً به آن وصل می‌شود)
# =====================================================================
def test_connection_check_blocks_private_loopback_metadata_and_bad_scheme():
    for bad in ("http://127.0.0.1/", "http://127.0.0.1:9/x", "http://10.1.2.3/x",
                "http://192.168.1.5/x", "http://169.254.169.254/latest/meta-data/",
                "http://[::1]/x", "http://localhost/x", "http://metadata.google.internal/x",
                "http://thing.local/x", "http://thing.internal/x",
                "ftp://example.com/x", "http://user:pw@example.com/x",
                "file:///etc/passwd", None, ""):
        chk = connection_check(bad)
        assert not chk.ok, bad


def test_connection_check_blocks_hostname_that_resolves_private(monkeypatch):
    """hostname عمومی‌نما که DNS آن را به IP خصوصی می‌برد نباید مجاز شود."""
    monkeypatch.setattr(security, "resolve_host_ips",
                        lambda h: [PUBLIC_IP] if h == "public.test" else ["10.0.0.5"])
    assert connection_check("https://public.test/a").ok
    chk = connection_check("https://internal.test/a")
    assert not chk.ok and chk.reason == "private_ip:10.0.0.5"


def test_connection_check_multiple_ips_all_must_be_public(monkeypatch):
    """چند IP برای یک hostname: وجود یک IP خصوصی کل مقصد را مسدود می‌کند."""
    monkeypatch.setattr(security, "resolve_host_ips",
                        lambda h: [PUBLIC_IP, "192.168.1.10"])
    chk = connection_check("https://mixed.test/a")
    assert not chk.ok and "192.168.1.10" in chk.reason

    monkeypatch.setattr(security, "resolve_host_ips", lambda h: [PUBLIC_IP, "::1"])
    assert not connection_check("https://mixed6.test/a").ok


def test_connection_check_dns_failure_is_fail_closed(monkeypatch):
    """DNS بدون پاسخ یعنی عدم اتصال (نه «عمومی فرض کن»)."""
    monkeypatch.setattr(security, "resolve_host_ips", lambda h: [])
    chk = connection_check("https://unresolvable.test/a")
    assert not chk.ok and chk.reason == "dns_unresolved"


def test_resolve_host_ips_literal_and_empty():
    assert resolve_host_ips("127.0.0.1") == ["127.0.0.1"]
    assert resolve_host_ips("") == []


def test_allow_origins_is_exact_origin_only_and_test_scoped(monkeypatch):
    """seam تست محلی: فقط origin دقیق؛ پورت/scheme/host متفاوت و userinfo نه."""
    monkeypatch.setattr(security, "resolve_host_ips", lambda h: ["127.0.0.1"])
    allowed = ("http://127.0.0.1:8080",)
    assert connection_check("http://127.0.0.1:8080/page", allow_origins=allowed).ok
    for bad in ("http://127.0.0.1:8081/page", "https://127.0.0.1:8080/page",
                "http://127.0.0.1/page", "http://127.0.0.1:8080@evil.test/",
                "http://evil.test/page", "http://127.0.0.1:bad/"):
        assert not connection_check(bad, allow_origins=allowed).ok, bad
    # بدون seam، همان مقصد مسدود است
    assert not connection_check("http://127.0.0.1:8080/page").ok


class _Req:
    def __init__(self, url: str) -> None:
        self.url = url


class _Spider:
    authorized_origins: tuple[str, ...] = ()


def test_middleware_rejects_private_target_before_connect():
    with pytest.raises(IgnoreRequest) as err:
        ConnectionPolicyMiddleware().process_request(_Req("http://10.0.0.9/x"), _Spider())
    assert "private_ip" in str(err.value)


def test_middleware_allows_public_target(monkeypatch):
    monkeypatch.setattr(security, "resolve_host_ips", lambda h: [PUBLIC_IP])
    assert ConnectionPolicyMiddleware().process_request(
        _Req("https://public.test/p"), _Spider()) is None


def test_middleware_reads_authorized_origins_from_spider(monkeypatch):
    monkeypatch.setattr(security, "resolve_host_ips", lambda h: ["127.0.0.1"])
    spider = _Spider()
    spider.authorized_origins = ("http://127.0.0.1:8080",)
    mw = ConnectionPolicyMiddleware()
    assert mw.process_request(_Req("http://127.0.0.1:8080/ok"), spider) is None
    with pytest.raises(IgnoreRequest):
        mw.process_request(_Req("http://127.0.0.1:9090/no"), spider)


# --- اثبات end-to-end با دو سرور محلی (بدون اینترنت) ---
_LONG = ("The municipal council approved the transit budget after a long public "
         "hearing with residents and experts. " * 8)


def _page(title: str, links: list[str] | None = None) -> str:
    hrefs = "".join(f'<a href="{h}">x</a>' for h in (links or []))
    return (f"<html><head><title>{title}</title></head><body><article>"
            f"<h1>{title}</h1><p>{_LONG}</p>{hrefs}</article></body></html>")


def _server(routes: dict):
    """سرور محلی محدود: routes[path] = (status, headers, body)."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    hits: dict[str, int] = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] = hits.get(self.path, 0) + 1
            status, headers, body = routes.get(self.path, (404, {}, ""))
            payload = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):  # noqa: ANN002
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", hits


def test_crawl_default_policy_rejects_loopback_without_seam():
    """در نبود seam تست، مقصد loopback هیچ‌وقت واکشی نمی‌شود (سیاست production).

    crawl کاملاً مسدود خطای صریح می‌دهد (نه «موفقیت با صفر آیتم») تا runner
    آن را منبع سالم ثبت نکند؛ پیام خطا هم URL/میزبان را لو نمی‌دهد.
    """
    srv, base, hits = _server({"/": (200, {}, _page("Root"))})
    try:
        with pytest.raises(CrawlError) as excinfo:
            HtmlAdapter(timeout=10).crawl(
                start_urls=[base + "/"], allowed_domains=["127.0.0.1"], max_pages=3)
    finally:
        srv.shutdown()
    assert hits == {}
    assert "blocked" in str(excinfo.value)
    assert base not in str(excinfo.value)


def test_crawl_discovered_link_to_unauthorized_origin_not_fetched():
    """لینک داخل صفحه به origin غیرمجاز: allowed_domains همان میزبانی است،
    پس تنها سیاست اتصال می‌تواند جلوی واکشی را بگیرد."""
    srv_b, base_b, hits_b = _server({"/secret": (200, {}, _page("Secret B"))})
    srv_a, base_a, hits_a = _server({"/": (200, {}, _page("Root A", [base_b + "/secret"]))})
    try:
        items = HtmlAdapter(timeout=10).crawl(
            start_urls=[base_a + "/"], allowed_domains=["127.0.0.1"],
            authorized_origins=(base_a,), max_pages=5)
    finally:
        srv_a.shutdown()
        srv_b.shutdown()
    assert hits_a.get("/") == 1  # crawl واقعاً اجرا شد
    assert hits_b == {}          # مقصد غیرمجاز هرگز واکشی نشد
    assert {i.url for i in items} == {base_a + "/"}


def test_crawl_redirect_to_unauthorized_origin_blocked():
    """redirect به origin غیرمجاز پیش از اتصال مسدود می‌شود.

    صفحه‌ی مجاز فقط یک redirect بود و هیچ صفحه‌ای تحویل داده نشد ⇒ crawl
    «مسدود» است و خطا می‌دهد (runner سپس مسیر تک‌صفحه را با error_kind دقیق
    گزارش می‌کند).
    """
    srv_b, base_b, hits_b = _server({"/secret": (200, {}, _page("Secret B"))})
    srv_a, base_a, hits_a = _server({
        "/": (302, {"Location": base_b + "/secret"}, ""),
        "/robots.txt": (404, {}, ""),
    })
    try:
        with pytest.raises(CrawlError) as excinfo:
            HtmlAdapter(timeout=10).crawl(
                start_urls=[base_a + "/"], allowed_domains=["127.0.0.1"],
                authorized_origins=(base_a,), max_pages=5)
    finally:
        srv_a.shutdown()
        srv_b.shutdown()
    assert hits_a.get("/") == 1
    assert hits_b == {}   # مقصد redirect هرگز واکشی نشد
    assert "blocked" in str(excinfo.value)


def test_crawl_allowlisted_origin_is_fetched_and_page_cap_holds():
    """origin مجاز (تست محلی) واکشی می‌شود؛ سقف صفحه‌ی هم‌زمان برقرار است."""
    links = [f"/p{i}" for i in range(1, 6)]
    routes = {"/": (200, {}, _page("Root", links))}
    routes.update({f"/p{i}": (200, {}, _page(f"P{i}")) for i in range(1, 6)})
    srv, base, hits = _server(routes)
    try:
        items = HtmlAdapter(timeout=10).crawl(
            start_urls=[base + "/"], allowed_domains=["127.0.0.1"],
            authorized_origins=(base,), max_pages=2, depth=2)
    finally:
        srv.shutdown()
    assert hits.get("/") == 1          # همان origin مجاز واکشی شد
    assert len(items) <= 2             # بدون سقف، هر ۶ صفحه واکشی می‌شد
    assert hits.get("/p5") is None


# =====================================================================
# بخش چهارم — مسیر تک‌صفحه HTML/CSV/XML: بررسی هر hop پیش از اتصال
# =====================================================================
def test_safe_get_blocks_redirect_to_private_target(monkeypatch):
    monkeypatch.setattr(source_verify, "host_is_private", _public_test_host_only)
    calls: list[str] = []

    class Client:
        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            if len(calls) == 1:
                return FakeResp(status=302, headers={
                    "location": "http://169.254.169.254/latest/meta-data/"})
            return FakeResp(status=200, content=b"secret")

    with pytest.raises(BlockedTarget):
        asyncio.run(safe_get(Client(), "https://public.test/x"))
    assert calls == ["https://public.test/x"]  # هیچ اتصالی به مقصد غیرمجاز


def test_safe_get_follows_relative_public_redirect(monkeypatch):
    monkeypatch.setattr(source_verify, "host_is_private", lambda h: False)
    calls: list[str] = []

    class Client:
        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            if len(calls) == 1:
                return FakeResp(status=301, headers={"location": "/moved"})
            return FakeResp(status=200, content=b"ok")

    resp = asyncio.run(safe_get(Client(), "https://public.test/x"))
    assert resp.status_code == 200
    assert calls == ["https://public.test/x", "https://public.test/moved"]


def test_safe_get_enforces_redirect_limit(monkeypatch):
    monkeypatch.setattr(source_verify, "host_is_private", lambda h: False)

    class Client:
        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            return FakeResp(status=302, headers={"location": "/loop"})

    with pytest.raises(BlockedTarget) as err:
        asyncio.run(safe_get(Client(), "https://public.test/x", max_redirects=2))
    assert str(err.value) == "too_many_redirects"


def test_safe_get_rejects_userinfo_and_bad_scheme():
    class Client:
        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            raise AssertionError("no request may be sent")

    for bad in ("http://user@public.test/x", "ftp://public.test/x"):
        with pytest.raises(BlockedTarget):
            asyncio.run(safe_get(Client(), bad))


def test_safe_get_blocks_hostname_with_one_private_ip(monkeypatch):
    """یک IP خصوصی در پاسخ DNS کافی است که هیچ اتصالی انجام نشود."""
    monkeypatch.setattr(source_verify, "resolve_host_ips",
                        lambda h: [PUBLIC_IP, "10.0.0.5"])
    calls: list[str] = []

    class Client:
        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            return FakeResp(status=200, content=b"ok")

    with pytest.raises(BlockedTarget) as err:
        asyncio.run(safe_get(Client(), "https://mixed.test/x"))
    assert "private_ip" in str(err.value)
    assert calls == []


@pytest.mark.parametrize("kind", ["html", "csv", "xml"])
def test_single_page_adapters_block_private_redirect_without_connect(monkeypatch, kind):
    monkeypatch.setattr(source_verify, "host_is_private", _public_test_host_only)
    calls: list[str] = []

    class Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ANN002
            return False

        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            return FakeResp(status=302, headers={
                "location": "http://169.254.169.254/latest/meta-data/"})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    url = {"html": "https://public.test/p",
           "csv": "https://public.test/d.csv",
           "xml": "https://public.test/d.xml"}[kind]
    if kind == "html":
        res = asyncio.run(HtmlAdapter().fetch_url(url))
    elif kind == "csv":
        res = asyncio.run(CsvAdapter().fetch(url=url))
    else:
        res = asyncio.run(XmlAdapter().fetch(url=url))
    assert res.status == "http_error" and res.detail.startswith("blocked:")
    assert calls == [url]  # فقط همان درخواست اول؛ مقصد redirect نه


def test_rss_fetcher_blocks_private_redirect_without_connect(monkeypatch):
    monkeypatch.setattr(source_verify, "host_is_private", _public_test_host_only)
    calls: list[str] = []

    class Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ANN002
            return False

        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            return FakeResp(status=302, headers={"location": "http://10.0.0.5/feed"})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with pytest.raises(ValueError, match="blocked feed target"):
        asyncio.run(RSSFetcher().fetch(url="https://public.test/feed"))
    assert calls == ["https://public.test/feed"]


# =====================================================================
# بخش دوم — هویت سری زمانی CSV بدون تغییر عنوان
# =====================================================================
def _csv_bytes(text: str) -> FakeResp:
    return FakeResp(content=text.encode())


def _csv_source(db=None, *, endpoint_config=None):
    src = Source(name="csv-p5", collection_method="dataset", type="api",
                 data_download_url="https://example.test/d.csv",
                 endpoint_config=endpoint_config)
    db = db or _mem_db()
    db.add(src)
    db.commit()
    return db, src


def test_csv_series_title_untouched_and_identity_in_external_id(monkeypatch):
    text = "title,indicator,period,value\nGDP,GDP,2023,100\nGDP,GDP,2024,110\n"
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_csv_bytes(text)))
    res = asyncio.run(CsvAdapter().fetch(url="https://example.test/d.csv", limit=10))
    assert [i.title for i in res.items] == ["GDP", "GDP"]  # بدون دوره‌ی مصنوعی
    assert [i.metadata["external_id"] for i in res.items] == ["ind:GDP:2023",
                                                             "ind:GDP:2024"]
    assert [i.metadata["period"] for i in res.items] == ["2023", "2024"]
    assert all(i.url is None for i in res.items)
    assert res.items[0].raw_payload == json.dumps(
        {"title": "GDP", "indicator": "GDP", "period": "2023", "value": "100"})


def test_csv_series_two_periods_stored_separately_idempotent(monkeypatch):
    text = "title,indicator,period,value\nGDP,GDP,2023,100\nGDP,GDP,2024,110\n"
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_csv_bytes(text)))
    db, src = _csv_source()
    m = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m, BotSettings()))
    docs = db.query(Document).all()
    assert m.stored == 2 and len(docs) == 2
    assert {d.external_id for d in docs} == {"ind:GDP:2023", "ind:GDP:2024"}
    assert {d.title for d in docs} == {"GDP"}
    assert all(d.priority_status for d in docs)

    m2 = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m2, BotSettings()))
    assert m2.stored == 0 and m2.duplicates == 2 and db.query(Document).count() == 2


def test_csv_series_new_period_added_and_old_period_not_duplicated(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(
        _csv_bytes("indicator,period,value\nCPI,2026-06,3.1\n")))
    db, src = _csv_source()
    asyncio.run(runner_module.run_source(db, src, BotMetrics(), BotSettings()))
    assert db.query(Document).count() == 1

    # همان دوره + یک دوره‌ی جدید در یک اجرا
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(
        _csv_bytes("indicator,period,value\nCPI,2026-06,3.1\nCPI,2026-07,3.4\n")))
    m = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m, BotSettings()))
    assert m.stored == 1 and m.duplicates == 1
    docs = db.query(Document).all()
    assert {d.external_id for d in docs} == {"ind:CPI:2026-06", "ind:CPI:2026-07"}
    assert all(d.title is None for d in docs)  # متن مصنوعی ساخته نشد
    # ردیف بدون عنوان/متن هم ستون‌های اولویت را می‌گیرد
    assert all(d.ingestion_priority and d.priority_score is not None for d in docs)


def test_url_less_api_rows_dedup_by_declared_id(monkeypatch):
    """ردیف API بدون URL: هویت = id اعلام‌شده؛ اجرای دوباره idempotent است."""
    payload = {"articles": [{"id": "api-1", "headline": "H one", "body": "b " * 40}]}
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(
        FakeResp(json_data=payload, content=json.dumps(payload).encode())))
    src = Source(name="api-p5", collection_method="api", type="api",
                 api_url="https://example.test/api")
    db = _mem_db()
    db.add(src)
    db.commit()
    for _ in range(2):
        asyncio.run(runner_module.run_source(db, src, BotMetrics(), BotSettings()))
    assert db.query(Document).count() == 1
    doc = db.query(Document).one()
    assert doc.external_id == "api-1" and doc.url is None


def test_url_bearing_dedup_and_revision_unchanged(monkeypatch):
    """مسیر URL‌دار دست‌نخورده: محتوای یکسان تکراری، محتوای جدید → revision."""
    row = "title,url,text\nA,https://example.test/a,first body here\n"
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_csv_bytes(row)))
    db, src = _csv_source()
    asyncio.run(runner_module.run_source(db, src, BotMetrics(), BotSettings()))
    m = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m, BotSettings()))
    assert m.stored == 0 and m.duplicates == 1 and db.query(Document).count() == 1

    changed = "title,url,text\nA,https://example.test/a,second body here\n"
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_csv_bytes(changed)))
    asyncio.run(runner_module.run_source(db, src, BotMetrics(), BotSettings()))
    docs = db.query(Document).all()
    assert len(docs) == 2
    assert max(d.revision or 0 for d in docs) == 2


# =====================================================================
# بخش سوم — اتصال محدودیت‌ها به adapterهای واقعی
# =====================================================================
def _api_source(**kw):
    base = dict(name="api-lim", collection_method="api", type="api",
                api_url="https://example.test/api")
    base.update(kw)
    return Source(**base)


def test_rest_json_max_pages_validated_and_capped(monkeypatch):
    """مقدار نامعتبر/غیرمثبت → پیش‌فرض؛ مقدار بزرگ → سقف تنظیمات؛ هیچ مقدار نامحدود."""
    seen: dict = {}

    async def spy(self, *, url, limit=20, max_pages=3, **kw):  # noqa: ANN001
        seen["max_pages"] = max_pages
        return JsonResult([], "ok", "")

    monkeypatch.setattr(RestJsonAdapter, "fetch", spy)
    monkeypatch.setenv("SOURCE_BOT_MAX_PAGES", "4")
    settings = BotSettings()
    cases = [
        (None, 3),
        ('{"max_pages": "abc"}', 3),
        ('{"max_pages": 0}', 3),
        ('{"max_pages": -2}', 3),
        ('{"max_pages": 2}', 2),
        ('{"max_pages": 999}', 4),
    ]
    for cfg, expected in cases:
        src = _api_source(endpoint_config=cfg)
        asyncio.run(runner_module._fetch_plan(pick_adapter(src), settings))
        assert seen["max_pages"] == expected, cfg


def test_rest_json_max_pages_applied_in_runner_path(monkeypatch):
    """سقف واقعاً در حلقه‌ی pagination مسیر runner اعمال می‌شود."""
    page1 = "https://example.test/api"
    page2 = "https://example.test/api?page=2"
    calls: list[str] = []

    class Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ANN002
            return False

        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            if url == page1:
                return FakeResp(json_data={"items": [{"title": "A",
                                                      "url": "https://example.test/a"}],
                                           "next": page2})
            return FakeResp(json_data={"items": [{"title": "B",
                                                  "url": "https://example.test/b"}]})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    src = _api_source(endpoint_config='{"max_pages": 1}')
    items, _, _ = asyncio.run(runner_module._fetch_plan(pick_adapter(src), BotSettings()))
    assert calls == [page1]
    assert [i.title for i in items] == ["A"]

    calls.clear()
    src2 = _api_source(name="api-lim-2", endpoint_config='{"max_pages": 2}')
    items2, _, _ = asyncio.run(runner_module._fetch_plan(pick_adapter(src2), BotSettings()))
    assert calls == [page1, page2]
    assert [i.title for i in items2] == ["A", "B"]


def test_rss_fetcher_max_bytes_is_configurable(monkeypatch):
    rss = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
           b'<item><title>A</title><link>https://x.test/1</link>'
           b'<description>' + b"x" * 300 + b'</description></item></channel></rss>')
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(FakeResp(content=rss)))
    with pytest.raises(ValueError, match="too big"):
        asyncio.run(RSSFetcher(max_bytes=100).fetch(url="https://example.com/feed"))
    assert len(asyncio.run(RSSFetcher().fetch(url="https://example.com/feed"))) == 1
    assert RSSFetcher.max_bytes == 5_000_000  # پیش‌فرض کلاس دست‌نخورده


def test_rss_max_bytes_wired_from_settings_in_runner(monkeypatch):
    rss = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
           b'<item><title>A</title><link>https://x.test/1</link>'
           b'<description>' + b"x" * 300 + b'</description></item></channel></rss>')
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(FakeResp(content=rss)))
    monkeypatch.setenv("SOURCE_BOT_MAX_BYTES", "150")
    monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "0")
    src = Source(name="rss-lim", collection_method="rss", type="rss",
                 feed_url="https://example.com/feed")
    db = _mem_db()
    db.add(src)
    db.commit()
    m = BotMetrics()
    asyncio.run(runner_module.run_source(db, src, m, BotSettings()))
    assert db.query(Document).count() == 0
    assert "too big" in (m.sources_failed.get("rss-lim") or "")
    assert "too big" in (src.last_error or "")


def test_adapter_limits_still_wired(monkeypatch):
    """سیم‌کشی فاز ۴ حفظ شده و فقط محدودیت‌های اثبات‌شده اضافه شده‌اند."""
    seen: dict = {}

    async def rss_spy(self, *, url, limit=20):  # noqa: ANN001
        seen["rss_max_bytes"] = self._inner.max_bytes
        return []

    monkeypatch.setattr("source_bot.adapters.rss.BotRSSAdapter.fetch", rss_spy)
    monkeypatch.setenv("SOURCE_BOT_MAX_BYTES", "1234")
    src = Source(name="rss-wire", collection_method="rss", type="rss",
                 feed_url="https://example.com/feed")
    asyncio.run(runner_module._fetch_plan(SourcePlan(src, "rss", src.feed_url),
                                          BotSettings()))
    assert seen["rss_max_bytes"] == 1234

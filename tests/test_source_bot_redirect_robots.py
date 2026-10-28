"""مرحلهٔ ۲۵ — allowlist روی هر hop redirect + robots.txt پیش از full-text.

کاملاً آفلاین: transport/کلاینت جعلی، resolver جعلی (monkeypatch) و تنها یک
سرور loopback محلی. هیچ DNS/HTTP خارجی، هیچ AI، هیچ migration/dependency جدید.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from domains.news import source_verify
from domains.news.fetchers import RawItem
from domains.news.source_verify import (
    BlockedTarget,
    GuardedTransport,
    fetch_url,
    host_allowed,
    safe_get,
)
from source_bot.adapters.html import HtmlAdapter, HtmlResult
from source_bot.fulltext import (
    FULL_TEXT,
    REASON_HOST,
    REASON_ROBOTS_DISALLOWED,
    REASON_ROBOTS_UNAVAILABLE,
    SUMMARY_ONLY,
    TEXT_REASON,
    TEXT_STATUS,
    enrich_rss_items,
)

PUBLIC_IP = "93.184.216.34"
ALLOWED = ("articles.example",)


@pytest.fixture(autouse=True)
def _offline_dns(monkeypatch):
    """بدون DNS واقعی: هر نام یک IP عمومی دارد؛ خود IPها با تابع واقعی سنجیده می‌شوند."""
    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: [PUBLIC_IP])
    monkeypatch.setattr(source_verify, "host_is_private", source_verify.is_forbidden_ip)


class _Resp:
    """پاسخ جعلی حداقلی برای مسیرهای sync و async (بدون سوکت)."""

    def __init__(self, status: int = 200, headers: dict | None = None,
                 content: bytes = b"ok", url: str = "") -> None:
        self.status_code = status
        self.headers = headers or {}
        self.content = content
        self.text = content.decode("utf-8", "replace")
        self.url = url


def _fake_async_client(calls: list[str], routes: dict[str, tuple[int, dict]]):
    class Client:
        def __init__(self, *a, **k) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):  # noqa: ANN201
            return self

        async def __aexit__(self, *a):  # noqa: ANN002
            return False

        async def get(self, url: str, headers=None):  # noqa: ANN001, ANN201
            calls.append(url)
            status, extra = routes.get(url, (404, {}))
            return _Resp(status, extra, url=url)

    return Client


def _client(calls: list[str], status: int, headers: dict | None = None,
            content: bytes = b"ok"):
    return _fake_async_client(calls, {"https://articles.example/1":
                                      (status, headers or {})})


# =====================================================================
# بخش اول — allowlist روی هر hop (safe_get)
# =====================================================================
def test_redirect_to_allowed_subdomain_is_followed():
    calls: list[str] = []
    routes = {"https://articles.example/1":
              (302, {"location": "https://cdn.articles.example/2"}),
              "https://cdn.articles.example/2": (200, {})}
    resp = asyncio.run(safe_get(_fake_async_client(calls, routes)(),
                                "https://articles.example/1", allow_hosts=ALLOWED))
    assert resp.status_code == 200
    assert calls == ["https://articles.example/1", "https://cdn.articles.example/2"]


def test_redirect_outside_allowlist_rejected_before_connect():
    calls: list[str] = []
    with pytest.raises(BlockedTarget) as err:
        asyncio.run(safe_get(_client(calls, 302, {"location": "https://other.example/x"})(),
                             "https://articles.example/1", allow_hosts=ALLOWED))
    assert str(err.value) == "host_not_allowed"
    assert calls == ["https://articles.example/1"]  # مقصد غیرمجاز هرگز واکشی نشد


@pytest.mark.parametrize("target", [
    "https://evilarticles.example/x",        # lookalike: بدون نقطهٔ جداکننده
    "https://articles.example.evil.com/x",   # دامنهٔ مجاز به‌عنوان زیردامنهٔ دیگری
    "https://articlesXexample/x",            # نام مشابه
])
def test_lookalike_redirect_hosts_rejected(target):
    calls: list[str] = []
    with pytest.raises(BlockedTarget) as err:
        asyncio.run(safe_get(_client(calls, 302, {"location": target})(),
                             "https://articles.example/1", allow_hosts=ALLOWED))
    assert str(err.value) == "host_not_allowed"
    assert calls == ["https://articles.example/1"]


def test_multihop_redirect_leaving_allowlist_at_last_hop_blocked():
    calls: list[str] = []
    routes = {"https://articles.example/1":
              (302, {"location": "https://cdn.articles.example/2"}),
              "https://cdn.articles.example/2":
              (302, {"location": "https://other.example/x"})}
    with pytest.raises(BlockedTarget) as err:
        asyncio.run(safe_get(_fake_async_client(calls, routes)(),
                             "https://articles.example/1", allow_hosts=ALLOWED))
    assert str(err.value) == "host_not_allowed"
    assert calls == ["https://articles.example/1", "https://cdn.articles.example/2"]


def test_allowlisted_host_must_still_pass_ip_guard():
    """allowlist مجوز اتصال به loopback/metadata نیست؛ گارد IP مستقل باقی است."""
    calls: list[str] = []
    for bad in ("http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/"):
        with pytest.raises(BlockedTarget) as err:
            asyncio.run(safe_get(_client(calls, 200)(), bad,
                                 allow_hosts=("127.0.0.1", "169.254.169.254")))
        assert "private" in str(err.value)
    assert calls == []  # پیش از هر اتصال


def test_redirect_to_private_ip_blocked_without_allowlist_change():
    """без allowlist: رفتار قبلی — گارد IP مقصد redirect را رد می‌کند."""
    calls: list[str] = []
    with pytest.raises(BlockedTarget) as err:
        asyncio.run(safe_get(_client(calls, 302,
                                     {"location": "http://169.254.169.254/x"})(),
                             "https://articles.example/1"))
    assert "private" in str(err.value)
    assert calls == ["https://articles.example/1"]


def test_empty_allowlist_is_previous_behaviour():
    """allowlist تهی = بدون تغییر رفتار (regression سایر adapterها)."""
    calls: list[str] = []
    routes = {"https://articles.example/1": (302, {"location": "https://b.example/2"}),
              "https://b.example/2": (200, {})}
    resp = asyncio.run(safe_get(_fake_async_client(calls, routes)(),
                                "https://articles.example/1"))
    assert resp.status_code == 200
    assert calls == ["https://articles.example/1", "https://b.example/2"]


# =====================================================================
# بخش دوم — همان کنترل در مسیر sync (fetch_url) و transport
# =====================================================================
def _fake_sync_client(calls: list[str], routes: dict[str, tuple[int, dict]]):
    class Client:
        def __init__(self, *a, **k) -> None:  # noqa: ANN002, ANN003
            pass

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, *a):  # noqa: ANN002
            return False

        def get(self, url: str):  # noqa: ANN201
            calls.append(url)
            status, extra = routes.get(url, (404, {}))
            return _Resp(status, extra, url=url)

    return Client


def test_fetch_url_rejects_redirect_outside_allowlist(monkeypatch):
    calls: list[str] = []
    routes = {"https://articles.example/1": (302, {"location": "https://other.example/x"})}
    monkeypatch.setattr(httpx, "Client", _fake_sync_client(calls, routes))
    res = fetch_url("https://articles.example/1", allow_hosts=ALLOWED)
    assert res.error_kind == "host_not_allowed" and not res.ok
    assert calls == ["https://articles.example/1"]


def test_fetch_url_follows_allowlisted_redirect(monkeypatch):
    calls: list[str] = []
    routes = {"https://articles.example/1": (302, {"location": "https://cdn.articles.example/2"}),
              "https://cdn.articles.example/2": (200, {})}
    monkeypatch.setattr(httpx, "Client", _fake_sync_client(calls, routes))
    res = fetch_url("https://articles.example/1", allow_hosts=ALLOWED)
    assert res.ok and res.error_kind is None
    assert calls == ["https://articles.example/1", "https://cdn.articles.example/2"]


def test_transport_rejects_offlist_request_before_connect():
    """هیچ درخواستی (حتی داخلیِ httpx برای redirect) از transport بدون allowlist رد نمی‌شود."""
    transport = GuardedTransport(allowed_hosts=ALLOWED)
    req = httpx.Request("GET", "https://other.example/x")
    with pytest.raises(BlockedTarget) as err:
        asyncio.run(transport.handle_async_request(req))
    assert str(err.value) == "host_not_allowed"


def test_transport_blocks_automatic_redirect_before_connect(monkeypatch):
    """redirect خودکار httpx (`follow_redirects=True`) هم به مقصد غیرمجاز نمی‌رسد."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    hits: dict[str, int] = {}
    port_box: dict[str, int] = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: ANN201
            hits[self.path] = hits.get(self.path, 0) + 1
            if self.path == "/":
                self.send_response(302)
                self.send_header("Location",
                                 f"http://blocked.test:{port_box['port']}/evil")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):  # noqa: ANN002
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port_box["port"] = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: ["127.0.0.1"])
    monkeypatch.setattr(source_verify, "host_is_private", lambda h: False)
    try:
        async def run():  # noqa: ANN202
            async with httpx.AsyncClient(
                    transport=GuardedTransport(allowed_hosts=("allowed.test",)),
                    follow_redirects=True, timeout=5) as client:
                await client.get(f"http://allowed.test:{port_box['port']}/")

        with pytest.raises(BlockedTarget):
            asyncio.run(run())
    finally:
        srv.shutdown()
    assert hits.get("/") == 1
    assert hits.get("/evil") is None  # مقصد redirect هرگز واکشی نشد


# =====================================================================
# بخش سوم — robots.txt پیش از full-text
# =====================================================================
def _item(url: str = "https://articles.example/1", text: str = "short rss summary"):
    return RawItem(title="t", url=url, raw_text=text,
                   raw_payload='{"summary": "short rss summary"}')


def _article_fetch(calls: list[str]):
    async def fetch(url: str, **kw):  # noqa: ANN001, ANN003, ANN202
        calls.append(url)
        return _HtmlOk(url)

    return fetch


def _HtmlOk(url: str):
    return HtmlResult([RawItem(title="t", url=url,
                               raw_text="full article body " * 30)], "ok")


def _robots(text: str | None, calls: list[str] | None = None):
    async def robots(url: str):  # noqa: ANN202
        if calls is not None:
            calls.append(url)
        return text

    return robots


def test_html_adapter_applies_allowlist_on_redirect(monkeypatch):
    """end-to-end: مسیر واقعی adapter نیز به مقصد خارج از allowlist وصل نمی‌شود."""
    calls: list[str] = []
    routes = {"https://articles.example/1": (302, {"location": "https://other.example/x"})}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(calls, routes))
    res = asyncio.run(HtmlAdapter().fetch_url("https://articles.example/1",
                                             allowed_hosts=ALLOWED))
    assert res.status == "http_error" and res.detail.startswith("blocked:")
    assert calls == ["https://articles.example/1"]


def test_robots_allows_then_single_article_get():
    art, rob = [], []
    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art),
                                 robots_fetch=_robots("User-agent: *\nAllow: /\n", rob)))
    assert rob == ["https://articles.example/robots.txt"]
    assert art == ["https://articles.example/1"]           # دقیقاً یک GET مقاله
    assert item.metadata[TEXT_STATUS] == FULL_TEXT
    assert TEXT_REASON not in item.metadata


def test_robots_disallow_prevents_article_get():
    art = []
    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art),
                                 robots_fetch=_robots("User-agent: *\nDisallow: /1\n")))
    assert art == []                                       # هیچ GET مقاله‌ای رخ نداد
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY
    assert item.metadata[TEXT_REASON] == REASON_ROBOTS_DISALLOWED
    assert item.raw_text == "short rss summary"
    assert item.raw_payload == '{"summary": "short rss summary"}'


def test_robots_unavailable_is_fail_closed():
    art = []
    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art), robots_fetch=_robots(None)))
    assert art == []
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY
    assert item.metadata[TEXT_REASON] == REASON_ROBOTS_UNAVAILABLE


@pytest.mark.parametrize("body", [
    "<html><body>error page</body></html>",   # پاسخ نامعتبر (HTML خطا)
    "",                                       # خالی
    "Disallow: /\n",                          # بدون اعلان user-agent
])
def test_invalid_robots_response_is_fail_closed(body):
    art = []
    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art), robots_fetch=_robots(body)))
    assert art == []
    assert item.metadata[TEXT_REASON] == REASON_ROBOTS_UNAVAILABLE


def test_robots_fetch_error_is_fail_closed():
    art = []

    async def boom(url: str):  # noqa: ANN202
        raise RuntimeError("robots unavailable")

    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art), robots_fetch=boom))
    assert art == []
    assert item.metadata[TEXT_REASON] == REASON_ROBOTS_UNAVAILABLE


def test_robots_redirect_outside_allowlist_blocks_article(monkeypatch):
    """robots.txt هم از allowlist عبور می‌کند؛ redirect غیرمجاز = ممنوع."""
    art: list[str] = []
    robots_calls: list[str] = []
    routes = {"https://articles.example/robots.txt":
              (302, {"location": "https://other.example/robots.txt"})}
    monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client(robots_calls, routes))
    item = _item()
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art)))
    assert robots_calls == ["https://articles.example/robots.txt"]
    assert art == []
    assert item.metadata[TEXT_REASON] == REASON_ROBOTS_UNAVAILABLE


def test_robots_cached_per_origin_within_run():
    art, rob = [], []
    items = [_item(url=f"https://articles.example/{i}") for i in (1, 2, 3)]
    asyncio.run(enrich_rss_items(items, allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art),
                                 robots_fetch=_robots("User-agent: *\nAllow: /\n", rob)))
    assert rob == ["https://articles.example/robots.txt"]     # یک‌بار برای همان origin
    assert art == [f"https://articles.example/{i}" for i in (1, 2, 3)]
    assert [i.metadata[TEXT_STATUS] for i in items] == [FULL_TEXT] * 3


def test_robots_failure_only_affects_its_own_item():
    art, rob = [], []

    async def robots(url: str):  # noqa: ANN202
        rob.append(url)
        if "blocked-origin" in url:
            return None
        return "User-agent: *\nAllow: /\n"

    items = [_item(url="https://blocked-origin.example/1"),
             _item(url="https://articles.example/2")]
    asyncio.run(enrich_rss_items(items, allowed_hosts=("blocked-origin.example",
                                                      "articles.example"),
                                 delay=0, fetch=_article_fetch(art), robots_fetch=robots))
    assert rob == ["https://blocked-origin.example/robots.txt",
                  "https://articles.example/robots.txt"]
    assert art == ["https://articles.example/2"]           # آیتم دوم قابل‌پردازش ماند
    assert items[0].metadata[TEXT_STATUS] == SUMMARY_ONLY
    assert items[0].metadata[TEXT_REASON] == REASON_ROBOTS_UNAVAILABLE
    assert items[1].metadata[TEXT_STATUS] == FULL_TEXT


def test_host_reason_recorded_without_request():
    art = []
    item = _item(url="https://other.example/1")
    asyncio.run(enrich_rss_items([item], allowed_hosts=ALLOWED, delay=0,
                                 fetch=_article_fetch(art),
                                 robots_fetch=_robots("User-agent: *\nAllow: /\n")))
    assert art == []
    assert item.metadata[TEXT_STATUS] == SUMMARY_ONLY
    assert item.metadata[TEXT_REASON] == REASON_HOST


def test_host_allowed_policy_lookalikes():
    assert host_allowed("www.bbc.co.uk", ("bbc.co.uk",)) is True
    assert host_allowed("bbc.co.uk", ("bbc.co.uk",)) is True
    for bad in ("evilbbc.co.uk", "bbc.co.uk.evil.com", "bbc.co.uk.evil", "", "x"):
        assert host_allowed(bad, ("bbc.co.uk",)) is False, bad

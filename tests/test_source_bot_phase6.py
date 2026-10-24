"""Phase 6 — بستن SSRF در مسیر اتصال (Scrapy/Twisted + HTTPX) و idempotency سری زمانی.

همه‌چیز آفلاین: سرور محلی 127.0.0.1، DNS جعلی (monkeypatch یا probe جدا)، transport
جعلی. هیچ تماس خارجی/AI واقعی وجود ندارد.

تفکیک «چه چیزی با چه چیزی اثبات می‌شود»:
- `test_probe_*`: مسیر واقعی اتصال Twisted (همان Agent/HostnameEndpoint که Scrapy
  استفاده می‌کند) با resolver سیاست؛ اتصال به مقصد ممنوع رخ نمی‌دهد.
- لایه‌ی downloader/Scrapy در `test_source_bot_phase5.py` (تست‌های crawl) پوشش شده است.
- تست‌های runner: مسیر واقعی `run_source` بدون هیچ درخواست/اتصال.
"""
from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news import source_verify
from domains.news.source_verify import (
    BlockedTarget,
    GuardedTransport,
    fetch_url,
    safe_get,
    target_allowed,
)
from source_bot import security
from source_bot.adapters.html import CrawlError, HtmlAdapter, _crawl_settings
from source_bot.adapters.rest_json import RestJsonAdapter
from source_bot.config import BotSettings
from source_bot.metrics import BotMetrics
from tests.test_source_bot_adapters_phase4 import FakeResp, _mem_db
from tests.test_source_bot_phase5 import _page, _server

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_IP = "93.184.216.34"


def _fake_policy_dns(monkeypatch, public: dict[str, list[str]]) -> None:
    """DNS جعلی policy: نام‌های `public` پاسخ داده‌شده، بقیه IP literal فرض می‌شوند.

    بدون هیچ DNS واقعی؛ literalهای خصوصی (127.0.0.1/10.x/metadata) با تابع واقعی
    سنجیده می‌شوند تا سیاست واقعاً امتحان شود.
    """
    real_hip = source_verify.host_is_private
    monkeypatch.setattr(source_verify, "host_is_private",
                        lambda h: False if h in public else real_hip(h))
    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: public.get(h, [h]))


def _loopback_alias(monkeypatch, mapping: dict[str, str]) -> None:
    """اتصال واقعی نام‌های تست فقط به loopback؛ هر مقصد دیگر ⇒ شکست تست.

    پس اگر سیاست جا بزند و درخواست ارسال شود، سرور محلی آن را می‌بیند.
    """
    real = socket.getaddrinfo

    def fake(host, port, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN201
        if host not in mapping:
            raise AssertionError(f"unexpected connect target: {host}")
        return real(mapping[host], port, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def _allow_policy_dns(monkeypatch, allowed: dict[str, list[str]],
                      blocked: dict[str, list[str]] | None = None) -> None:
    """سیاست جعلیِ تست در **همان نقطه‌ی حقیقت** (`_allowed_ips`) که اتصال pin از آن می‌آید.

    چون اتصال به IPِ همین تابع pin می‌شود، `allowed` هم «اجازه» و هم «مقصد
    واقعی اتصال» را تعیین می‌کند؛ میزبان‌های دیگر با تابع واقعی سنجیده می‌شوند
    (literalهای خصوصی/ممنوع دست‌نخورده و مسدود می‌مانند). نام‌های مجاز برای
    بررسی مستقیم `fetch_url` (که `host_is_private` را جدا صدا می‌زند) هم مجاز می‌شوند.
    """
    real_ips = source_verify._allowed_ips
    real_hip = source_verify.host_is_private

    def fake(host: str, *, allow_private: bool = False) -> tuple[list[str], str]:
        if host in allowed:
            return list(allowed[host]), ""
        if blocked and host in blocked:
            return [], f"private_ip:{blocked[host][0]}"
        return real_ips(host, allow_private=allow_private)

    monkeypatch.setattr(source_verify, "_allowed_ips", fake)
    monkeypatch.setattr(source_verify, "host_is_private",
                        lambda h: False if h in allowed else real_hip(h))


# =====================================================================
# بخش ۱ — resolver سیاست: همان IPی که تأیید می‌شود همان IP اتصال است
# =====================================================================
def test_vetted_ip_returns_exact_validated_connect_ip(monkeypatch):
    """خروجی = همان `ip`ی که Twisted به آن وصل می‌شود (نه یک resolve تازه)."""
    monkeypatch.setattr(security, "resolve_host_ips", lambda h: [PUBLIC_IP])
    assert security.vetted_ip(PUBLIC_IP, "site.test") == PUBLIC_IP


@pytest.mark.parametrize(("ip", "answers"), [
    ("127.0.0.1", ["127.0.0.1"]),            # خودِ مقصد اتصال خصوصی است
    ("169.254.169.254", ["169.254.169.254"]),
    (PUBLIC_IP, [PUBLIC_IP, "10.0.0.5"]),    # یک IP ممنوع در پاسخ DNS ⇒ کل پاسخ رد
    (PUBLIC_IP, []),                         # DNS بی‌پاسخ ⇒ fail-closed
])
def test_vetted_ip_blocks_unsafe_answers(monkeypatch, ip, answers):
    from twisted.internet.error import DNSLookupError

    monkeypatch.setattr(security, "resolve_host_ips", lambda h: answers)
    with pytest.raises(DNSLookupError):
        security.vetted_ip(ip, "site.test")


def test_vetted_ip_allow_hosts_seam_is_explicit_and_narrow(monkeypatch):
    """seam فقط میزبان صریح را مجاز می‌کند؛ میزبان دیگر مسدود می‌ماند."""
    from twisted.internet.error import DNSLookupError

    monkeypatch.setattr(security, "resolve_host_ips", lambda h: [])
    assert security.vetted_ip("127.0.0.1", "pinned.test",
                              allow_hosts=("pinned.test",)) == "127.0.0.1"
    with pytest.raises(DNSLookupError):
        security.vetted_ip("127.0.0.1", "other.test", allow_hosts=("pinned.test",))


def test_missing_crawl_seam_keeps_resolver_strict():
    """نبودِ تنظیمات ⇒ فهرست تهی و سیاست کامل (کنترل امنیتی خاموش نمی‌شود)."""
    from twisted.internet.error import DNSLookupError

    from source_bot.adapters import scrapy_policy

    scrapy_policy.set_test_origin_hosts([])
    assert scrapy_policy._test_origin_hosts == frozenset()
    with pytest.raises(DNSLookupError):
        security.vetted_ip("127.0.0.1", "127.0.0.1",
                           allow_hosts=scrapy_policy._test_origin_hosts)


# =====================================================================
# بخش ۲ — probe واقعی: resolver کنترل اتصال را دارد + TLS دست‌نخورده
# =====================================================================
def _run_probe(mode: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "tests._phase6_probe", mode],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300, check=False)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_probe_blocked_target_never_connected_and_vetted_ip_is_connected():
    blocked = _run_probe("blocked")
    assert blocked["connections"] == 0                  # هیچ اتصالی به مقصد ممنوع
    assert blocked["outcome"].get("status") is None      # پاسخ HTTP هم نیامد
    assert blocked["policy_calls"] == [{"name": "pinned.test", "connect_ip": "127.0.0.1",
                                        "blocked": "DNSLookupError"}]

    allowed = _run_probe("allowed")                      # همان نام + seam صریح
    assert allowed["connections"] == 1
    assert allowed["outcome"]["status"] == 200
    assert len(allowed["policy_calls"]) == 1             # یک resolve در هر درخواست (بدون resolve دوباره)
    call = allowed["policy_calls"][0]
    assert call["returned"] == call["connect_ip"] == "127.0.0.1"


def test_probe_https_verifies_certificate_hostname_on_pinned_ip():
    """TLS با hostname اصلی URL انجام می‌شود، نه با IP پین‌شده (verify فعال است)."""
    ok = _run_probe("tls_ok")
    assert ok["outcome"]["status"] == 200                # کنترل: گواهی معتبر برای همان نام
    bad = _run_probe("tls_mismatch")
    assert bad["outcome"].get("status") is None
    assert "mismatch" in bad["outcome"]["error"].lower()
    assert bad["policy_calls"][0]["returned"] == "127.0.0.1"


# =====================================================================
# بخش ۳ — سیاست مشترک httpx: fail-closed + هر hop پیش از اتصال
# =====================================================================
def test_target_allowed_fail_closed_and_any_private_ip_blocks(monkeypatch):
    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: [])
    ok, reason = target_allowed("https://unknown.test/x")
    assert not ok and reason == "dns_unresolved"

    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: [PUBLIC_IP, "10.0.0.5"])
    ok, reason = target_allowed("https://mixed.test/x")
    assert not ok and reason == "private_ip:10.0.0.5"

    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: [PUBLIC_IP])
    assert target_allowed("https://ok.test/x")[0]


def test_safe_get_sends_nothing_when_dns_is_unresolved(monkeypatch):
    monkeypatch.setattr(source_verify, "resolve_host_ips", lambda h: [])
    calls: list[str] = []

    class Client:
        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            raise AssertionError("no request may be sent")

    with pytest.raises(BlockedTarget):
        asyncio.run(safe_get(Client(), "https://unknown.test/x"))
    assert calls == []


def test_guarded_transport_applies_policy_to_every_auto_redirect_hop(monkeypatch):
    """حتی اگر مصرف‌کننده redirect خودکار را روشن کند، hop دوم هم از policy می‌گذرد."""
    _fake_policy_dns(monkeypatch, {"allowed.test": [PUBLIC_IP]})
    sent: list[str] = []

    async def fake_inner(self, request):  # noqa: ANN001, ANN202
        sent.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://10.0.0.5/next"},
                              request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_inner)

    async def go():
        async with httpx.AsyncClient(transport=GuardedTransport(),
                                     follow_redirects=True) as client:
            await client.get("https://allowed.test/start")

    with pytest.raises(BlockedTarget):
        asyncio.run(go())
    assert sent == ["https://allowed.test/start"]   # hop دوم هرگز ارسال نشد


# =====================================================================
# بخش ۴ — REST: redirect و pagination («next» غیرقابل‌اعتماد) از همان policy
# =====================================================================
def _rest_fake_client(pages: dict, calls: list):
    class Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):  # noqa: ANN002
            return False

        async def get(self, url, headers=None):  # noqa: ANN001, ANN202
            calls.append(url)
            return pages[url]

    return Client


def test_rest_json_redirect_to_hostname_resolving_private_is_not_requested(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(httpx, "AsyncClient", _rest_fake_client({
        "https://api.test/api": FakeResp(
            status=302, headers={"location": "https://internal.test/x"},
            url="https://api.test/api"),
    }, calls))
    _fake_policy_dns(monkeypatch, {"api.test": [PUBLIC_IP], "internal.test": ["10.0.0.5"]})

    res = asyncio.run(RestJsonAdapter().fetch(url="https://api.test/api"))
    assert calls == ["https://api.test/api"]        # مقصد redirect درخواست نشد
    assert res.status == "http_error" and res.detail == "blocked: private_ip:10.0.0.5"


def test_rest_json_pagination_next_resolving_private_is_not_requested(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(httpx, "AsyncClient", _rest_fake_client({
        "https://api.test/api": FakeResp(
            json_data={"items": [], "next": "https://next.test/api?p=2"},
            url="https://api.test/api"),
    }, calls))
    _fake_policy_dns(monkeypatch, {"api.test": [PUBLIC_IP], "next.test": ["10.0.0.5"]})

    res = asyncio.run(RestJsonAdapter().fetch(url="https://api.test/api", max_pages=3))
    assert calls == ["https://api.test/api"]        # صفحه‌ی «next» درخواست نشد
    assert res.status == "http_error" and res.detail == "blocked: private_ip:10.0.0.5"


# =====================================================================
# بخش ۵ — fetch_url: هر hop پیش از اتصال (loopback/metadata/نام خصوصی)
# =====================================================================
def test_fetch_url_redirect_to_loopback_never_reaches_server(monkeypatch):
    routes: dict = {"/ok": (200, {}, "leak")}
    srv, base, hits = _server(routes)
    port = urlparse(base).port
    routes["/start"] = (302, {"Location": f"http://127.0.0.1:{port}/ok"}, "")
    # فقط همین نام به loopback مجاز است؛ literal خصوصی مجاز نمیشود
    _allow_policy_dns(monkeypatch, {"alias.test": ["127.0.0.1"]})
    _loopback_alias(monkeypatch, {"127.0.0.1": "127.0.0.1"})
    try:
        res = fetch_url(f"http://alias.test:{port}/start", timeout=5)
    finally:
        srv.shutdown()
    assert res.error_kind == "ssrf_blocked" and not res.ok
    assert hits == {"/start": 1}      # مقصد redirect (همان سرور) هرگز درخواست نشد


@pytest.mark.parametrize(("path", "target", "answers"), [
    ("/private", "http://169.254.169.254/latest/meta-data/", {}),            # metadata
    ("/private", "http://10.0.0.5/private", {}),                             # IP خصوصی
    ("/rebind", "http://rebind.test/{port}/rebind", {"rebind.test": ["10.0.0.5"]}),
])
def test_fetch_url_never_connects_to_forbidden_redirect_target(
        monkeypatch, path, target, answers):
    """مقصد ممنوع: نه اتصال، نه resolve در لایه‌ی اتصال، و error_kind صریح."""
    routes: dict = {path: (200, {}, "leak")}
    srv, base, hits = _server(routes)
    port = urlparse(base).port
    routes["/start"] = (302, {"Location": target.format(port=port)}, "")
    _allow_policy_dns(monkeypatch, {"alias.test": ["127.0.0.1"]}, blocked=answers)
    _loopback_alias(monkeypatch, {"127.0.0.1": "127.0.0.1"})
    try:
        res = fetch_url(f"http://alias.test:{port}/start", timeout=5)
    finally:
        srv.shutdown()
    assert res.error_kind == "ssrf_blocked" and not res.ok
    assert hits == {"/start": 1}   # هیچ درخواستی به مقصد ممنوع (حتی صفحه‌ی هدف) نرفت


def test_fetch_url_follows_allowed_chain_within_cap_and_records_it(monkeypatch):
    srv, base, hits = _server({
        "/a": (302, {"Location": "/b"}, ""),
        "/b": (302, {"Location": "/c"}, ""),
        "/c": (200, {}, "done"),
    })
    port = urlparse(base).port
    _allow_policy_dns(monkeypatch, {"alias.test": ["127.0.0.1"]})
    _loopback_alias(monkeypatch, {"127.0.0.1": "127.0.0.1"})
    user_base = f"http://alias.test:{port}"
    try:
        res = fetch_url(f"{user_base}/a", timeout=5)
    finally:
        srv.shutdown()
    assert res.ok and res.status_code == 200
    assert res.redirect_chain == [f"{user_base}/{p}" for p in ("a", "b", "c")]
    assert res.final_url == f"{user_base}/c"
    assert hits == {"/a": 1, "/b": 1, "/c": 1}


def test_fetch_url_stops_chain_at_cap(monkeypatch):
    """> سقف redirect ⇒ too_many_redirects (بدون حلقه‌ی بی‌پایان)."""
    routes = {f"/r{i}": (302, {"Location": f"/r{i + 1}"}, "") for i in range(8)}
    routes["/r8"] = (200, {}, "end")
    srv, base, hits = _server(routes)
    port = urlparse(base).port
    _allow_policy_dns(monkeypatch, {"alias.test": ["127.0.0.1"]})
    _loopback_alias(monkeypatch, {"127.0.0.1": "127.0.0.1"})
    try:
        res = fetch_url(f"http://alias.test:{port}/r0", timeout=5)
    finally:
        srv.shutdown()
    assert res.error_kind == "too_many_redirects" and not res.ok
    assert sum(hits.values()) == 6   # شروع + ۵ hop مجاز (MAX_FETCH_REDIRECTS)
    assert hits.get("/r8", 0) == 0


# =====================================================================
# بخش ۶ — سیم‌کشی مسیر واقعی: تنظیمات crawl + runner
# =====================================================================
def test_crawl_settings_wire_both_policy_layers_and_keep_tls_default():
    from scrapy.utils.misc import load_object
    from twisted.internet.interfaces import IResolverSimple

    from source_bot.adapters import scrapy_policy

    settings = _crawl_settings(10.0, {"DEPTH_LIMIT": 2})
    middleware = settings["DOWNLOADER_MIDDLEWARES"]
    assert middleware["source_bot.adapters.scrapy_policy.ConnectionPolicyMiddleware"] == 100
    assert middleware["scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware"] is None
    resolver_cls = load_object(settings["DNS_RESOLVER"])
    assert resolver_cls is scrapy_policy.PolicyResolver
    assert IResolverSimple.implementedBy(resolver_cls)
    assert settings["DEPTH_LIMIT"] == 2
    # TLS دست‌نخورده: context factory پیش‌فرض Scrapy جایگزین نشده است
    assert "DOWNLOADER_CLIENTCONTEXTFACTORY" not in settings
    from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
    from twisted.web.client import BrowserLikePolicyForHTTPS

    assert issubclass(ScrapyClientContextFactory, BrowserLikePolicyForHTTPS)


def _run_runner_source(db, src) -> BotMetrics:
    """مسیر واقعی runner با retry صفر (تست سریع و بدون انتظار backoff)."""
    from source_bot import runner as runner_module

    metrics = BotMetrics()
    settings = BotSettings()
    settings.max_retries = 0
    asyncio.run(runner_module.run_source(db, src, metrics, settings))
    return metrics


def _scrape_source(db, *, name: str, url: str, crawl: bool = False) -> Source:
    src = Source(name=name, collection_method="scrape", type="website", homepage_url=url,
                 endpoint_config=json.dumps({"crawl": True}) if crawl else None)
    db.add(src)
    db.commit()
    return src


def test_runner_path_blocks_loopback_origin_before_any_connection():
    """مسیر واقعی runner: منبع با URL غیرمجاز (loopback) هیچ درخواستی نمی‌فرستد."""
    srv, base, hits = _server({"/": (200, {}, _page("Root")), "/robots.txt": (404, {}, "")})
    db = _mem_db()
    try:
        src = _scrape_source(db, name="phase6-literal", url=base + "/")
        metrics = _run_runner_source(db, src)
        assert hits == {}                                    # حتی robots.txt
        assert metrics.sources_failed.get("phase6-literal")
        assert src.last_error
        assert db.query(Document).count() == 0
    finally:
        srv.shutdown()


def test_runner_path_blocks_private_dns_target_and_passes_no_test_origins(monkeypatch):
    """مقصدی که DNS آن خصوصی است (و واقعاً به سرور محلی می‌رسد): هیچ درخواستی نمی‌رود.

    هم‌زمان ثابت می‌کند runner هرگز seam تست (`authorized_origins`) را به crawl نمی‌دهد.
    """
    srv, base, hits = _server({"/": (200, {}, _page("Root")), "/robots.txt": (404, {}, "")})
    port = urlparse(base).port
    _fake_policy_dns(monkeypatch, {"rebind.test": ["10.0.0.5"]})
    _loopback_alias(monkeypatch, {"rebind.test": "127.0.0.1"})
    seen: dict = {}

    def fake_crawl(self, **kwargs):  # noqa: ANN001, ANN003 — امضای HtmlAdapter.crawl
        seen.update(kwargs)
        raise CrawlError("test: crawl layer replaced (connect layer is what we assert)")

    monkeypatch.setattr(HtmlAdapter, "crawl", fake_crawl)
    db = _mem_db()
    user_url = f"http://rebind.test:{port}/"
    try:
        src = _scrape_source(db, name="phase6-rebind", url=user_url, crawl=True)
        metrics = _run_runner_source(db, src)
        assert seen["start_urls"] == [user_url]
        assert "authorized_origins" not in seen        # seam تست از runner قابل دسترسی نیست
        assert hits == {}                              # مقصد ممنوع درخواست نشد
        assert "blocked" in str(metrics.sources_failed.get("phase6-rebind", ""))
        assert db.query(Document).count() == 0
    finally:
        srv.shutdown()


# =====================================================================
# بخش ۷ — idempotency سری زمانی: تضمین‌شده و تضمین‌نشده
# =====================================================================
def _series_item(external_id: str):
    from domains.news.fetchers import RawItem

    return RawItem(title="Economic series", url=None, raw_text="value=1",
                   metadata={"external_id": external_id, "adapter": "csv"})


def _file_db(tmp_path):
    """SQLite فایلی: تنها راه تست هم‌زمانی واقعی (چند اتصال، چند ترد)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.base import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'phase6.sqlite3'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _series_source(db, name: str) -> Source:
    src = Source(name=name, collection_method="dataset", type="api")
    db.add(src)
    db.commit()
    return src


def test_series_period_stored_sequentially_only_once(tmp_path):
    """شاهد مثبت: تکرار ترتیبی همان دوره (indicator+period) رکورد دوم نمی‌سازد."""
    from domains.news.ingestion import NewsIngestionPipeline

    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "series-seq")
        pipeline = NewsIngestionPipeline(db)
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is True
        db.commit()
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is False
        db.commit()
        assert db.query(Document).count() == 1
        assert db.query(Document).one().external_id == "cpi:2026-01"


# شکاف پیشین (دو ردیف هم‌زمان با یک external_id) در Phase 7 با index یکتای
# جزئی بسته شد؛ شاهد آن `tests/test_news_identity_phase7.py` است.


def test_run_once_lock_serializes_two_truly_concurrent_runs(monkeypatch, tmp_path):
    """سازوکار موجود (قفل فایل): دو اجرای واقعاً هم‌زمان سریالی می‌شوند."""
    from source_bot import runner as runner_module

    monkeypatch.setattr(runner_module, "LOCK_PATH", str(tmp_path / "bot.lock"))
    Session = _file_db(tmp_path)
    with Session() as db:
        # منبع باید plan قابل‌اجرا داشته باشد تا `_fetch_plan` (fake) صدا زده شود
        db.add(Source(name="lock-src", collection_method="rss", type="rss",
                      feed_url="https://feed.test/rss"))
        db.commit()

    started = threading.Event()

    async def slow_fetch(plan, settings):  # noqa: ANN001, ANN202
        started.set()
        await asyncio.sleep(1.5)
        return [], plan.url or "", {}

    monkeypatch.setattr(runner_module, "_fetch_plan", slow_fetch)
    outcomes: list[object] = []

    def run() -> None:
        db = Session()
        try:
            outcomes.append(asyncio.run(runner_module.run_once(source_name="lock-src", db=db)))
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(exc)
        finally:
            db.close()

    first = threading.Thread(target=run)
    first.start()
    assert started.wait(timeout=20)   # اجرای اول قفل را گرفته و در حال کار است
    second = threading.Thread(target=run)
    second.start()
    first.join(timeout=30)
    second.join(timeout=30)

    assert len(outcomes) == 2
    assert sum(isinstance(o, RuntimeError) and "lock exists" in str(o)
               for o in outcomes) == 1
    metrics = [o for o in outcomes if isinstance(o, BotMetrics)]
    assert len(metrics) == 1 and metrics[0].sources_ok == 1

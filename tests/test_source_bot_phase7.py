"""Phase 7 — pin اتصال HTTPX، سیاست Scrapy در برابر تنظیم ناسازگار، و crawl مسدود.

هیچ ترافیک بیرونی در این تست‌ها نیست: DNS/اتصال در همان نقطه‌ی واقعی
(anyio / socket / reactor) مهار می‌شود و تنها سرورهای محلی loopback بالا می‌آیند.
"""
from __future__ import annotations

import asyncio
import datetime
import ipaddress
import socket
import ssl
from pathlib import Path

import anyio
import httpx
import pytest

from backend.database.models.document import Document
from domains.news import source_verify
from domains.news.source_verify import (
    BlockedTarget,
    GuardedSyncTransport,
    GuardedTransport,
    _pin_pool,
    _PinnedAsyncBackend,
    fetch_url,
    pinned_ip,
    target_allowed,
)
from source_bot.adapters.html import CrawlError, HtmlAdapter, _crawl_settings, get_spider_class
from source_bot.adapters.scrapy_policy import assert_policy_settings
from tests.test_source_bot_adapters_phase4 import _mem_db
from tests.test_source_bot_phase5 import _page, _server
from tests.test_source_bot_phase6 import (
    _allow_policy_dns,
    _run_probe,
    _run_runner_source,
    _scrape_source,
)

PUBLIC_IP = "93.184.216.34"
PRIVATE_IP = "10.0.0.5"
# تابع واقعی resolve، پیش از patch آفلاینِ conftest — برای تست خطای DNS
_REAL_RESOLVE = source_verify.resolve_host_ips


class _Stop(Exception):
    """توقف پیش از سوکت واقعی: تست نباید سوکت بسازد، فقط مقصد را ببیند."""


def _record_connects(monkeypatch) -> list[tuple[str, int]]:
    """ضبط مقصد واقعی اتصال در لایه‌ی anyio (پایین‌ترین نقطه‌ی HTTPX)."""
    seen: list[tuple[str, int]] = []

    async def fake(remote_host, remote_port, **kw):  # noqa: ANN001, ANN003, ANN202
        seen.append((remote_host, remote_port))
        raise _Stop("no real socket in tests")

    monkeypatch.setattr(anyio, "connect_tcp", fake)
    return seen


def _policy_answer(monkeypatch, answer: list[str], *, fail: bool = False) -> list[str]:
    """DNS جعلی policy؛ لیست برگشتی تعداد resolve‌ها را ثبت می‌کند."""
    calls: list[str] = []

    def resolver(host: str) -> list[str]:
        calls.append(host)
        return [] if fail else list(answer)

    monkeypatch.setattr(source_verify, "resolve_host_ips", resolver)
    return calls


def _get(url: str, transport=None, **kwargs):  # noqa: ANN001, ANN003, ANN201
    async def go():
        async with httpx.AsyncClient(transport=transport or GuardedTransport(),
                                     timeout=5, **kwargs) as client:
            return await client.get(url)

    return asyncio.run(go())


# =====================================================================
# بخش ۱ — pin اتصال HTTPX به همان IP تأییدشده
# =====================================================================
def test_connect_target_is_the_validated_ip_not_the_hostname(monkeypatch):
    """سوکت به IP تأییدشده می‌رود؛ نام فقط برای Host/SNI می‌ماند."""
    calls = _policy_answer(monkeypatch, [PUBLIC_IP])
    seen = _record_connects(monkeypatch)

    with pytest.raises(_Stop):
        _get("https://public.test/x")

    assert seen == [(PUBLIC_IP, 443)]
    assert ipaddress.ip_address(seen[0][0])          # مقصد اتصال IP literal است
    assert calls == ["public.test", "public.test"]   # policy + همان لحظه‌ی اتصال
    assert PUBLIC_IP != "public.test"


def test_dns_flip_at_connect_time_is_blocked_before_socket(monkeypatch):
    """پنجره‌ی rebinding: پاسخ دوم (لحظه‌ی اتصال) خصوصی بود ⇒ هیچ اتصالی ساخته نشد."""
    calls = _policy_answer(monkeypatch, [PUBLIC_IP])
    seen = _record_connects(monkeypatch)

    def flipping(host: str) -> list[str]:
        calls.append(host)
        return [PUBLIC_IP] if len(calls) == 1 else [PRIVATE_IP]

    monkeypatch.setattr(source_verify, "resolve_host_ips", flipping)

    with pytest.raises(BlockedTarget) as excinfo:
        _get("https://rebind.test/x")

    assert str(excinfo.value) == f"private_ip:{PRIVATE_IP}"
    assert seen == []
    assert len(calls) == 2          # دو resolve: سنجش پیش از ارسال و pin لحظه‌ی اتصال


def test_mixed_public_and_private_answer_is_blocked(monkeypatch):
    """یک پاسخ ممنوع در میان پاسخ‌ها کافی است؛ «انتخاب تصادفی IP عمومی» ممنوع."""
    _policy_answer(monkeypatch, [PUBLIC_IP, PRIVATE_IP])
    seen = _record_connects(monkeypatch)

    with pytest.raises(BlockedTarget) as excinfo:
        _get("https://mixed.test/x")

    assert str(excinfo.value) == f"private_ip:{PRIVATE_IP}"
    assert seen == []


def test_dns_failure_never_authorizes_a_connection(monkeypatch):
    _policy_answer(monkeypatch, [], fail=True)
    seen = _record_connects(monkeypatch)

    with pytest.raises(BlockedTarget) as excinfo:
        _get("https://unresolved.test/x")

    assert str(excinfo.value) == "dns_unresolved"
    assert seen == []


def test_unparsable_dns_answer_is_blocked(monkeypatch):
    _policy_answer(monkeypatch, ["not-an-ip"])
    seen = _record_connects(monkeypatch)

    with pytest.raises(BlockedTarget) as excinfo:
        _get("https://garbage.test/x")

    assert str(excinfo.value).startswith("unparsable_ip:")
    assert seen == []


def test_dns_error_or_timeout_fails_closed_in_the_policy_core(monkeypatch):
    """خطای/تایم‌اوت واقعی DNS = «نامعلوم» و مسدود؛ نه «عمومی»."""
    monkeypatch.setattr(source_verify, "resolve_host_ips", _REAL_RESOLVE)

    def boom(*a, **k):  # noqa: ANN002, ANN003, ANN201
        raise TimeoutError("dns timeout")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    assert source_verify.resolve_host_ips("boom.test") == []
    assert target_allowed("https://boom.test/x") == (False, "dns_unresolved")
    with pytest.raises(BlockedTarget) as excinfo:
        pinned_ip("boom.test")
    assert str(excinfo.value) == "dns_unresolved"


def test_auto_redirect_hop_is_revalidated_and_never_connected(monkeypatch):
    """مصرف‌کننده‌ای که redirect خودکار را روشن کند هم hop دوم را از policy می‌گذراند."""
    _policy_answer(monkeypatch, [PUBLIC_IP])
    seen = _record_connects(monkeypatch)
    sent: list[str] = []

    async def fake_inner(self, request):  # noqa: ANN001, ANN202
        sent.append(str(request.url))
        return httpx.Response(302, headers={"location": f"http://{PRIVATE_IP}/next"},
                              request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_inner)

    with pytest.raises(BlockedTarget) as excinfo:
        _get("https://allowed.test/start", follow_redirects=True)

    assert str(excinfo.value).startswith("private")
    assert sent == ["https://allowed.test/start"]   # فقط hop اول؛ hop دوم مسدود شد
    assert seen == []


def test_env_proxy_cannot_bypass_the_pin(monkeypatch):
    """پروکسی محیطی نباید مقصد اتصال را از IP تأییدشده دور بزند."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    _policy_answer(monkeypatch, [PUBLIC_IP])
    seen = _record_connects(monkeypatch)

    with pytest.raises(_Stop):
        _get("https://public.test/x")

    assert seen == [(PUBLIC_IP, 443)]        # نه 127.0.0.1:9 (پروکسی)


@pytest.mark.parametrize("kwargs", [{"proxy": "http://127.0.0.1:9"}, {"uds": "/tmp/x.sock"}])
def test_transports_reject_proxy_and_uds(kwargs):
    with pytest.raises(ValueError):
        GuardedTransport(**kwargs)
    with pytest.raises(ValueError):
        GuardedSyncTransport(**kwargs)


def test_transports_reject_positional_args():
    with pytest.raises(ValueError):
        GuardedTransport(True)
    with pytest.raises(ValueError):
        GuardedSyncTransport(True)


def test_missing_pool_backend_fails_loudly(monkeypatch):
    """اگر layout پول عوض شود، اجرا متوقف می‌شود (هرگز اتصال بدون pin)."""
    transport = GuardedTransport()
    monkeypatch.delattr(transport._pool, "_network_backend")
    with pytest.raises(RuntimeError, match="cannot pin"):
        _pin_pool(transport._pool, _PinnedAsyncBackend)


def test_literal_private_and_mapped_ipv6_are_blocked(monkeypatch):
    for host in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "::", "::ffff:10.0.0.5",
                 "::ffff:127.0.0.1"):
        url = f"http://[{host}]/x" if ":" in host else f"http://{host}/x"
        ok, reason = target_allowed(url)
        assert not ok, host
        assert reason.startswith(("private_host", "private_ip"))


def test_sync_transport_pins_to_validated_ip(monkeypatch):
    """مسیر sync (`fetch_url`) هم به IP تأییدشده pin می‌شود."""
    from httpcore import SyncBackend

    seen: list[str] = []

    def fake_connect(self, host, port, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN201
        seen.append(host)
        raise _Stop("no real socket in tests")

    monkeypatch.setattr(SyncBackend, "connect_tcp", fake_connect)
    _policy_answer(monkeypatch, [PUBLIC_IP])
    res = fetch_url("https://public.test/x", timeout=5)
    assert seen == [PUBLIC_IP]                # backend فقط IP تأییدشده را دید
    assert not res.ok and res.error_kind


def test_sync_transport_blocks_private_target_before_any_io():
    with pytest.raises(BlockedTarget):
        GuardedSyncTransport().handle_request(httpx.Request("GET", "http://10.0.0.5/x"))


# =====================================================================
# بخش ۲ — TLS روی IP pin‌شده: SNI و اعتبارسنجی نام دست‌نخورده
# =====================================================================
def _self_signed(tmp_path: Path, hostname: str):  # noqa: ANN202
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    crt, pem = tmp_path / f"{hostname}.crt", tmp_path / f"{hostname}.key"
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    pem.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    return crt, pem


async def _tls_server(ctx: ssl.SSLContext, sni_seen: list[str], head: list[bytes] | None = None):  # noqa: ANN202
    async def handler(reader, writer) -> None:  # noqa: ANN001
        raw = await reader.read(4096)
        if head is not None:
            head.append(raw)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        await writer.drain()
        writer.close()

    ctx.sni_callback = lambda _obj, server_name, _ctx: sni_seen.append(server_name)
    return await asyncio.start_server(handler, "127.0.0.1", 0, ssl=ctx)


def _tls_case(monkeypatch, tmp_path, request_host: str, cert_host: str,
              head: list[bytes] | None = None, *, trust_system: bool = False):
    """سرور TLS محلی با گواهی `cert_host` را با URL `request_host` می‌زند.

    `trust_system=True` ⇒ کلاینت اعتماد پیش‌فرض سیستم را دارد (گواهی self-signed
    پذیرفته نمی‌شود)؛ وگرنه همان گواهی سرور به‌عنوان trust root داده می‌شود.
    """
    crt, pem = _self_signed(tmp_path, cert_host)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(crt), str(pem))
    verify = True if trust_system else ssl.create_default_context(cafile=str(crt))
    sni: list[str] = []
    _allow_policy_dns(monkeypatch, {request_host: ["127.0.0.1"]})

    async def go():
        server = await _tls_server(ctx, sni, head)
        port = server.sockets[0].getsockname()[1]
        try:
            async with httpx.AsyncClient(
                    transport=GuardedTransport(verify=verify), timeout=5) as client:
                return await client.get(f"https://{request_host}:{port}/x")
        finally:
            server.close()
            await server.wait_closed()

    return asyncio.run(go()), sni


def test_pinned_https_keeps_sni_and_hostname_verification(monkeypatch, tmp_path):
    head: list[bytes] = []
    resp, sni = _tls_case(monkeypatch, tmp_path, "public.test", "public.test", head)
    assert resp.status_code == 200
    assert sni == ["public.test"]                    # SNI از نام اصلی URL، نه از IP
    assert b"host: public.test" in head[0].lower()   # هدر Host هم نام اصلی است


def test_pinned_https_rejects_certificate_for_another_hostname(monkeypatch, tmp_path):
    with pytest.raises(httpx.ConnectError):
        _tls_case(monkeypatch, tmp_path, "other.test", "public.test")


def test_pinned_https_rejects_untrusted_certificate(monkeypatch, tmp_path):
    """گواهی self-signed با trust پیش‌فرض پذیرفته نمی‌شود (verify خاموش نشد)."""
    with pytest.raises(httpx.ConnectError):
        _tls_case(monkeypatch, tmp_path, "public.test", "public.test", trust_system=True)


# =====================================================================
# بخش ۳ — سیاست Scrapy: تنظیم ناسازگار ⇒ توقف روشن
# =====================================================================
def _effective_crawl_settings(overrides: dict | None = None):
    """همان چیزی که `crawler.settings` در child process می‌بیند (بدون reactor)."""
    from scrapy.crawler import Crawler
    from scrapy.settings import Settings, default_settings

    overrides = overrides or {}
    settings = Settings()
    settings.setmodule(default_settings, priority="default")
    settings.update(_crawl_settings(10.0, overrides), priority="project")
    spider_cls = get_spider_class([], overrides)
    return Crawler(spider_cls, settings).settings


def test_effective_crawl_settings_pass_the_policy_guard():
    settings = _effective_crawl_settings({"DEPTH_LIMIT": 2})
    assert_policy_settings(settings)
    assert settings.get("DEPTH_LIMIT") == 2


def test_replaced_resolver_or_middleware_stops_the_crawl():
    from source_bot.adapters.scrapy_policy import MIDDLEWARE_PATH, PROXY_MIDDLEWARE_PATH

    cases = [
        {"DNS_RESOLVER": "scrapy.resolver.CachingThreadedResolver"},
        {"DOWNLOADER_MIDDLEWARES": {MIDDLEWARE_PATH: None}},
        {"DOWNLOADER_MIDDLEWARES": {PROXY_MIDDLEWARE_PATH: 750}},
        {"DOWNLOAD_HANDLERS": {"http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler"}},
    ]
    for override in cases:
        settings = _effective_crawl_settings()
        for key, value in override.items():
            settings.set(key, value, priority="cmdline")
        with pytest.raises(RuntimeError, match="unsafe crawl settings"):
            assert_policy_settings(settings)


def test_env_override_of_resolver_cannot_replace_the_policy(monkeypatch):
    """متغیر محیطی `SCRAPY_*` نباید resolver/handler/proxy را از policy جدا کند."""
    from scrapy.utils.misc import load_object

    from source_bot.adapters.scrapy_policy import PolicyResolver

    monkeypatch.setenv("SCRAPY_DNS_RESOLVER", "scrapy.resolver.CachingThreadedResolver")
    monkeypatch.setenv(
        "SCRAPY_DOWNLOADER_MIDDLEWARES",
        '{"scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750}')
    monkeypatch.setenv(
        "SCRAPY_DOWNLOAD_HANDLERS",
        '{"http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler"}')
    settings = _effective_crawl_settings()
    assert_policy_settings(settings)      # سیاست همان‌جا دست‌نخورده مانده
    assert load_object(settings.get("DNS_RESOLVER")) is PolicyResolver
    assert settings.getdict("DOWNLOAD_HANDLERS") == {}
    assert settings.getwithbase("DOWNLOADER_MIDDLEWARES").get(
        "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware") is None


def test_probe_ipv6_only_and_dns_failure_never_connect():
    """مسیر واقعی reactor: پاسخ AAAA-only یا DNS شکست‌خورده ⇒ صفر اتصال."""
    for mode in ("ipv6only", "dns_fail"):
        out = _run_probe(mode)
        assert out["connections"] == 0, mode
        assert "status" not in out["outcome"], mode
        assert "DNSLookup" in out["outcome"]["error"], mode


# =====================================================================
# بخش ۴ — crawl مسدود در برابر crawl سالمِ خالی
# =====================================================================
def test_blocked_crawl_raises_and_leaks_no_url():
    srv, base, hits = _server({"/": (200, {}, _page("Root"))})
    try:
        with pytest.raises(CrawlError) as excinfo:
            HtmlAdapter(timeout=10).crawl(
                start_urls=[base + "/"], allowed_domains=["127.0.0.1"], max_pages=2)
    finally:
        srv.shutdown()
    assert hits == {}
    message = str(excinfo.value)
    assert "blocked" in message
    assert base not in message and "127.0.0.1" not in message   # بدون افشای مقصد


def test_healthy_crawl_without_items_is_not_blocked():
    """صفحه‌ی سالم بدون آیتم استخراج‌شدنی ⇒ موفقیت خالی، نه خطا."""
    srv, base, hits = _server({"/": (200, {}, "<html><body></body></html>")})
    try:
        items = HtmlAdapter(timeout=10).crawl(
            start_urls=[base + "/"], allowed_domains=["127.0.0.1"],
            authorized_origins=(base,), max_pages=2)
    finally:
        srv.shutdown()
    assert items == []
    assert hits.get("/") == 1


def test_runner_records_blocked_crawl_as_failure_not_success():
    """گذار واقعی runner: crawl کاملاً مسدود ⇒ failed، بدون هیچ آیتم."""
    srv, base, hits = _server({"/": (200, {}, _page("Root")), "/robots.txt": (404, {}, "")})
    db = _mem_db()
    try:
        src = _scrape_source(db, name="p7-blocked", url=base + "/", crawl=True)
        metrics = _run_runner_source(db, src)
        assert hits == {}
        assert metrics.sources_ok == 0
        assert metrics.sources_failed.get("p7-blocked")
        assert db.query(Document).count() == 0
    finally:
        srv.shutdown()


def test_runner_never_reaches_the_test_origin_seam(monkeypatch):
    """seam تست (`authorized_origins`) از مسیر runner قابل دسترسی نیست؛
    crawl سالمِ خالی هم موفقیت عادی است."""
    seen: dict = {}

    def spy(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen.update(kwargs)
        return []

    monkeypatch.setattr(HtmlAdapter, "crawl", spy)
    db = _mem_db()
    src = _scrape_source(db, name="p7-seam", url="http://public.test/", crawl=True)
    metrics = _run_runner_source(db, src)
    assert "authorized_origins" not in seen
    assert metrics.sources_ok == 1 and not metrics.sources_failed

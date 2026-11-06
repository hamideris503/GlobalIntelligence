"""Probe آفلاین Phase 6: آیا resolver سیاست، **اتصال واقعی** Twisted را کنترل می‌کند؟

در یک پروسس جدا اجرا می‌شود (reactor تازه) و فقط با loopback کار می‌کند؛ هیچ
DNS/شبکه‌ی بیرونی وجود ندارد (gethostbyname/getaddrinfo جعلی می‌شوند).

حالت‌ها (argv[1]):
- blocked: نام عمومی‌نما که DNS آن loopback است، بدون seam → باید مسدود شود
  (تعداد اتصال‌های سرور محلی = ۰).
- allowed: همان حالت با seam تست → باید وصل شود (۱ اتصال) ⇒ ثابت می‌کند IPی که
  resolver برمی‌گرداند همان IPی است که سوکت به آن وصل می‌شود.
- tls_ok / tls_mismatch: با گواهی تستی Twisted (SAN=localhost) و trust root همان
  گواهی: نام منطبق ⇒ ۲۰۰؛ نام غیرمنطبق ⇒ خطای گواهی (verify hostname فعال است).
- ipv6only: پاسخ DNS فقط AAAA دارد ⇒ resolver IPv4-only شکست می‌خورد و هیچ
  اتصالی رخ نمی‌دهد (fail-closed برای مقصد بدون پوشش امن).
- dns_fail: DNS در لایه‌ی اتصال شکست می‌خورد ⇒ هیچ اتصالی و هیچ resolver bypass.

خروجی: یک JSON روی stdout.  اجرا: python -m tests._phase6_probe <mode>
"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import twisted.test.ssl_helpers as ssl_helpers


class _Handler(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self) -> None:  # noqa: N802 — امضای http.server
        type(self).hits += 1
        body = b"<html><body><p>probe ok</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: ANN002 — بی‌صدا
        return


def _config(mode: str) -> dict:
    if mode == "blocked":
        return {"fqdn": "pinned.test", "connect_ip": "127.0.0.1", "answers": ["127.0.0.1"],
                "seam": [], "tls": False}
    if mode == "allowed":
        return {"fqdn": "pinned.test", "connect_ip": "127.0.0.1", "answers": ["127.0.0.1"],
                "seam": ["http://pinned.test"], "tls": False}
    if mode == "tls_ok":
        return {"fqdn": "localhost", "connect_ip": "127.0.0.1", "answers": ["127.0.0.1"],
                "seam": ["https://localhost"], "tls": True}
    if mode == "tls_mismatch":
        return {"fqdn": "mismatch.test", "connect_ip": "127.0.0.1", "answers": ["127.0.0.1"],
                "seam": ["https://mismatch.test"], "tls": True}
    if mode == "ipv6only":
        # پاسخ DNS فقط AAAA دارد. resolver اسکرپی (مثل پیش‌فرض) IPv4-only است،
        # پس باید fail-closed باشد: هیچ اتصالی.
        return {"fqdn": "v6only.test", "connect_ip": None,
                "answers": ["2606:4700::1111"], "seam": [], "tls": False,
                "gethostbyname_fails": True, "family": socket.AF_INET6}
    if mode == "dns_fail":
        # DNS در لایه‌ی اتصال شکست می‌خورد ⇒ نه اتصالی، نه مسیر بدون کنترل.
        return {"fqdn": "nodns.test", "connect_ip": None, "answers": [],
                "seam": [], "tls": False, "gethostbyname_fails": True,
                "family": socket.AF_INET}
    raise SystemExit(f"unknown mode: {mode}")


def _install_fake_dns(cfg: dict) -> None:
    """نام تست فقط؛ هر نام دیگر به DNS واقعی می‌رود (در این probe نام دیگری نیست)."""
    real_gethostbyname, real_getaddrinfo = socket.gethostbyname, socket.getaddrinfo

    def gethostbyname(name: str) -> str:
        if name == cfg["fqdn"] and cfg.get("gethostbyname_fails"):
            # مثل نامی که فقط AAAA دارد: gethostbyname (IPv4-only) پاسخ نمی‌دهد
            raise socket.gaierror(socket.EAI_NONAME, "no IPv4 address")
        return cfg["connect_ip"] if name == cfg["fqdn"] else real_gethostbyname(name)

    def getaddrinfo(host, port, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN201
        if host == cfg["fqdn"]:
            family = cfg.get("family", socket.AF_INET)
            if family == socket.AF_INET6:
                return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "",
                         (ip, port or 0, 0, 0)) for ip in cfg["answers"]]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))
                    for ip in cfg["answers"]]
        return real_getaddrinfo(host, port, *a, **k)

    socket.gethostbyname, socket.getaddrinfo = gethostbyname, getaddrinfo


def _make_trust_policy():  # noqa: ANN202
    """سیاست TLS که فقط گواهی تستی Twisted را معتبر می‌داند (برای تست verify hostname)."""
    from twisted.internet.ssl import Certificate, optionsForClientTLS
    from twisted.web.iweb import IPolicyForHTTPS
    from zope.interface import implementer

    with open(ssl_helpers.certPath, "rb") as fh:
        trust_root = Certificate.loadPEM(fh.read())

    @implementer(IPolicyForHTTPS)
    class _TrustTestCert:
        def creatorForNetloc(self, hostname, port):  # noqa: ANN001
            name = hostname.decode() if isinstance(hostname, bytes) else hostname
            return optionsForClientTLS(name, trustRoot=trust_root)

    return _TrustTestCert()


def _start_server(tls: bool) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(ssl_helpers.certPath)  # cert+key در همان PEM
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    mode = sys.argv[1]
    cfg = _config(mode)
    server = _start_server(cfg["tls"])
    port = server.server_address[1]
    _install_fake_dns(cfg)

    from scrapy.settings import Settings, default_settings
    from twisted.internet import reactor
    from twisted.web.client import Agent, readBody

    import source_bot.adapters.scrapy_policy as policy

    calls: list[dict] = []
    real_vetted = policy.vetted_ip

    def spy(ip, name, *, allow_hosts=()):  # noqa: ANN001, ANN202
        try:
            out = real_vetted(ip, name, allow_hosts=allow_hosts)
        except Exception as exc:  # noqa: BLE001
            calls.append({"name": name, "connect_ip": ip, "blocked": type(exc).__name__})
            raise
        calls.append({"name": name, "connect_ip": ip, "returned": out})
        return out

    policy.vetted_ip = spy  # نوع: نادیده (spy فقط برای مشاهده)
    policy.set_test_origin_hosts(cfg["seam"])

    settings = Settings()
    settings.setmodule(default_settings, priority="default")
    settings.set("DNS_TIMEOUT", 5.0, priority="default")

    class _Crawler:  # Scrapy's from_crawler only needs .settings
        pass

    _Crawler.settings = settings
    resolver = policy.PolicyResolver.from_crawler(_Crawler, reactor)
    resolver.install_on_reactor()

    scheme = "https" if cfg["tls"] else "http"
    url = f"{scheme}://{cfg['fqdn']}:{port}/probe"
    outcome: dict = {}
    agent = (Agent(reactor, contextFactory=_make_trust_policy()) if cfg["tls"]
             else Agent(reactor))

    def _ok(response):  # noqa: ANN001, ANN202
        return readBody(response).addCallback(
            lambda body: outcome.update({"status": response.code, "body_len": len(body)}))

    def _err(failure):  # noqa: ANN001, ANN202
        outcome["error"] = f"{failure.type.__name__}:{str(failure.value)[:200]}"

    d = agent.request(b"GET", url.encode())
    d.addCallbacks(_ok, _err)
    d.addBoth(lambda _res: reactor.stop())
    reactor.run()

    server.shutdown()
    print(json.dumps({"mode": mode, "url": url, "connections": _Handler.hits,
                      "outcome": outcome, "policy_calls": calls}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

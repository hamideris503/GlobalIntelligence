"""Tests for source URL verifier (Step: census). Local HTTP server only — no network."""
from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from domains.news.source_verify import check_rss, fetch_url, host_is_private

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>T</title>
<item><title>A</title><link>https://x.local/1</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>T</title>
<entry><title>A</title></entry></feed>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence
        pass

    def do_GET(self) -> None:
        if self.path == "/ok":
            body = b"<html><body>hello</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redir":
            self.send_response(301)
            self.send_header("Location", "/ok")
            self.end_headers()
        elif self.path == "/missing":
            self.send_response(404)
            self.end_headers()
        elif self.path == "/rss":
            body = RSS.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/atom":
            body = ATOM.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/atom+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/notfeed":
            body = b"<html><body>no feed here</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/slow":
            time.sleep(3)
            try:
                self.send_response(200)
                self.end_headers()
            except BrokenPipeError:
                pass
        else:
            self.send_response(500)
            self.end_headers()


def _base() -> str:
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}"


BASE = _base()


def test_fetch_ok() -> None:
    r = fetch_url(BASE + "/ok", allow_private=True)
    assert r.ok and r.status_code == 200 and r.final_url == BASE + "/ok"


def test_redirect_chain_recorded() -> None:
    r = fetch_url(BASE + "/redir", allow_private=True)
    assert r.ok
    assert r.redirect_chain == [BASE + "/redir", BASE + "/ok"]
    assert r.final_url == BASE + "/ok"


def test_404_classified() -> None:
    r = fetch_url(BASE + "/missing", allow_private=True)
    assert not r.ok and r.error_kind == "http_404"


def test_timeout_retry() -> None:
    r = fetch_url(BASE + "/slow", timeout=1.0, allow_private=True)
    assert not r.ok and r.error_kind == "timeout"


def test_ssrf_blocked() -> None:
    assert host_is_private("localhost")
    assert host_is_private("127.0.0.1")
    assert host_is_private("10.1.2.3")
    assert host_is_private("169.254.169.254")
    assert not host_is_private("example.com")
    r = fetch_url("http://localhost:9/nope")
    assert not r.ok and r.error_kind == "ssrf_blocked"
    r = fetch_url("ftp://example.com/x")
    assert not r.ok and r.error_kind == "invalid_url"


def test_rss_valid_and_invalid() -> None:
    assert check_rss(BASE + "/rss", allow_private=True).ok
    assert check_rss(BASE + "/atom", allow_private=True).ok
    bad = check_rss(BASE + "/notfeed", allow_private=True)
    assert not bad.ok and bad.error_kind == "rss_invalid"
    missing = check_rss(BASE + "/missing", allow_private=True)
    assert not missing.ok

"""Feed validation without storage — همه آفلاین (httpx ماک‌شده)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from domains.news.fetchers import FeedCheck, validate_feed
from tests.conftest import TestingSession

FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Quake hits region</title><link>https://ex.com/1</link>
<description>big earthquake damage</description>
<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
<item><title>Markets rally on data</title><link>https://ex.com/2</link>
<description>stocks up</description></item>
</channel></rss>"""
EMPTY_FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title></channel></rss>"""
HTML = b"<html><head><title>H</title></head><body><p>hello world</p></body></html>"


class FakeResp:
    def __init__(self, status=200, body=b"", ctype="application/rss+xml"):
        self.status_code = status
        self.content = body
        self.headers = {"content-type": ctype}
        self.url = "https://ex.com/f.xml"
        self.history = []
        self.request = None

    def raise_for_status(self):
        pass


def _fake_client_for(resp=None, exc=None):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            if exc is not None:
                raise exc
            return resp

    return FakeClient


def test_validate_feed_valid(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _fake_client_for(FakeResp(200, FEED)))
    res = validate_feed("https://ex.com/f.xml")
    assert isinstance(res, FeedCheck)
    assert res.ok is True and res.items == 2 and res.reason == "ok"


def test_validate_feed_html_is_not_feed(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client",
                        _fake_client_for(FakeResp(200, HTML, "text/html")))
    res = validate_feed("https://ex.com/p")
    assert res.ok is False and res.reason == "not_feed"


def test_validate_feed_broken_xml_fails(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client",
                        _fake_client_for(FakeResp(200, b"<rss><channel><item><title>oops")))
    res = validate_feed("https://ex.com/f.xml")
    assert res.ok is False and res.reason in ("not_feed", "empty_feed", "unreadable_items")


def test_validate_feed_empty_is_not_ok(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _fake_client_for(FakeResp(200, EMPTY_FEED)))
    res = validate_feed("https://ex.com/f.xml")
    assert res.ok is False and res.reason == "empty_feed"


def test_validate_feed_unreadable_items(monkeypatch):
    import httpx

    nolink = (b'<?xml version="1.0"?><rss version="2.0"><channel>'
              b"<item><title>No link here</title></item></channel></rss>")
    monkeypatch.setattr(httpx, "Client", _fake_client_for(FakeResp(200, nolink)))
    res = validate_feed("https://ex.com/f.xml")
    assert res.ok is False and res.reason == "unreadable_items"


def test_validate_feed_http_error(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _fake_client_for(FakeResp(404, b"nope")))
    res = validate_feed("https://ex.com/f.xml")
    assert res.ok is False and res.reason == "http_404"


def test_validate_feed_timeout(monkeypatch):
    import httpx

    import domains.news.source_verify as sv

    monkeypatch.setattr(httpx, "Client",
                        _fake_client_for(exc=httpx.TimeoutException("t")))
    monkeypatch.setattr(sv.time, "sleep", lambda *a: None)
    res = validate_feed("https://ex.com/f.xml")
    assert res.ok is False and res.reason == "timeout"


def test_validate_feed_ssrf_and_bad_url_need_no_network():
    assert validate_feed("http://169.254.169.254/").reason == "ssrf_blocked"
    assert validate_feed("ftp://ex.com/f").reason == "invalid_url"
    assert validate_feed(None).reason in ("invalid_url", "fetch_failed")


def test_validate_feed_creates_nothing():
    db = TestingSession()
    try:
        d0 = db.query(Document).count()
        a0 = db.query(Article).count()
        import httpx  # noqa: F401  (no network used; SSRF short-circuits)
        assert validate_feed("http://169.254.169.254/").ok is False
        assert db.query(Document).count() == d0
        assert db.query(Article).count() == a0
    finally:
        db.close()


def test_recheck_feed_by_id_success_and_failure(client: TestClient, monkeypatch):
    import domains.news.fetchers as fetchers
    from backend.database.models.source import Source as SrcModel

    db = TestingSession()
    src = SrcModel(name="v-feed-id", collection_method="rss", type="rss",
                   feed_url="https://ex.com/f.xml")
    db.add(src)
    db.commit()
    sid = str(src.id)
    db.close()

    monkeypatch.setattr(fetchers, "validate_feed",
                        lambda url, **k: FeedCheck(True, 2, url, "application/rss+xml", "ok"))
    ok = client.post(f"/api/sources/{sid}/recheck", params={"check": "feed"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["validation_status"] == "VERIFIED"

    monkeypatch.setattr(fetchers, "validate_feed",
                        lambda url, **k: FeedCheck(False, 0, url, "text/html", "not_feed"))
    bad = client.post(f"/api/sources/{sid}/recheck", params={"check": "feed"})
    assert bad.status_code == 200, bad.text
    assert bad.json()["validation_status"] != "VERIFIED"

    db2 = TestingSession()
    try:
        assert db2.query(Document).count() == 0
        assert db2.query(Article).count() == 0
    finally:
        db2.close()


def test_recheck_feed_rejects_non_rss_and_bad_check(client: TestClient):

    db = TestingSession()
    from backend.database.models.source import Source as SrcModel

    src = SrcModel(name="v-feed-api", collection_method="api", type="api",
                   api_url="https://ex.com/api")
    db.add(src)
    db.commit()
    sid = str(src.id)
    db.close()
    assert client.post(f"/api/sources/{sid}/recheck",
                       params={"check": "feed"}).status_code == 422
    assert client.post(f"/api/sources/{sid}/recheck",
                       params={"check": "nope"}).status_code == 422

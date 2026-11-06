"""صفحهٔ منابع (مرحلهٔ ۴): آمار، فهرست صفحه‌بندی‌شده و نقش‌ها."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from backend.main import app
from tests.conftest import TestingSession


def _source(name: str, *, active: bool = True) -> Source:
    s = TestingSession()
    src = Source(name=name, type="rss", active=active, validation_status="VERIFIED")
    s.add(src)
    s.commit()
    s.refresh(src)
    s.close()
    return src


def test_all_sources_stats_shape(client: TestClient) -> None:
    _source("s1")
    body = client.get("/api/sources/stats").json()
    assert set(body) == {"sources_total", "sources_active", "documents_total", "articles_total"}
    assert body["sources_total"] >= 1


def test_source_stats_counts_and_404(client: TestClient) -> None:
    src = _source("s2")
    s = TestingSession()
    doc = Document(source_id=src.id, url="https://example.com/x", title="t")
    s.add(doc)
    s.flush()
    s.add(Article(document_id=doc.id, title="a", classification_status="done"))
    s.commit()
    s.close()

    body = client.get(f"/api/sources/{src.id}/stats").json()
    assert body["source_id"] == str(src.id)
    assert body["document_count"] == 1
    assert body["article_count"] == 1
    assert body["active"] is True

    assert client.get(f"/api/sources/{uuid.uuid4()}/stats").status_code == 404


def test_source_list_pagination_envelope(client: TestClient) -> None:
    for i in range(3):
        _source(f"page-{i}")
    body = client.get("/api/sources?page=1&page_size=2&sort=name").json()
    assert set(body) >= {"items", "total", "page", "page_size", "has_more"}
    assert len(body["items"]) == 2
    assert body["total"] >= 3


def test_source_list_legacy_no_envelope(client: TestClient) -> None:
    _source("legacy")
    body = client.get("/api/sources?limit=5").json()
    assert isinstance(body, list)


def test_source_list_filter_active(client: TestClient) -> None:
    _source("on", active=True)
    _source("off", active=False)
    body = client.get("/api/sources?active=false&page=1&page_size=50").json()
    names = [i["name"] for i in body["items"]]
    assert "off" in names and "on" not in names


def test_stats_viewer_allowed(client: TestClient) -> None:
    app.dependency_overrides[require_user] = lambda: CurrentUser(
        username="v", role="viewer", via="session"
    )
    try:
        assert client.get("/api/sources/stats").status_code == 200
    finally:
        app.dependency_overrides.pop(require_user, None)

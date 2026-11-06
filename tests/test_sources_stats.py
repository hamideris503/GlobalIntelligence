"""آمار منابع (مرحلهٔ ۴)."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.database.models.source import Source
from tests.conftest import TestingSession


def _source(name: str) -> Source:
    s = TestingSession()
    src = Source(name=name, type="rss", active=True, validation_status="VERIFIED")
    s.add(src)
    s.commit()
    s.refresh(src)
    s.close()
    return src


def test_all_sources_stats(client: TestClient) -> None:
    _source("s1")
    res = client.get("/api/sources/stats")
    assert res.status_code == 200
    body = res.json()
    assert "sources_total" in body
    assert body["sources_total"] >= 1


def test_source_stats_not_found(client: TestClient) -> None:
    res = client.get(f"/api/sources/{uuid.uuid4()}/stats")
    assert res.status_code == 404


def test_source_stats_ok(client: TestClient) -> None:
    s = _source("s2")
    res = client.get(f"/api/sources/{s.id}/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["source_id"] == str(s.id)
    assert "document_count" in body
    assert "article_count" in body
    assert body["active"] is True


def test_source_stats_role_viewer_allowed(client: TestClient) -> None:
    s = _source("s3")
    # default test client has API_KEY="" => dev bypass admin; still 200
    res = client.get(f"/api/sources/{s.id}/stats")
    assert res.status_code == 200

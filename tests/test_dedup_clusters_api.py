"""API tests for /api/dedup/clusters."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_clusters_empty_or_list():
    # with API key (empty string is allowed in test mode)
    r = client.get("/api/dedup/clusters", headers={"X-API-Key": ""})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for item in data:
        assert "article_id" in item
        assert "cluster" in item
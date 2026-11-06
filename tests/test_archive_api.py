"""API tests for archive router."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_storage_and_settings():
    r = client.get("/api/archive/storage")
    assert r.status_code == 200
    assert "counts" in r.json()
    r2 = client.get("/api/archive/settings")
    assert r2.status_code == 200
    assert r2.json()["ARCHIVE_AUTO_PURGE_ENABLED"] is False


def test_catalog_empty():
    r = client.get("/api/archive/catalog")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_validate_missing():
    r = client.post("/api/archive/validate", json={"path": "/nope.zip"})
    assert r.status_code == 404

"""Tests for the Source Registry API & service (Phase 7)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_get_source(client: TestClient) -> None:
    res = client.post(
        "/api/sources",
        json={"name": "Test Source", "domain": "test.example", "country": "US",
              "type": "api", "language": "en", "credibility_score": 0.5},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Test Source"
    sid = body["id"]

    got = client.get(f"/api/sources/{sid}")
    assert got.status_code == 200
    assert got.json()["domain"] == "test.example"


def test_duplicate_name_conflict(client: TestClient) -> None:
    payload = {"name": "Dup Source", "type": "api"}
    assert client.post("/api/sources", json=payload).status_code == 201
    assert client.post("/api/sources", json=payload).status_code == 409


def test_list_and_filter(client: TestClient) -> None:
    client.post("/api/sources", json={"name": "A", "type": "api", "country": "IR"})
    client.post("/api/sources", json={"name": "B", "type": "rss", "country": "US"})
    all_sources = client.get("/api/sources").json()
    assert len(all_sources) == 2
    ir = client.get("/api/sources?country=IR").json()
    assert len(ir) == 1 and ir[0]["name"] == "A"


def test_update_and_health(client: TestClient) -> None:
    sid = client.post("/api/sources", json={"name": "H", "type": "api"}).json()["id"]

    upd = client.patch(f"/api/sources/{sid}", json={"credibility_score": 0.9})
    assert upd.status_code == 200
    assert upd.json()["credibility_score"] == 0.9

    ok = client.post(f"/api/sources/{sid}/health", json={"ok": True})
    assert ok.status_code == 200
    assert ok.json()["last_success"] is not None

    err = client.post(f"/api/sources/{sid}/health", json={"ok": False, "error": "timeout"})
    assert err.status_code == 200
    assert err.json()["last_error"] == "timeout"


def test_get_missing_source_404(client: TestClient) -> None:
    res = client.get("/api/sources/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_seed_data_is_valid() -> None:
    from db.seed.sources import INITIAL_SOURCES

    assert len(INITIAL_SOURCES) >= 10
    names = [s["name"] for s in INITIAL_SOURCES]
    assert len(names) == len(set(names)), "seed names must be unique"

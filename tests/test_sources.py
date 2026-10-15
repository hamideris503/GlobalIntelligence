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


def test_census_fields_and_filters(client: TestClient) -> None:
    """فیلدهای census جدا ذخیره می‌شوند و فیلتر category/validation کار می‌کند."""
    res = client.post("/api/sources", json={
        "name": "CensusA", "type": "official", "country": "US",
        "homepage_url": "https://example.gov/", "canonical_url": "https://example.gov/",
        "geography": "country", "category": " stats", "api_url": "https://api.example.gov/v1",
        "api_documentation_url": "https://example.gov/docs",
        "rss_url": "https://example.gov/feed", "validation_status": "NEEDS_REVIEW",
        "priority": 1, "access_model": "free",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["homepage_url"] == "https://example.gov/"
    assert body["api_url"] == "https://api.example.gov/v1"
    assert body["rss_url"] == "https://example.gov/feed"
    assert body["validation_status"] == "NEEDS_REVIEW"
    assert body["category"] == " stats"
    got = client.get("/api/sources?validation_status=NEEDS_REVIEW").json()
    assert any(s["name"] == "CensusA" for s in got)
    cat = client.get("/api/sources?category=%20stats").json()
    assert any(s["name"] == "CensusA" for s in cat)
    # پیش‌فرض وضعیت برای رکورد جدید
    plain = client.post("/api/sources", json={"name": "CensusB"}).json()
    assert plain["validation_status"] == "PENDING_VALIDATION"


def test_recheck_updates_status(monkeypatch, client: TestClient) -> None:
    """بررسی مجدد: بدون شبکه (mock fetch) وضعیت و canonical به‌روز می‌شود."""
    from domains.news import source_verify as sv

    sid = client.post("/api/sources",
                      json={"name": "RC", "homepage_url": "https://example.gov/"}).json()["id"]
    monkeypatch.setattr(
        sv, "fetch_url",
        lambda url, **kw: sv.FetchResult(url=url, final_url="https://example.gov/home",
                                        status_code=200, ok=True))
    res = client.post(f"/api/sources/{sid}/recheck")
    assert res.status_code == 200
    body = res.json()
    assert body["validation_status"] == "VERIFIED"
    assert body["canonical_url"] == "https://example.gov/home"


def test_recheck_without_homepage_422(client: TestClient) -> None:
    sid = client.post("/api/sources", json={"name": "NH"}).json()["id"]
    res = client.post(f"/api/sources/{sid}/recheck")
    assert res.status_code == 422


def test_export_json_csv(client: TestClient) -> None:
    client.post("/api/sources", json={"name": "EX1", "category": "economy"})
    js = client.get("/api/sources/export/all?format=json")
    assert js.status_code == 200
    rows = js.json()
    assert any(r["name"] == "EX1" and r["category"] == "economy" for r in rows)
    assert all("api_key" not in r for r in rows)
    csv = client.get("/api/sources/export/all?format=csv")
    assert csv.status_code == 200
    assert "EX1" in csv.text and "homepage_url" in csv.text.splitlines()[0]


def test_seed_data_is_valid() -> None:
    from db.seed.sources import INITIAL_SOURCES

    assert len(INITIAL_SOURCES) >= 10
    names = [s["name"] for s in INITIAL_SOURCES]
    assert len(names) == len(set(names)), "seed names must be unique"

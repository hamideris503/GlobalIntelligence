"""Tests for the Source Registry API & service (Phase 7)."""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import models as _models  # noqa: F401 — ثبت مدل‌ها
from backend.database.base import Base
from backend.database.session import get_db
from backend.main import app

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)


def _override_get_db() -> Generator[Session, None, None]:
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean() -> None:
    session = TestingSession()
    try:
        session.query(_models.Source).delete()
        session.commit()
    finally:
        session.close()


def test_create_and_get_source() -> None:
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


def test_duplicate_name_conflict() -> None:
    payload = {"name": "Dup Source", "type": "api"}
    assert client.post("/api/sources", json=payload).status_code == 201
    assert client.post("/api/sources", json=payload).status_code == 409


def test_list_and_filter() -> None:
    client.post("/api/sources", json={"name": "A", "type": "api", "country": "IR"})
    client.post("/api/sources", json={"name": "B", "type": "rss", "country": "US"})
    all_sources = client.get("/api/sources").json()
    assert len(all_sources) == 2
    ir = client.get("/api/sources?country=IR").json()
    assert len(ir) == 1 and ir[0]["name"] == "A"


def test_update_and_health() -> None:
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


def test_get_missing_source_404() -> None:
    res = client.get("/api/sources/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_seed_data_is_valid() -> None:
    from db.seed.sources import INITIAL_SOURCES

    assert len(INITIAL_SOURCES) >= 10
    names = [s["name"] for s in INITIAL_SOURCES]
    assert len(names) == len(set(names)), "seed names must be unique"

"""Tests for the jobs API (Phase 4).

از dependency override برای گرفتن یک دیتابیس SQLite درون‌حافظه استفاده می‌کند
تا به PostgreSQL واقعی نیاز نباشد.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.base import Base
from backend.database import models as _models  # noqa: F401 — ثبت مدل‌ها
from backend.database.session import get_db
from backend.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# جدول‌ها به‌صورت داینامیک از metadata ساخته می‌شوند (SQLite سازگار با UUID/JSON)
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
def _clean_jobs() -> None:
    session = TestingSession()
    try:
        session.query(_models.JobRun).delete()
        session.commit()
    finally:
        session.close()


def test_trigger_and_list_job() -> None:
    res = client.post(
        "/api/jobs/trigger",
        json={"job_name": "test_job", "source": "pytest", "payload": {"k": "v"}},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "accepted"
    assert body["job_run"]["job_name"] == "test_job"
    assert body["job_run"]["source"] == "pytest"

    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    items = listing.json()
    assert any(j["job_name"] == "test_job" for j in items)


def test_trigger_requires_job_name() -> None:
    res = client.post("/api/jobs/trigger", json={"source": "pytest"})
    assert res.status_code == 422

"""Shared test fixtures & single in-memory database.

مشکل: چند فایل تست هرکدام engine و override جدا تعریف می‌کردند و آخرین import
برنده می‌شد. اینجا یک engine مشترک و یک override واحد تعریف می‌شود.
"""
from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# قبل از import تنظیمات، محیط تست را امن و بدون کلید تنظیم کن
os.environ.setdefault("APP_ENV", "development")
os.environ["API_KEY"] = ""  # env var بر .env اولویت دارد → بدون احراز هویت در تست
os.environ["MOCK_MODE"] = "true"

from backend.core.config import get_settings
from backend.database.base import Base
from backend.database.session import get_db
from backend.main import app

# Database engine: use PostgreSQL when DATABASE_URL points to PostgreSQL (CI),
# otherwise fall back to in-memory SQLite (local development).
_db_url = os.environ.get("DATABASE_URL", "")
if "postgres" in _db_url:
    from sqlalchemy.pool import NullPool

    engine = create_engine(_db_url, poolclass=NullPool, connect_args={"connect_timeout": 10})
    # Tables already exist (created by Alembic in CI); skip create_all to avoid
    # any PG-side DDL overhead or lock contention.
else:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _override_get_db() -> Generator[Session, None, None]:
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db

# IP عمومی مستندات (example.com) برای resolver جعلیِ تست‌های آفلاین
TEST_PUBLIC_IP = "93.184.216.34"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _offline_resolver(monkeypatch) -> None:
    """resolver را برای تست‌های آفلاین mock می‌کند (سیاست production دست‌نخورده).

    `target_allowed` روی DNS بی‌پاسخ fail-closed است، پس هاست‌های نمونه‌ی تست
    (`example.test` …) باید «عمومی» resolve شوند تا مسیر واقعی adapter اجرا شود.
    literalها (127.0.0.1، 10.x، metadata) دست‌نخورده می‌مانند تا سیاست خصوصی
    واقعاً سنجیده شود؛ تستی که خودش DNS را بررسی می‌کند، همان‌جا patch می‌کند.
    """
    import ipaddress

    from domains.news import source_verify

    real = source_verify.resolve_host_ips

    def fake(host: str) -> list[str]:
        try:
            ipaddress.ip_address((host or "").strip("[]"))
        except ValueError:
            return [TEST_PUBLIC_IP]
        return real(host)

    monkeypatch.setattr(source_verify, "resolve_host_ips", fake)


@pytest.fixture(autouse=True)
def _clean_tables() -> Generator[None, None, None]:
    """پاک‌سازی همه‌ی جدول‌ها پیش از هر تست."""
    session = TestingSession()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()
    yield


@pytest.fixture(autouse=True)
def _reset_settings() -> Generator[None, None, None]:
    """تنظیمات singleton و gateway را پیش/پس از هر تست تازه می‌کند."""
    import backend.ai.budget as budget_module
    import backend.ai.gateway.gateway as gw_module

    get_settings.cache_clear()
    gw_module._gateway = None
    budget_module.reset_session_factory()
    yield
    get_settings.cache_clear()
    gw_module._gateway = None
    budget_module.reset_session_factory()

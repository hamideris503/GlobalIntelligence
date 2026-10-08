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

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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
    import backend.ai.gateway.gateway as gw_module

    get_settings.cache_clear()
    gw_module._gateway = None
    yield
    get_settings.cache_clear()
    gw_module._gateway = None

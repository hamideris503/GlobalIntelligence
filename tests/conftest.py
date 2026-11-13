"""Shared test fixtures & single in-memory database.

مشکل: چند فایل تست هرکدام engine و override جدا تعریف می‌کردند و آخرین import
برنده می‌شد. اینجا یک engine مشترک و یک override واحد تعریف می‌شود.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# F-10: pytest's shared ``pytest-of-<user>`` root keeps a ``pytest-current``
# directory symlink. On Windows a stale one cannot be unlinked (WinError 5), so
# every later run fails during temp cleanup. A run-private temp root means the
# shared root (and its symlink) is never touched, and parallel runs cannot
# collide. ``PYTEST_DEBUG_TEMPROOT`` is read lazily, so setting it here is early
# enough; an explicit ``--basetemp`` still wins.
_OWN_TEMPROOT = Path(tempfile.mkdtemp(prefix=f"gi-pytest-{os.getpid()}-"))
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(_OWN_TEMPROOT))


def _cleanup_own_temproot() -> None:
    for link in _OWN_TEMPROOT.rglob("pytest-current"):
        try:
            link.rmdir()  # Windows: removes a dir symlink; POSIX rmdir refuses it
        except OSError:
            pass
    shutil.rmtree(_OWN_TEMPROOT, ignore_errors=True)


atexit.register(_cleanup_own_temproot)

# قبل از import تنظیمات، محیط تست را امن و بدون کلید تنظیم کن
os.environ.setdefault("APP_ENV", "development")
os.environ["API_KEY"] = ""  # env var بر .env اولویت دارد → بدون احراز هویت در تست
os.environ["GI_ALLOW_DEV_AUTH_BYPASS"] = "1"
os.environ["MOCK_MODE"] = "true"

from backend.core.config import get_settings  # noqa: E402


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "migration: migration chain tests (SQLite- or PG-specific)")
    config.addinivalue_line("markers", "pg: tests requiring a live PostgreSQL instance")
from backend.database.base import Base  # noqa: E402
from backend.database.session import get_db  # noqa: E402
from backend.main import app  # noqa: E402

# Database engine: use PostgreSQL when DATABASE_URL points to PostgreSQL (CI),
# otherwise fall back to in-memory SQLite (local development).
_db_url = os.environ.get("DATABASE_URL", "")
if "postgres" in _db_url:
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    # Resolve the test DB host to a literal IP up front. Some tests patch
    # ``socket.getaddrinfo`` globally to simulate DNS; with a hostname DSN that
    # patch also redirects the database connection and every query fails with
    # ``ConnectionTimeout`` (F-05). A numeric host never consults DNS.
    _pg_url = make_url(_db_url)
    if (_pg_url.host or "").lower() in {"localhost", "::1"}:
        _pg_url = _pg_url.set(host="127.0.0.1")
    engine = create_engine(_pg_url, poolclass=NullPool, connect_args={"connect_timeout": 10})
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

    علاوه بر آن، `socket.getaddrinfo` برای TLDهای رزرو‌شده (RFC 6761: `.test`،
    `.invalid`، `.example`، `.localhost`) بلافاصله `gaierror` می‌دهد. این مسیر
    (`host_is_private` و هر مصرف‌کننده‌ی دیگر) بی‌آنکه patch شود به DNS واقعی
    می‌رفت و هر جست‌وجوی ناموجود ~۱۲ ثانیه منتظر resolver می‌ماند (F-08).
    """
    import ipaddress
    import socket

    from domains.news import source_verify

    real = source_verify.resolve_host_ips

    def fake(host: str) -> list[str]:
        try:
            ipaddress.ip_address((host or "").strip("[]"))
        except ValueError:
            return [TEST_PUBLIC_IP]
        return real(host)

    monkeypatch.setattr(source_verify, "resolve_host_ips", fake)

    real_gai = socket.getaddrinfo
    reserved = (".test", ".invalid", ".example", ".localhost")

    def offline_gai(host, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        name = host.decode() if isinstance(host, bytes) else str(host or "")
        low = name.strip().rstrip(".").lower()
        if low.endswith(reserved) or low in {"test", "invalid", "example", "localhost"}:
            raise socket.gaierror(socket.EAI_NONAME, f"offline reserved TLD: {name}")
        return real_gai(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", offline_gai)


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

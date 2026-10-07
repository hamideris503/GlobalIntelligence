"""Database engine, session & connectivity helpers.

Phase 3: مدل‌ها و session factory اضافه شدند.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """یک Engine واحد (lazy singleton) برمی‌گرداند."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """یک session factory واحد برمی‌گرداند."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency برای گرفتن Session دیتابیس."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database() -> dict[str, object]:
    """اتصال به دیتابیس را بررسی می‌کند.

    Returns:
        dict با کلیدهای ok (bool)، detail (str) و در صورت موفقیت نسخه.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar_one()
            revision = None
            try:
                revision = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
            except Exception:  # noqa: BLE001 — جدول نسخه ممکن است وجود نداشته باشد
                revision = None
        return {
            "ok": True,
            "detail": "connected",
            "server": str(version).split(",")[0],
            "migration": revision,
        }
    except Exception as exc:  # noqa: BLE001 — هر خطای اتصال را گزارش می‌کنیم
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

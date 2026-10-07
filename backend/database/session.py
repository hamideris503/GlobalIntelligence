"""Database engine & connectivity helpers.

در Phase 2 فقط اتصال به PostgreSQL و بررسی سلامت آن لازم است.
مدل‌ها و migrations در Phase 3 اضافه می‌شوند.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from backend.core.config import get_settings

_engine: Engine | None = None


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


def check_database() -> dict[str, object]:
    """اتصال به دیتابیس را بررسی می‌کند.

    Returns:
        dict با کلیدهای ok (bool) و detail (str).
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "detail": "connected"}
    except Exception as exc:  # noqa: BLE001 — می‌خواهیم هر خطای اتصال را گزارش کنیم
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

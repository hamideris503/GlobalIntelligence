"""Database engine, session & connectivity helpers.

Phase 3: مدل‌ها و session factory اضافه شدند.

GI-DB-001 (ممیزی ۲۰۲۶-۱۱-۱۵): زنجیرهٔ Alembic روی SQLite ستون‌های
`created_at`/`updated_at` را با `DEFAULT (now())` می‌سازد، در حالی که SQLite
تابع `now()` را نمی‌شناسد. نتیجه: هر INSERT در مسیر local (که `.env` آن را
SQLite می‌گذارد) با `unknown function: now()` شکست می‌خورد، در حالی که تست‌ها
(که schema را با `create_all` می‌سازند) این را نمی‌بینند.

اصلاح: تابع `now()` فقط روی اتصال‌های SQLite ثبت می‌شود. DDL تولید‌شده توسط
26 migration دست‌نخورده می‌ماند، PostgreSQL هیچ تغییری نمی‌بیند، و زمان با
timezone (UTC) برگردانده می‌شود تا با `DateTime(timezone=True)` سازگار باشد.
"""
from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _sqlite_now() -> str:
    """معادل `now()` برای SQLite؛ UTC و سازگار با DateTime(timezone=True)."""
    return datetime.now(UTC).isoformat(sep=" ")


def _install_sqlite_compat(engine: Engine) -> None:
    """توابعی را که migrationها فرض می‌کنند روی SQLite ثبت می‌کند.

    Alembic برای ستون‌های timestamp از `DEFAULT (now())` استفاده می‌کند
    (26 فایل migration). SQLite چنین تابعی ندارد، بنابراین بدون این ثبت
    تنها *نوشتن* روی دیتابیس مهاجرت‌شده شکست می‌خورد (خواندن سالم است).
    """
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _register(dbapi_connection, _record) -> None:  # noqa: ANN001
        create_function = getattr(dbapi_connection, "create_function", None)
        if create_function is None:  # pragma: no cover - غیر-SQLite
            return
        create_function("now", 0, _sqlite_now)


def get_engine() -> Engine:
    """یک Engine واحد (lazy singleton) برمی‌گرداند."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        if url.startswith("sqlite"):
            kwargs: dict[str, object] = {"future": True}
        else:
            kwargs = {
                "pool_pre_ping": True,
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "future": True,
            }
            if url.startswith("postgresql"):
                kwargs["connect_args"] = {"connect_timeout": 10}
        _engine = create_engine(url, **kwargs)
        _install_sqlite_compat(_engine)
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


def _server_version(conn) -> str:  # noqa: ANN001
    """نسخهٔ سرور با دستور سازگار با dialect.

    `SELECT version()` مخصوص PostgreSQL است و روی SQLite (و MySQL) خطا
    می‌دهد؛ قبلاً همین باعث می‌شد `/health/db` روی نصب local همیشه
    `degraded` گزارش شود (GI-DB-002).
    """
    dialect = conn.dialect.name
    if dialect == "sqlite":
        return str(conn.execute(text("SELECT sqlite_version()")).scalar_one())
    if dialect == "mysql":
        return str(conn.execute(text("SELECT VERSION()")).scalar_one())
    return str(conn.execute(text("SELECT version()")).scalar_one())


def check_database() -> dict[str, object]:
    """اتصال به دیتابیس را بررسی می‌کند.

    Returns:
        dict با کلیدهای ok (bool)، detail (str) و در صورت موفقیت نسخه.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            version = _server_version(conn)
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

"""GI-DB-001 — نوشتن روی SQLite ساخته‌شده با Alembic باید کار کند.

زنجیرهٔ Alembic ستون‌های timestamp را با `DEFAULT (now())` می‌سازد (26 فایل
migration). SQLite تابع `now()` ندارد و قبلاً هر INSERT با
`sqlite3.OperationalError: unknown function: now()` شکست می‌خورد، در حالی که
تست‌های دیگر با `Base.metadata.create_all` (که `CURRENT_TIMESTAMP` تولید می‌کند)
این باگ را نمی‌دیدند.

این فایل عمداً همان DDL تولیدشدهٔ Alembic را بازسازی می‌کند تا رگرسیون در
آینده دیده شود.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database.session import _install_sqlite_compat, get_engine

ALEMBIC_STYLE_DDL = """
CREATE TABLE gi_alembic_style (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT (now()) NOT NULL,
    updated_at DATETIME DEFAULT (now()) NOT NULL
)
"""


@pytest.fixture()
def sqlite_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'gi_audit.db'}", future=True)
    _install_sqlite_compat(engine)
    with engine.begin() as conn:
        conn.execute(text(ALEMBIC_STYLE_DDL))
    return engine


def test_insert_into_alembic_style_table_succeeds(sqlite_engine) -> None:
    with sqlite_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO gi_alembic_style (name) VALUES ('audit')")
        )
        row = conn.execute(
            text("SELECT name, created_at, updated_at FROM gi_alembic_style")
        ).one()
    assert row.name == "audit"
    assert row.created_at is not None
    assert row.updated_at is not None


def test_now_function_returns_utc_timestamp(sqlite_engine) -> None:
    with sqlite_engine.connect() as conn:
        value = conn.execute(text("SELECT now()")).scalar_one()
    assert isinstance(value, str)
    assert "-" in value and ":" in value


def test_app_engine_registers_compat_for_sqlite() -> None:
    """Engine واقعی اپ روی SQLite باید تابع now() را داشته باشد."""
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("این تست مخصوص لاین SQLite است")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT now()")).scalar_one()


def test_orm_insert_uses_server_default_without_error(tmp_path) -> None:
    """مدل‌های دارای TimestampMixin روی schema سبکِ Alembic قابل insert هستند."""
    from sqlalchemy.schema import CreateTable

    from backend.database.models.source import Source

    engine = create_engine(f"sqlite:///{tmp_path / 'gi_orm.db'}", future=True)
    _install_sqlite_compat(engine)
    # DDL واقعی همان جدول، ولی با همان پیش‌فرضی که Alembic روی SQLite تولید می‌کند
    ddl = str(CreateTable(Source.__table__).compile(engine))
    ddl = ddl.replace("DEFAULT CURRENT_TIMESTAMP", "DEFAULT (now())")
    assert "DEFAULT (now())" in ddl
    with engine.begin() as conn:
        conn.execute(text(ddl))
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    try:
        session.add(Source(name="audit-source", type="news"))
        session.commit()
        stored = session.execute(
            text("SELECT name, created_at FROM sources")
        ).one()
        assert stored.name == "audit-source"
        assert stored.created_at is not None
    finally:
        session.close()

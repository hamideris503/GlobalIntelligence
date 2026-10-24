"""Stage90 — PostgreSQL-dialect checks for the Stage89 dispatch migration.

No database is contacted: the model and the real migration script are compiled
with SQLAlchemy's PostgreSQL dialect and Alembic's offline SQL mode. A live
PostgreSQL run remains a CI concern (no local server in this environment).
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from backend.database.models.article_dispatch import ArticleDispatch

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db/migrations/versions/88a9b2c1d4e5_article_dispatch_table.py"


def _migration_module():
    spec = importlib.util.spec_from_file_location("stage89_dispatch_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _offline_postgres_sql(fn) -> str:  # noqa: ANN001
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(context):
        fn()
    return buffer.getvalue()


def test_migration_is_the_current_head() -> None:
    module = _migration_module()
    assert module.revision == "88a9b2c1d4e5"
    assert module.down_revision == "d91e4c7a2b60"


def test_model_ddl_compiles_for_postgres() -> None:
    dialect = postgresql.dialect()
    ddl = str(CreateTable(ArticleDispatch.__table__).compile(dialect=dialect))
    assert "CREATE TABLE article_dispatches" in ddl
    for column in ("article_id", "task_name", "status", "attempts",
                   "next_retry_at", "last_error", "meta", "lock_version"):
        assert column in ddl
    assert "uq_article_dispatch_task" in ddl
    assert "ON DELETE CASCADE" in ddl

    indexes = " ".join(
        str(CreateIndex(index).compile(dialect=dialect))
        for index in ArticleDispatch.__table__.indexes
    )
    for name in ("ix_article_dispatch_article_status",
                 "ix_article_dispatch_task_status",
                 "ix_article_dispatch_next_retry"):
        assert name in indexes


def test_migration_upgrade_compiles_for_postgres() -> None:
    sql = _offline_postgres_sql(_migration_module().upgrade)
    assert "CREATE TABLE article_dispatches" in sql
    assert "uq_article_dispatch_task" in sql
    assert "ON DELETE CASCADE" in sql
    assert "VARCHAR(32)" in sql and "VARCHAR(16)" in sql
    for name in ("ix_article_dispatch_article_status",
                 "ix_article_dispatch_task_status",
                 "ix_article_dispatch_next_retry"):
        assert f"CREATE INDEX {name}" in sql


def test_migration_downgrade_compiles_for_postgres() -> None:
    sql = _offline_postgres_sql(_migration_module().downgrade)
    for name in ("ix_article_dispatch_article_status",
                 "ix_article_dispatch_task_status",
                 "ix_article_dispatch_next_retry"):
        assert f"DROP INDEX {name}" in sql
    assert "DROP TABLE article_dispatches" in sql

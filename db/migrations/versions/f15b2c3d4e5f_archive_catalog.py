"""F13-LOCAL-2: archive catalog tables.

Revision ID: f15b2c3d4e5f
Revises: f14a0b1c2d3e
Create Date: 2026-10-30
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f15b2c3d4e5f"
down_revision: str | None = "f14a0b1c2d3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return any(ix.get("name") == name for ix in sa.inspect(op.get_bind()).get_indexes(table))


def upgrade() -> None:
    # ``ArchiveCatalog``/``ArchiveArticle`` live in the ORM metadata, so a schema
    # built by ``Base.metadata.create_all`` (dev SQLite files, test replays)
    # already contains these tables and indexes. Creating them again aborts the
    # whole upgrade, which is what broke ``upgrade head`` before this guard.
    if not _has_table("archive_catalog"):
        op.create_table(
            "archive_catalog",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archive_id", sa.String(128), nullable=False, unique=True),
            sa.Column("batch_id", sa.String(256), nullable=True),
            sa.Column("parent_batch_id", sa.String(256), nullable=True),
            sa.Column("part_index", sa.Integer(), nullable=True),
            sa.Column("total_parts", sa.Integer(), nullable=True),
            sa.Column("schema_version", sa.String(32), nullable=False, server_default="1.0"),
            sa.Column("file_name", sa.String(512), nullable=True),
            sa.Column("file_size", sa.BigInteger(), nullable=True),
            sa.Column("sha256", sa.String(128), nullable=True),
            sa.Column("archive_path", sa.Text(), nullable=True),
            sa.Column("manifest_json", sa.Text(), nullable=True),
            sa.Column("validation_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("restore_status", sa.String(32), nullable=False, server_default="not_restored"),
            sa.Column("telegram_status", sa.String(32), nullable=False, server_default="not_sent"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sanitized_error", sa.Text(), nullable=True),
            sa.Column("article_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("record_counts_json", sa.Text(), nullable=True),
        )
    if not _has_index("archive_catalog", "ix_archive_catalog_archive_id"):
        op.create_index("ix_archive_catalog_archive_id", "archive_catalog", ["archive_id"])
    if not _has_index("archive_catalog", "ix_archive_catalog_batch_id"):
        op.create_index("ix_archive_catalog_batch_id", "archive_catalog", ["batch_id"])

    if not _has_table("archive_articles"):
        op.create_table(
            "archive_articles",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archive_id", sa.String(128), nullable=False),
            sa.Column("original_article_id", sa.String(64), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=True),
            sa.Column("content_hash", sa.String(128), nullable=True),
            sa.Column("eligibility_reason", sa.String(64), nullable=True),
            sa.Column("eligibility_status", sa.String(32), nullable=False, server_default="BLOCKED"),
            sa.Column("archive_status", sa.String(32), nullable=False, server_default="archived"),
            sa.Column("restore_status", sa.String(32), nullable=False, server_default="not_restored"),
            sa.Column("archived_at", sa.String(64), nullable=True),
            sa.Column("conflict_detail", sa.Text(), nullable=True),
        )
    if not _has_index("archive_articles", "ix_archive_articles_archive_id"):
        op.create_index("ix_archive_articles_archive_id", "archive_articles", ["archive_id"])
    if not _has_index("archive_articles", "ix_archive_articles_original_article_id"):
        op.create_index(
            "ix_archive_articles_original_article_id", "archive_articles", ["original_article_id"]
        )


def downgrade() -> None:
    if _has_index("archive_articles", "ix_archive_articles_original_article_id"):
        op.drop_index("ix_archive_articles_original_article_id", table_name="archive_articles")
    if _has_index("archive_articles", "ix_archive_articles_archive_id"):
        op.drop_index("ix_archive_articles_archive_id", table_name="archive_articles")
    if _has_table("archive_articles"):
        op.drop_table("archive_articles")
    if _has_index("archive_catalog", "ix_archive_catalog_batch_id"):
        op.drop_index("ix_archive_catalog_batch_id", table_name="archive_catalog")
    if _has_index("archive_catalog", "ix_archive_catalog_archive_id"):
        op.drop_index("ix_archive_catalog_archive_id", table_name="archive_catalog")
    if _has_table("archive_catalog"):
        op.drop_table("archive_catalog")

"""Phase 89: article_dispatches — durable, idempotent downstream dispatch.

Additive only: one new table, no changes to existing tables. A row is the
idempotency record for ``(article_id, task_name)``; ``task_name`` carries the
analysis version (``<task>@v<version>``), so a handler version bump creates a
new row instead of reusing a completed one.

Revision ID: 88a9b2c1d4e5
Revises: d91e4c7a2b60
Create Date: 2026-10-23 14:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "88a9b2c1d4e5"
down_revision: str | None = "d91e4c7a2b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_dispatches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("lock_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "task_name", name="uq_article_dispatch_task"),
    )
    op.create_index(
        "ix_article_dispatch_article_status", "article_dispatches", ["article_id", "status"]
    )
    op.create_index(
        "ix_article_dispatch_task_status", "article_dispatches", ["task_name", "status"]
    )
    op.create_index(
        "ix_article_dispatch_next_retry", "article_dispatches", ["next_retry_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_article_dispatch_next_retry", table_name="article_dispatches")
    op.drop_index("ix_article_dispatch_task_status", table_name="article_dispatches")
    op.drop_index("ix_article_dispatch_article_status", table_name="article_dispatches")
    op.drop_table("article_dispatches")

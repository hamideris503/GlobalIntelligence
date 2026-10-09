"""phase51 learning_insights table

Revision ID: 181fd4efd921
Revises: 90d0c5b8761c
Create Date: 2026-10-09 06:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "181fd4efd921"
down_revision: str | None = "90d0c5b8761c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "subject", "period", name="uq_learning_insight"),
    )
    op.create_index("ix_learning_insights_kind", "learning_insights", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_learning_insights_kind", table_name="learning_insights")
    op.drop_table("learning_insights")

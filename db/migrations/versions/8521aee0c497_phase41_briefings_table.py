"""phase41 briefings table

Revision ID: 8521aee0c497
Revises: b67115733d7f
Create Date: 2026-10-09 06:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8521aee0c497"
down_revision: str | None = "b67115733d7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "period", name="uq_briefing_kind_period"),
    )
    op.create_index("ix_briefings_kind", "briefings", ["kind"])
    op.create_index("ix_briefings_period", "briefings", ["period"])


def downgrade() -> None:
    op.drop_index("ix_briefings_period", table_name="briefings")
    op.drop_index("ix_briefings_kind", table_name="briefings")
    op.drop_table("briefings")

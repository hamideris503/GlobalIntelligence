"""phase29 tournaments table

Revision ID: bb484db8621f
Revises: cb4b37bfa856
Create Date: 2026-10-09 03:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bb484db8621f"
down_revision: str | None = "cb4b37bfa856"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("targets", sa.Text(), nullable=True),
        sa.Column("methods", sa.Text(), nullable=True),
        sa.Column("horizon", sa.String(length=32), nullable=True),
        sa.Column("results", sa.Text(), nullable=True),
        sa.Column("winner_model", sa.String(length=128), nullable=True),
        sa.Column("n_forecasts", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tournaments_name", "tournaments", ["name"])


def downgrade() -> None:
    op.drop_index("ix_tournaments_name", table_name="tournaments")
    op.drop_table("tournaments")

"""phase39 self_evaluations table

Revision ID: b67115733d7f
Revises: 56ede3ad3189
Create Date: 2026-10-09 05:50:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b67115733d7f"
down_revision: str | None = "56ede3ad3189"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "self_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(length=8), nullable=True),
        sa.Column("checks", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("self_evaluations")

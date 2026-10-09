"""phase21 macro_assessments table

Revision ID: ce70a0fa41c3
Revises: 672f88b5d692
Create Date: 2026-10-09 02:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce70a0fa41c3"
down_revision: str | None = "672f88b5d692"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "macro_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("indicator", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=3), nullable=True),
        sa.Column("period", sa.String(length=32), nullable=True),
        sa.Column("latest_value", sa.Float(), nullable=True),
        sa.Column("yoy_change", sa.Float(), nullable=True),
        sa.Column("acceleration", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("momentum", sa.Float(), nullable=True),
        sa.Column("momentum_label", sa.String(length=32), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("inputs", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("indicator", "country", "period", name="uq_macro_assess"),
    )
    op.create_index("ix_macro_assessments_indicator", "macro_assessments", ["indicator"])
    op.create_index("ix_macro_assessments_country", "macro_assessments", ["country"])


def downgrade() -> None:
    op.drop_index("ix_macro_assessments_country", table_name="macro_assessments")
    op.drop_index("ix_macro_assessments_indicator", table_name="macro_assessments")
    op.drop_table("macro_assessments")

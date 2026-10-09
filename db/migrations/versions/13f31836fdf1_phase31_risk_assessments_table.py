"""phase31 risk_assessments table

Revision ID: 13f31836fdf1
Revises: bb484db8621f
Create Date: 2026-10-09 04:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "13f31836fdf1"
down_revision: str | None = "bb484db8621f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("drivers", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "period", name="uq_risk_assess"),
    )
    op.create_index("ix_risk_assessments_category", "risk_assessments", ["category"])
    op.create_index("ix_risk_assessments_period", "risk_assessments", ["period"])


def downgrade() -> None:
    op.drop_index("ix_risk_assessments_period", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_category", table_name="risk_assessments")
    op.drop_table("risk_assessments")

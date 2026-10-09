"""phase34 transmission_assessments table

Revision ID: 94b508e36070
Revises: 13f31836fdf1
Create Date: 2026-10-09 04:25:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "94b508e36070"
down_revision: str | None = "13f31836fdf1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transmission_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("input_value", sa.Float(), nullable=True),
        sa.Column("exposure", sa.Float(), nullable=True),
        sa.Column("impact", sa.Float(), nullable=True),
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
        sa.UniqueConstraint("channel", "period", name="uq_transmission_assess"),
    )
    op.create_index(
        "ix_transmission_assessments_channel", "transmission_assessments", ["channel"]
    )
    op.create_index(
        "ix_transmission_assessments_period", "transmission_assessments", ["period"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transmission_assessments_period", table_name="transmission_assessments"
    )
    op.drop_index(
        "ix_transmission_assessments_channel", table_name="transmission_assessments"
    )
    op.drop_table("transmission_assessments")

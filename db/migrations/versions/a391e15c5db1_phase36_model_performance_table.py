"""phase36 model_performance table

Revision ID: a391e15c5db1
Revises: f606d7199126
Create Date: 2026-10-09 05:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a391e15c5db1"
down_revision: str | None = "f606d7199126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_performance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("n_scored", sa.Integer(), nullable=True),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("mean_brier", sa.Float(), nullable=True),
        sa.Column("mean_log_loss", sa.Float(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model", "period", name="uq_model_perf"),
    )
    op.create_index("ix_model_performance_model", "model_performance", ["model"])
    op.create_index("ix_model_performance_period", "model_performance", ["period"])


def downgrade() -> None:
    op.drop_index("ix_model_performance_period", table_name="model_performance")
    op.drop_index("ix_model_performance_model", table_name="model_performance")
    op.drop_table("model_performance")

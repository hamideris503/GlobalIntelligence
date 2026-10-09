"""phase37 provider_run_stats table

Revision ID: 54c4fdb11fe7
Revises: f606d7199126
Create Date: 2026-10-09 05:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "54c4fdb11fe7"
down_revision: str | None = "a391e15c5db1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_run_stats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("task", sa.String(length=128), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("structured_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "model", "task", "period", name="uq_provider_run"
        ),
    )
    op.create_index(
        "ix_provider_run_stats_task", "provider_run_stats", ["task"]
    )
    op.create_index(
        "ix_provider_run_stats_provider", "provider_run_stats", ["provider"]
    )


def downgrade() -> None:
    op.drop_index("ix_provider_run_stats_provider", table_name="provider_run_stats")
    op.drop_index("ix_provider_run_stats_task", table_name="provider_run_stats")
    op.drop_table("provider_run_stats")

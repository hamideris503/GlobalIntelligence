"""phase53 debate runs/messages tables

Revision ID: a1b2c3d4e5f6
Revises: 181fd4efd921
Create Date: 2026-10-11 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "181fd4efd921"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "debate_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="done"),
        sa.Column("context_hash", sa.String(length=64), nullable=True),
        sa.Column("reference_price", sa.Float(), nullable=True),
        sa.Column("consensus_probability", sa.Float(), nullable=True),
        sa.Column("disagreement", sa.Float(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_estimate", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debate_runs_target", "debate_runs", ["target"])
    op.create_table(
        "debate_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("agent", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("probability_up", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["debate_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debate_messages_run_id", "debate_messages", ["run_id"])
    op.create_index("ix_debate_messages_agent", "debate_messages", ["agent"])


def downgrade() -> None:
    op.drop_index("ix_debate_messages_agent", table_name="debate_messages")
    op.drop_index("ix_debate_messages_run_id", table_name="debate_messages")
    op.drop_table("debate_messages")
    op.drop_index("ix_debate_runs_target", table_name="debate_runs")
    op.drop_table("debate_runs")

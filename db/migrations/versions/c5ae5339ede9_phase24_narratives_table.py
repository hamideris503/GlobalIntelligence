"""phase24 narratives table

Revision ID: c5ae5339ede9
Revises: bdd7eabe4da2
Create Date: 2026-10-09 03:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5ae5339ede9"
down_revision: str | None = "bdd7eabe4da2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "narratives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("event_ids", sa.Text(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=True),
        sa.Column("article_count", sa.Integer(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dominant_stance", sa.String(length=64), nullable=True),
        sa.Column("stance_divergence", sa.Float(), nullable=True),
        sa.Column("strength", sa.Float(), nullable=True),
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
        sa.UniqueConstraint("period", "signature", name="uq_narrative_sig"),
    )
    op.create_index("ix_narratives_period", "narratives", ["period"])
    op.create_index("ix_narratives_signature", "narratives", ["signature"])


def downgrade() -> None:
    op.drop_index("ix_narratives_signature", table_name="narratives")
    op.drop_index("ix_narratives_period", table_name="narratives")
    op.drop_table("narratives")

"""phase5: human_reviews table

Revision ID: b7e1c2d3f4a5
Revises: f17d4e5f6a7b
Create Date: 2026-11-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e1c2d3f4a5"
down_revision: str | None = "f17d4e5f6a7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_reviews",
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_reviews_entity", "human_reviews", ["entity_type", "entity_id"])
    op.create_index("ix_human_reviews_action", "human_reviews", ["action"])


def downgrade() -> None:
    op.drop_index("ix_human_reviews_action", table_name="human_reviews")
    op.drop_index("ix_human_reviews_entity", table_name="human_reviews")
    op.drop_table("human_reviews")

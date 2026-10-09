"""phase23 social_assessments table

Revision ID: bdd7eabe4da2
Revises: 5cf8f59a349b
Create Date: 2026-10-09 02:50:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bdd7eabe4da2"
down_revision: str | None = "5cf8f59a349b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "social_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("avg_sentiment", sa.Float(), nullable=True),
        sa.Column("article_count", sa.Integer(), nullable=True),
        sa.Column("unrest_share", sa.Float(), nullable=True),
        sa.Column("stance_mix", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("scope_type", "scope", "period", name="uq_social_assess"),
    )
    op.create_index(
        "ix_social_assessments_scope", "social_assessments", ["scope_type", "scope"]
    )
    op.create_index(
        "ix_social_assessments_period", "social_assessments", ["period"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_social_assessments_period", table_name="social_assessments"
    )
    op.drop_index(
        "ix_social_assessments_scope", table_name="social_assessments"
    )
    op.drop_table("social_assessments")

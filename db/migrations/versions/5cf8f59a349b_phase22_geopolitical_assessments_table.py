"""phase22 geopolitical_assessments table

Revision ID: 5cf8f59a349b
Revises: ce70a0fa41c3
Create Date: 2026-10-09 02:35:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5cf8f59a349b"
down_revision: str | None = "ce70a0fa41c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "geopolitical_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=512), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("tension", sa.Float(), nullable=True),
        sa.Column("conflict_share", sa.Float(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=True),
        sa.Column("sanction_links", sa.Integer(), nullable=True),
        sa.Column("top_types", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("actor", "period", name="uq_geo_assess"),
    )
    op.create_index(
        "ix_geopolitical_assessments_actor", "geopolitical_assessments", ["actor"]
    )
    op.create_index(
        "ix_geopolitical_assessments_period", "geopolitical_assessments", ["period"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_geopolitical_assessments_period", table_name="geopolitical_assessments"
    )
    op.drop_index(
        "ix_geopolitical_assessments_actor", table_name="geopolitical_assessments"
    )
    op.drop_table("geopolitical_assessments")

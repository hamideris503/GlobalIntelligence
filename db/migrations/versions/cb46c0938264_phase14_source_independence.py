"""phase14 source independence

Revision ID: cb46c0938264
Revises: 9b2bac1ae190
Create Date: 2026-10-08 15:19:18.482123
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cb46c0938264"
down_revision: str | None = "9b2bac1ae190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) فیلدهای استقلال روی Claim
    op.add_column(
        "claims",
        sa.Column(
            "supporting_source_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "claims",
        sa.Column(
            "independent_source_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "claims",
        sa.Column("source_independence", sa.Float(), nullable=True),
    )

    # 2) جدول وابستگی منابع
    op.create_table(
        "source_dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "detected_by", sa.String(length=32), nullable=False, server_default="manual"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "depends_on_id", name="uq_source_dependency_pair"
        ),
    )
    op.create_index(
        "ix_source_dependencies_source_id", "source_dependencies", ["source_id"]
    )
    op.create_index(
        "ix_source_dependencies_depends_on_id", "source_dependencies", ["depends_on_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_source_dependencies_depends_on_id", table_name="source_dependencies")
    op.drop_index("ix_source_dependencies_source_id", table_name="source_dependencies")
    op.drop_table("source_dependencies")
    op.drop_column("claims", "source_independence")
    op.drop_column("claims", "independent_source_count")
    op.drop_column("claims", "supporting_source_count")

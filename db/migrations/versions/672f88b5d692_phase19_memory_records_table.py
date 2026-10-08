"""phase19 memory_records table

Revision ID: 672f88b5d692
Revises: 9800836e7fcc
Create Date: 2026-10-08 20:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "672f88b5d692"
down_revision: str | None = "9800836e7fcc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("ref_type", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("record_metadata", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("layer", "ref_type", "ref_id", name="uq_memory_record_ref"),
    )
    op.create_index("ix_memory_records_layer", "memory_records", ["layer"])
    op.create_index("ix_memory_records_ref_id", "memory_records", ["ref_id"])
    op.create_index("ix_memory_records_observed_at", "memory_records", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_memory_records_observed_at", table_name="memory_records")
    op.drop_index("ix_memory_records_ref_id", table_name="memory_records")
    op.drop_index("ix_memory_records_layer", table_name="memory_records")
    op.drop_table("memory_records")

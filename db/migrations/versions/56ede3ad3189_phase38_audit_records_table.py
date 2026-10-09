"""phase38 audit_records table

Revision ID: 56ede3ad3189
Revises: 54c4fdb11fe7
Create Date: 2026-10-09 05:35:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "56ede3ad3189"
down_revision: str | None = "54c4fdb11fe7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("params", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ok"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_records_action", "audit_records", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_records_action", table_name="audit_records")
    op.drop_table("audit_records")

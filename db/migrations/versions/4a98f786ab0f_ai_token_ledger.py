"""ai token ledger for daily budget accounting (additive, no data touched).

Revision ID: 4a98f786ab0f
Revises: b67a512b5ad2
Create Date: 2026-10-16 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4a98f786ab0f"
down_revision: str | None = "b67a512b5ad2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_token_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("task", sa.String(128)),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_tokens", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False, server_default="reserved"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_key", name="uq_ai_ledger_request_key"),
    )
    op.create_index("ix_ai_ledger_day_status", "ai_token_ledger",
                    ["day", "status"])


def downgrade() -> None:
    op.drop_index("ix_ai_ledger_day_status", table_name="ai_token_ledger")
    op.drop_table("ai_token_ledger")

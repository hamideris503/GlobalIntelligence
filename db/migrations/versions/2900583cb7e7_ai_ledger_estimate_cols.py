"""ai ledger estimate trace columns (nullable; old rows stay valid).

Revision ID: 2900583cb7e7
Revises: 4a98f786ab0f
Create Date: 2026-10-16 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2900583cb7e7"
down_revision: str | None = "4a98f786ab0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_token_ledger",
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_token_ledger",
        sa.Column("output_cap_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_token_ledger", "output_cap_tokens")
    op.drop_column("ai_token_ledger", "estimated_input_tokens")

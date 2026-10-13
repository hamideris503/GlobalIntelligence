"""phase54 debate confidence + context pack columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-11 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("debate_runs", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("debate_runs", sa.Column("context_pack", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("debate_runs", "context_pack")
    op.drop_column("debate_runs", "confidence")

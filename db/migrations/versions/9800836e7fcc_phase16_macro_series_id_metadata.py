"""phase16 macro series_id metadata

Revision ID: 9800836e7fcc
Revises: 34b4e7f87ba7
Create Date: 2026-10-08 19:35:41.349853
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9800836e7fcc"
down_revision: str | None = "34b4e7f87ba7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "macro_observations",
        sa.Column("series_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "macro_observations",
        sa.Column("meta", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_macro_observations_series_id",
        "macro_observations",
        ["series_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_macro_observations_series_id", table_name="macro_observations")
    op.drop_column("macro_observations", "meta")
    op.drop_column("macro_observations", "series_id")

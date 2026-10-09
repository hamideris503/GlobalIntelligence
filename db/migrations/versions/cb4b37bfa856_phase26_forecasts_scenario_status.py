"""phase26 forecasts scenario status

Revision ID: cb4b37bfa856
Revises: c5ae5339ede9
Create Date: 2026-10-09 03:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cb4b37bfa856"
down_revision: str | None = "c5ae5339ede9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "forecasts",
        sa.Column("scenario", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "forecasts",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index("ix_forecasts_scenario", "forecasts", ["scenario"])


def downgrade() -> None:
    op.drop_index("ix_forecasts_scenario", table_name="forecasts")
    op.drop_column("forecasts", "status")
    op.drop_column("forecasts", "scenario")

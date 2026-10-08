"""phase12: events.claims_extracted

Revision ID: f6e19dcde0b6
Revises: f58aab369371
Create Date: 2026-10-08 16:15:07.103072
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f6e19dcde0b6'
down_revision: str | None = 'f58aab369371'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("claims_extracted", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("events", "claims_extracted")

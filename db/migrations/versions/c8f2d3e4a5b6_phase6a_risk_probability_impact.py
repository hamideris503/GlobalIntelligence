"""phase6a: risk probability/impact columns

Revision ID: c8f2d3e4a5b6
Revises: b7e1c2d3f4a5
Create Date: 2026-11-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8f2d3e4a5b6"
down_revision: str | None = "b7e1c2d3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("risk_assessments", sa.Column("probability", sa.Float(), nullable=True))
    op.add_column("risk_assessments", sa.Column("impact", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("risk_assessments", "impact")
    op.drop_column("risk_assessments", "probability")

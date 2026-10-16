"""article decided_by provenance (nullable; legacy rows stay NULL).

Revision ID: b67a512b5ad2
Revises: f594a47ca800
Create Date: 2026-10-16 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b67a512b5ad2"
down_revision: str | None = "f594a47ca800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("decided_by", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "decided_by")

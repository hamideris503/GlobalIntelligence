"""phase13: claims.evidence_extracted

Revision ID: 9b2bac1ae190
Revises: f6e19dcde0b6
Create Date: 2026-10-08 16:29:20.240460
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b2bac1ae190"
down_revision: str | None = "f6e19dcde0b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("evidence_extracted", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("claims", "evidence_extracted")

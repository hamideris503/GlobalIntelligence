"""phase15 events graph_extracted

Revision ID: 34b4e7f87ba7
Revises: cb46c0938264
Create Date: 2026-10-08 15:33:09.325362
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "34b4e7f87ba7"
down_revision: str | None = "cb46c0938264"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("graph_extracted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "entity_relationships",
        sa.Column("confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("entity_relationships", "confidence")
    op.drop_column("events", "graph_extracted")

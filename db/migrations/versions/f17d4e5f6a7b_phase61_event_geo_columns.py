"""phase61: event geo columns

Revision ID: f17d4e5f6a7b
Revises: e1f2a3b4c5d6
Create Date: 2026-11-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f17d4e5f6a7b"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("country", sa.String(length=8), nullable=True))
    op.add_column("events", sa.Column("location_precision", sa.String(length=16), nullable=True))
    op.add_column("events", sa.Column("location_source", sa.String(length=32), nullable=True))
    op.add_column("events", sa.Column("location_confidence", sa.Float(), nullable=True))
    op.create_index("ix_events_country", "events", ["country"])
    op.create_index("ix_events_latitude_longitude", "events", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("ix_events_latitude_longitude", table_name="events")
    op.drop_index("ix_events_country", table_name="events")
    op.drop_column("events", "location_confidence")
    op.drop_column("events", "location_source")
    op.drop_column("events", "location_precision")
    op.drop_column("events", "country")
    op.drop_column("events", "longitude")
    op.drop_column("events", "latitude")

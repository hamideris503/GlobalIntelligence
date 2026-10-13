"""source_bot ingestion-priority columns on documents (additive, nullable).

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ("canonical_url", sa.Text()),
    ("final_url", sa.Text()),
    ("external_id", sa.String(255)),
    ("ingestion_priority", sa.String(8)),
    ("priority_score", sa.Float()),
    ("priority_reason", sa.Text()),
    ("priority_source", sa.String(16)),
    ("priority_status", sa.String(32)),
    ("duplicate_status", sa.String(32)),
    ("canonical_id", sa.Text()),
]


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        for name, ctype in COLUMNS:
            try:
                batch.add_column(sa.Column(name, ctype, nullable=True))
            except Exception:  # noqa: BLE001 — اگر ستون هست، ادامه
                pass


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        for name, _ in COLUMNS:
            try:
                batch.drop_column(name)
            except Exception:  # noqa: BLE001
                pass

"""ai_models free-verification columns (additive, nullable).

Revision ID: c41d9e2b7f3a
Revises: 2900583cb7e7
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c41d9e2b7f3a"
down_revision: str | None = "2900583cb7e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ("free_status", sa.String(16)),
    ("free_source_url", sa.String(512)),
    ("free_verified_on", sa.Date()),
    ("free_review_days", sa.Integer()),
    ("free_limits", sa.Text()),
    ("free_account_prereqs", sa.Text()),
    ("free_privacy_notes", sa.Text()),
    ("free_verified_by", sa.String(64)),
    ("free_blocked_reason", sa.Text()),
]


def upgrade() -> None:
    with op.batch_alter_table("ai_models") as batch:
        for name, ctype in COLUMNS:
            try:
                batch.add_column(sa.Column(name, ctype, nullable=True))
            except Exception:  # noqa: BLE001 - ستون تکراری در صورت اجرای مجدد
                pass


def downgrade() -> None:
    with op.batch_alter_table("ai_models") as batch:
        for name, _ctype in COLUMNS:
            try:
                batch.drop_column(name)
            except Exception:  # noqa: BLE001
                pass

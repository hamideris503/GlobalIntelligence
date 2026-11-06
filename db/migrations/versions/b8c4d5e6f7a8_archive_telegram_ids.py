"""F13: store Telegram message/file ids on archive_catalog."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b8c4d5e6f7a8"
down_revision: str | None = "a7f3c9d1e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("archive_catalog", sa.Column("telegram_message_id", sa.String(64), nullable=True))
    op.add_column("archive_catalog", sa.Column("telegram_file_id", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("archive_catalog", "telegram_file_id")
    op.drop_column("archive_catalog", "telegram_message_id")
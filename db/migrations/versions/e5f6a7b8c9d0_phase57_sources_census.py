"""phase57 sources census columns (homepage/canonical/api/rss/validation_status/...)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-12 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ("homepage_url", sa.Text()),
    ("canonical_url", sa.Text()),
    ("geography", sa.String(32)),
    ("category", sa.String(64)),
    ("subcategory", sa.String(64)),
    ("primary_or_secondary", sa.String(16)),
    ("official_status", sa.String(16)),
    ("reliability_rationale", sa.Text()),
    ("bias_notes", sa.Text()),
    ("priority", sa.Integer()),
    ("access_model", sa.String(32)),
    ("registration_required", sa.Boolean()),
    ("api_url", sa.Text()),
    ("api_documentation_url", sa.Text()),
    ("api_auth_type", sa.String(32)),
    ("rss_url", sa.Text()),
    ("sitemap_url", sa.Text()),
    ("archive_url", sa.Text()),
    ("data_download_url", sa.Text()),
    ("terms_url", sa.Text()),
    ("license_terms", sa.Text()),
    ("robots_status", sa.String(32)),
    ("validation_status", sa.String(32)),
    ("last_checked_at", sa.DateTime(timezone=True)),
]


def upgrade() -> None:
    for name, coltype in COLUMNS:
        if name == "validation_status":
            op.add_column("sources", sa.Column(
                name, coltype, nullable=False, server_default="PENDING_VALIDATION"))
        else:
            op.add_column("sources", sa.Column(name, coltype, nullable=True))
    op.create_index("ix_sources_category", "sources", ["category"])


def downgrade() -> None:
    op.drop_index("ix_sources_category", table_name="sources")
    for name, _coltype in reversed(COLUMNS):
        op.drop_column("sources", name)

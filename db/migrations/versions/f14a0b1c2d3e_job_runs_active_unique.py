"""F-14: partial unique index on job_runs to prevent concurrent active jobs.

At most one row per ``job_name`` may be in an active status (``pending`` or
``running``). Completed/failed rows are unconstrained, so a source can be
re-ingested after the previous run finishes.

Revision ID: f14a0b1c2d3e
Revises: 88a9b2c1d4e5
Create Date: 2026-10-29
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f14a0b1c2d3e"
down_revision: str | None = "88a9b2c1d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "uq_job_runs_active"


def _index_exists() -> bool:
    """True when the index is already present.

    ``JobRun.__table_args__`` declares the same index, so any schema created by
    ``Base.metadata.create_all`` (dev SQLite files, test replays) already carries
    it. Without this guard ``alembic upgrade head`` aborts with
    ``index uq_job_runs_active already exists`` on those databases.
    """
    insp = sa.inspect(op.get_bind())
    return any(ix.get("name") == INDEX_NAME for ix in insp.get_indexes("job_runs"))


def upgrade() -> None:
    if _index_exists():
        return
    op.create_index(
        INDEX_NAME,
        "job_runs",
        ["job_name"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
        sqlite_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    if _index_exists():
        op.drop_index(INDEX_NAME, table_name="job_runs")

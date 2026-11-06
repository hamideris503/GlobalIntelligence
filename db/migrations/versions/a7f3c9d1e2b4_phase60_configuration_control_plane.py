"""F03.0: configuration control plane tables (instances + revisions).

Revision ID: a7f3c9d1e2b4
Revises: f16c3d4e5f6a
Create Date: 2026-11-02
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7f3c9d1e2b4"
down_revision: str | None = "f16c3d4e5f6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "configuration_instances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("latest_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_revision", sa.Integer(), nullable=True),
    )
    op.create_index("ix_configuration_instances_kind", "configuration_instances", ["kind"])
    op.create_unique_constraint(
        "uq_configuration_instance_kind_slug", "configuration_instances", ["kind", "slug"]
    )

    op.create_table(
        "configuration_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("descriptor_version", sa.String(length=16), nullable=False,
                  server_default="1"),
        sa.Column("validation_json", sa.Text(), nullable=True),
        sa.Column("test_json", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="api"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["configuration_instances.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_configuration_revisions_instance_id", "configuration_revisions", ["instance_id"]
    )
    op.create_unique_constraint(
        "uq_configuration_revision_number",
        "configuration_revisions",
        ["instance_id", "revision_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_configuration_revision_number", "configuration_revisions", type_="unique"
    )
    op.drop_index(
        "ix_configuration_revisions_instance_id", table_name="configuration_revisions"
    )
    op.drop_table("configuration_revisions")
    op.drop_constraint(
        "uq_configuration_instance_kind_slug", "configuration_instances", type_="unique"
    )
    op.drop_index("ix_configuration_instances_kind", table_name="configuration_instances")
    op.drop_table("configuration_instances")

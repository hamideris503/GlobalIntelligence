"""phase56 settings tables (ai_providers/ai_models/agent_assignments/app_settings)
+ void_reason on forecasts/debate_runs

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-11 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("key_hint", sa.String(length=16), nullable=True),
        sa.Column("extra_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_test_status", sa.String(length=16), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_ai_provider_name"),
    )
    op.create_index("ix_ai_providers_kind", "ai_providers", ["kind"])
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("price_in_per_mtok", sa.Float(), nullable=True),
        sa.Column("price_out_per_mtok", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "model_name", name="uq_model_provider_name"),
    )
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    op.create_table(
        "agent_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("model_id", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_id"], ["ai_models.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent", name="uq_agent_assignment_agent"),
    )
    op.create_index("ix_agent_assignments_agent", "agent_assignments", ["agent"])
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.add_column("forecasts", sa.Column("void_reason", sa.Text(), nullable=True))
    op.add_column("debate_runs", sa.Column("void_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("debate_runs", "void_reason")
    op.drop_column("forecasts", "void_reason")
    op.drop_table("app_settings")
    op.drop_index("ix_agent_assignments_agent", table_name="agent_assignments")
    op.drop_table("agent_assignments")
    op.drop_index("ix_ai_models_provider_id", table_name="ai_models")
    op.drop_table("ai_models")
    op.drop_index("ix_ai_providers_kind", table_name="ai_providers")
    op.drop_table("ai_providers")

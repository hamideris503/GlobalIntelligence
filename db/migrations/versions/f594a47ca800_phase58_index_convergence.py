"""phase58 index convergence (autogenerate drift).

Converges the database to the models without touching tables or data:
- agent_assignments: replace hand-written (constraint + plain index) with the
  unique index the model declares.
- documents / learning_insights / portfolio_snapshots / provider_run_stats /
  social_assessments: create model-declared indexes that were never migrated;
  drop two superseded index definitions (old explicit name, old composite).

Revision ID: f594a47ca800
Revises: f7a8b9c0d1e2
Create Date: 2026-10-16 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f594a47ca800"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) agent_assignments.agent: unique index per model (was constraint
    #    uq_agent_assignment_agent + separate plain index from phase56).
    op.drop_constraint(
        "uq_agent_assignment_agent", "agent_assignments", type_="unique"
    )
    op.drop_index("ix_agent_assignments_agent", table_name="agent_assignments")
    op.create_index(
        "ix_agent_assignments_agent",
        "agent_assignments",
        ["agent"],
        unique=True,
    )
    # 3) documents.ingestion_priority (model index never migrated).
    op.create_index(
        "ix_documents_ingestion_priority", "documents", ["ingestion_priority"]
    )
    # 4) learning_insights period/subject (model indexes never migrated).
    op.create_index(
        "ix_learning_insights_period", "learning_insights", ["period"]
    )
    op.create_index(
        "ix_learning_insights_subject", "learning_insights", ["subject"]
    )
    # 5) portfolio_snapshots: model names (old explicit name replaced).
    op.drop_index(
        "ix_portfolio_snapshots_portfolio", table_name="portfolio_snapshots"
    )
    op.create_index(
        "ix_portfolio_snapshots_period", "portfolio_snapshots", ["period"]
    )
    op.create_index(
        "ix_portfolio_snapshots_portfolio_id",
        "portfolio_snapshots",
        ["portfolio_id"],
    )
    # 6) provider_run_stats model/period (model indexes never migrated).
    op.create_index(
        "ix_provider_run_stats_model", "provider_run_stats", ["model"]
    )
    op.create_index(
        "ix_provider_run_stats_period", "provider_run_stats", ["period"]
    )
    # 7) social_assessments: model single-column indexes replace the old
    #    composite (scope_type, scope).
    op.drop_index(
        "ix_social_assessments_scope", table_name="social_assessments"
    )
    op.create_index(
        "ix_social_assessments_scope", "social_assessments", ["scope"]
    )
    op.create_index(
        "ix_social_assessments_scope_type",
        "social_assessments",
        ["scope_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_social_assessments_scope_type", table_name="social_assessments"
    )
    op.drop_index("ix_social_assessments_scope", table_name="social_assessments")
    op.create_index(
        "ix_social_assessments_scope",
        "social_assessments",
        ["scope_type", "scope"],
    )
    op.drop_index(
        "ix_provider_run_stats_period", table_name="provider_run_stats"
    )
    op.drop_index("ix_provider_run_stats_model", table_name="provider_run_stats")
    op.drop_index(
        "ix_portfolio_snapshots_portfolio_id",
        table_name="portfolio_snapshots",
    )
    op.drop_index(
        "ix_portfolio_snapshots_period", table_name="portfolio_snapshots"
    )
    op.create_index(
        "ix_portfolio_snapshots_portfolio",
        "portfolio_snapshots",
        ["portfolio_id"],
    )
    op.drop_index(
        "ix_learning_insights_subject", table_name="learning_insights"
    )
    op.drop_index("ix_learning_insights_period", table_name="learning_insights")
    op.drop_index(
        "ix_documents_ingestion_priority", table_name="documents"
    )
    op.drop_index("ix_agent_assignments_agent", table_name="agent_assignments")
    op.create_index(
        "ix_agent_assignments_agent", "agent_assignments", ["agent"]
    )
    op.create_unique_constraint(
        "uq_agent_assignment_agent", "agent_assignments", ["agent"]
    )

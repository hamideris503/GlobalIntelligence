"""Stage: user registration, email verification, password reset, 30-day sessions."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f0auth_users_accounts"
down_revision: str | None = "c8f2d3e4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    is_sqlite = op.get_context().dialect.name == "sqlite"
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    if is_sqlite:
        with op.batch_alter_table("sessions") as batch:
            batch.alter_column(
                "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True
            )
    else:
        op.alter_column(
            "sessions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True
        )

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index(
        "ix_auth_tokens_user_purpose", "auth_tokens", ["user_id", "purpose"]
    )
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    is_sqlite = op.get_context().dialect.name == "sqlite"
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_purpose", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    # Admin sessions may legitimately have NULL expires_at; restore a value
    # before this column becomes NOT NULL again.
    op.execute("UPDATE sessions SET expires_at = CURRENT_TIMESTAMP WHERE expires_at IS NULL")
    if is_sqlite:
        with op.batch_alter_table("sessions") as batch:
            batch.alter_column(
                "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False
            )
    else:
        op.alter_column(
            "sessions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
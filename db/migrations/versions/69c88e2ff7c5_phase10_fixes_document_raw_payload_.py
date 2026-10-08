"""phase10-fixes: document raw_payload, source feed_url, article classification fields

Revision ID: 69c88e2ff7c5
Revises: 71f41613dd11
Create Date: 2026-10-08 15:13:46.831305
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "69c88e2ff7c5"
down_revision: str | None = "71f41613dd11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- articles: فیلدهای طبقه‌بندی ---
    op.add_column("articles", sa.Column("country", sa.String(length=2), nullable=True))
    op.add_column(
        "articles",
        sa.Column(
            "classification_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "articles",
        sa.Column(
            "classification_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column("articles", sa.Column("classification_error", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("classification_meta", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_articles_classification_status"),
        "articles",
        ["classification_status"],
        unique=False,
    )
    op.create_index(op.f("ix_articles_country"), "articles", ["country"], unique=False)

    # --- documents: raw_payload + قید یکتایی + FK RESTRICT ---
    op.add_column("documents", sa.Column("raw_payload", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_document_source_url_content", "documents", ["source_id", "hash", "content_hash"]
    )
    # حذف هر FK موجود روی documents.source_id بدون نیاز به نام
    op.execute(
        """
        DO $$
        DECLARE cname text;
        BEGIN
            FOR cname IN
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
                WHERE rel.relname = 'documents' AND con.contype = 'f' AND att.attname = 'source_id'
            LOOP
                EXECUTE format('ALTER TABLE documents DROP CONSTRAINT %I', cname);
            END LOOP;
        END $$;
        """
    )
    op.create_foreign_key(
        "documents_source_id_fkey",
        "documents",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # --- sources: feed_url + endpoint_config ---
    op.add_column("sources", sa.Column("feed_url", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("endpoint_config", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "endpoint_config")
    op.drop_column("sources", "feed_url")

    op.drop_constraint("documents_source_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_source_id_fkey",
        "documents",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("uq_document_source_url_content", "documents", type_="unique")
    op.drop_column("documents", "raw_payload")

    op.drop_index(op.f("ix_articles_country"), table_name="articles")
    op.drop_index(op.f("ix_articles_classification_status"), table_name="articles")
    op.drop_column("articles", "classification_meta")
    op.drop_column("articles", "classification_error")
    op.drop_column("articles", "classification_attempts")
    op.drop_column("articles", "classification_status")
    op.drop_column("articles", "country")

"""phase7 document identity for url-less rows (partial unique index).

`(source_id, external_id) WHERE external_id IS NOT NULL AND hash IS NULL`

ردیف‌های بدون URL (سری زمانی CSV / ردیف API بدون لینک) فقط با شناسه‌ی اعلام‌شده‌ی
آداپتور (شاخص + دوره‌ی مشاهده) هویت دارند؛ NULL در SQLite/PostgreSQL یکتایی را
نمی‌شکند، پس بدون این index دو ردیف هم‌زمان با یک external_id ممکن بود.
ردیف‌های URL‌دار (hash IS NOT NULL)، revision و dedup فعلی دست‌نخورده می‌مانند.

پیش از ساخت index، گروه‌های متعارض فقط **خوانده و شمارش** می‌شوند: اگر duplicate
موجود باشد migration متوقف می‌شود و کلیدهای متعارض را گزارش می‌کند. هیچ حذف،
ادغام یا بازنویسی خودکار انجام نمی‌شود؛ تعیین‌تکلیف داده کار کاربر است.

نکته‌ی PostgreSQL: index داخل تراکنش migration ساخته می‌شود (بدون CONCURRENTLY —
آن نیاز به autocommit دارد و برای این جدول لازم نیست).

Revision ID: a7c1f5e9b3d2
Revises: c41d9e2b7f3a
Create Date: 2026-10-17 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c1f5e9b3d2"
down_revision: str | None = "c41d9e2b7f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_documents_source_external_id"
PREDICATE = "external_id IS NOT NULL AND hash IS NULL"


def _duplicate_groups(bind) -> list[tuple[str, str, int]]:  # noqa: ANN001
    """گروه‌های (source_id, external_id) با بیش از یک ردیف — فقط خواندنی."""
    rows = bind.execute(sa.text(
        "SELECT source_id, external_id, COUNT(*) AS n FROM documents "
        "WHERE external_id IS NOT NULL AND hash IS NULL "
        "GROUP BY source_id, external_id HAVING COUNT(*) > 1"
    )).fetchall()
    return [(str(r[0]), str(r[1]), int(r[2])) for r in rows]


def upgrade() -> None:
    duplicates = _duplicate_groups(op.get_bind())
    if duplicates:
        shown = ", ".join(f"{sid}/{eid}(n={n})" for sid, eid, n in duplicates[:20])
        more = "" if len(duplicates) <= 20 else f" (+{len(duplicates) - 20} more)"
        raise RuntimeError(
            "migration stopped before creating the unique index: "
            f"{len(duplicates)} duplicate (source_id, external_id) group(s) for "
            f"url-less documents need manual resolution: {shown}{more}"
        )
    op.create_index(
        INDEX_NAME,
        "documents",
        ["source_id", "external_id"],
        unique=True,
        sqlite_where=sa.text(PREDICATE),
        postgresql_where=sa.text(PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="documents")

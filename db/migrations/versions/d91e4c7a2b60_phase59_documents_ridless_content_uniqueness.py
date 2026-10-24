"""phase59 uniqueness for url-less documents that have a content identity.

`(source_id, content_hash) WHERE hash IS NULL AND content_hash IS NOT NULL
 AND (external_id IS NULL OR trim(external_id) = '')`

ردیف بدون URL که هم `external_id` ندارد و هم با payload معنا‌دار/عنوان/متن هش
محتوا گرفته است، پیش از این فقط با بررسی قبلی `store_item` از درج تکراری
محافظت می‌شد: `UniqueConstraint(source_id, hash, content_hash)` این ردیف‌ها را
نمی‌گیرد چون `hash IS NULL` است و NULL در SQLite/PostgreSQL یکتایی را نمی‌شکند.
این index جزئی همان تضمین را در سطح دیتابیس ایجاد می‌کند و:
- ردیف‌های URL‌دار (`hash IS NOT NULL`) را دست نمی‌زند؛
- ردیف‌هایی با `external_id` معتبر و `content_hash` تهی را بیرون می‌گذارد
  (آن‌ها قید اختصاصی خودشان را دارند)؛
- `trim` عمدی است تا external_id خالی/فاصله‌دار شناسه‌ی معتبر تلقی نشود؛
- برای محتوای کاملاً بی‌هویت (`content_hash IS NULL`) هیچ ادغامی ایجاد نمی‌کند؛
- یکتایی را فقط درون یک منبع اعمال می‌کند.

پیش از ساخت index، گروه‌های متعارض فقط **خوانده و شمارش** می‌شوند: اگر duplicate
موجود باشد migration متوقف می‌شود و کلیدهای متعارض را گزارش می‌کند. هیچ حذف،
ادغام یا بازنویسی خودکار انجام نمی‌شود؛ تعیین‌تکلیف داده کار کاربر است.

نکته‌ی PostgreSQL: index داخل تراکنش migration ساخته می‌شود (بدون CONCURRENTLY —
آن نیاز به autocommit دارد و برای این جدول لازم نیست).

Revision ID: d91e4c7a2b60
Revises: a7c1f5e9b3d2
Create Date: 2026-10-18 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d91e4c7a2b60"
down_revision: str | None = "a7c1f5e9b3d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_documents_source_content_hash_ridless"
PREDICATE = (
    "hash IS NULL AND content_hash IS NOT NULL "
    "AND (external_id IS NULL OR trim(external_id) = '')"
)


def _duplicate_groups(bind) -> list[tuple[str, str, int]]:  # noqa: ANN001
    """گروه‌های (source_id, content_hash) با بیش از یک ردیف — فقط خواندنی."""
    rows = bind.execute(sa.text(
        "SELECT source_id, content_hash, COUNT(*) AS n FROM documents "
        "WHERE hash IS NULL AND content_hash IS NOT NULL "
        "AND (external_id IS NULL OR trim(external_id) = '') "
        "GROUP BY source_id, content_hash HAVING COUNT(*) > 1"
    )).fetchall()
    return [(str(r[0]), str(r[1]), int(r[2])) for r in rows]


def upgrade() -> None:
    duplicates = _duplicate_groups(op.get_bind())
    if duplicates:
        # هش محتوا، محتوای خام نیست؛ فقط شناسه‌ی کوتاه‌شده گزارش می‌شود.
        shown = ", ".join(f"{sid}/{chash[:12]}(n={n})" for sid, chash, n in duplicates[:20])
        more = "" if len(duplicates) <= 20 else f" (+{len(duplicates) - 20} more)"
        raise RuntimeError(
            "migration stopped before creating the unique index: "
            f"{len(duplicates)} duplicate (source_id, content_hash) group(s) for "
            f"url-less documents without a valid external_id need manual "
            f"resolution: {shown}{more}"
        )
    op.create_index(
        INDEX_NAME,
        "documents",
        ["source_id", "content_hash"],
        unique=True,
        sqlite_where=sa.text(PREDICATE),
        postgresql_where=sa.text(PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="documents")

"""Archive catalog models (F13)."""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class ArchiveCatalog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "archive_catalog"

    archive_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(256), index=True)
    parent_batch_id: Mapped[str | None] = mapped_column(String(256), index=True)
    part_index: Mapped[int | None] = mapped_column(Integer)
    total_parts: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(128))
    archive_path: Mapped[str | None] = mapped_column(Text)
    manifest_json: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    restore_status: Mapped[str] = mapped_column(String(32), default="not_restored", nullable=False)
    telegram_status: Mapped[str] = mapped_column(String(32), default="not_sent", nullable=False)
    telegram_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sanitized_error: Mapped[str | None] = mapped_column(Text)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    record_counts_json: Mapped[str | None] = mapped_column(Text)


class ArchiveArticle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "archive_articles"

    archive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    original_article_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    revision: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    eligibility_reason: Mapped[str | None] = mapped_column(String(64))
    eligibility_status: Mapped[str] = mapped_column(String(32), default="BLOCKED", nullable=False)
    archive_status: Mapped[str] = mapped_column(String(32), default="archived", nullable=False)
    restore_status: Mapped[str] = mapped_column(String(32), default="not_restored", nullable=False)
    archived_at: Mapped[str | None] = mapped_column(String(64))
    conflict_detail: Mapped[str | None] = mapped_column(Text)

"""Configuration control-plane models (F03.0).

- `ConfigurationInstance`: یک شیء قابل‌پیکربندی (مثلاً یک Source) با شمارندهٔ نسخه.
- `ConfigurationRevision`: تاریخچهٔ افزودنی؛ هر تغییر ردیف جدید می‌سازد.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class ConfigurationInstance(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "configuration_instances"
    __table_args__ = (
        UniqueConstraint("kind", "slug", name="uq_configuration_instance_kind_slug"),
    )

    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    # نسخهٔ instance برای optimistic locking (۰ = هنوز revision ندارد)
    latest_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_revision: Mapped[int | None] = mapped_column(Integer)


class ConfigurationRevision(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "configuration_revisions"
    __table_args__ = (
        UniqueConstraint(
            "instance_id", "revision_number", name="uq_configuration_revision_number"
        ),
    )

    instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("configuration_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="draft", nullable=False, server_default="draft"
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    descriptor_version: Mapped[str] = mapped_column(String(16), default="1", nullable=False)
    validation_json: Mapped[str | None] = mapped_column(Text)
    test_json: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(64), default="api", nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

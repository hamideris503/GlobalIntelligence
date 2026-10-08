"""SourceDependency — وابستگی بین منابع (Phase 14).

دو منبع «مستقل» نیستند اگر یکی از دیگری منتشر کند/وابسته باشد. این جدول
یال‌های گراف وابستگی را نگه می‌دارد تا هنگام شمردن «تأیید مستقل» یک Claim،
منابع هم‌خانواده به یک منبع مستقل فروکاسته شوند.

اصل: **تعداد mention ≠ تعداد تأیید مستقل** (DATA_SOURCES.md).
"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin


class SourceDependency(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "source_dependencies"
    __table_args__ = (
        UniqueConstraint("source_id", "depends_on_id", name="uq_source_dependency_pair"),
    )

    # منبع وابسته (downstream)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # منبع مرجع (upstream / canonical)
    depends_on_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # syndication | aggregator | same_owner | repost | manual
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    # شدت وابستگی: 1.0 یعنی کاملاً وابسته (اصلاً مستقل نیست)، 0 = مستقل
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # domain | heuristic | manual
    detected_by: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")

    source: Mapped[Source] = relationship(foreign_keys=[source_id])  # noqa: F821
    depends_on: Mapped[Source] = relationship(foreign_keys=[depends_on_id])  # noqa: F821

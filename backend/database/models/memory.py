"""MemoryRecord — حافظه‌ی تاریخی یکپارچه (Phase 19, بند Memory-First).

یک رکورد حافظه ارجاعی سبک به یک موجودیت (event/world_state/article/...) است
که «چه چیزی در چه زمانی دانسته شد» را با Point-in-Time Integrity نگه می‌دارد.
idempotency با UniqueConstraint روی (layer, ref_type, ref_id).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin
from backend.database.enums import MemoryLayer


class MemoryRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memory_records"
    __table_args__ = (
        UniqueConstraint("layer", "ref_type", "ref_id", name="uq_memory_record_ref"),
    )

    layer: Mapped[str] = mapped_column(
        String(32), default=MemoryLayer.event.value, nullable=False, index=True
    )
    ref_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[float | None] = mapped_column(Float)

    # چه زمانی این چیز در جهان رخ داد/مشاهده شد (Point-in-Time)
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    # چه زمانی وارد حافظه شد
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # JSON: جزئیات لایه (method, inputs, versions...)
    # نام `metadata` برای SQLAlchemy رزرو است؛ از record_metadata استفاده می‌شود.
    record_metadata: Mapped[str | None] = mapped_column(Text)

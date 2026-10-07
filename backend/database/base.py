"""SQLAlchemy declarative base و mixinهای مشترک.

- Base: کلاس پایه‌ی همه‌ی مدل‌ها
- UUIDMixin: کلید اصلی UUID
- TimestampMixin: created_at / updated_at
- PointInTimeMixin: زمان‌های موردنیاز برای Point-in-Time Integrity (بند 45)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """کلاس پایه‌ی همه‌ی مدل‌های ORM."""


class UUIDMixin:
    """کلید اصلی UUID (قابل استفاده در همه‌ی backendها)."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """زمان ساخت و آخرین به‌روزرسانی رکورد."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PointInTimeMixin:
    """زمان‌های کلیدی برای جلوگیری از look-ahead / future leakage (بند 45).

    همه nullable هستند (در صورت امکان ثبت می‌شوند).
    """

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

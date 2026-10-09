"""AlertRule و Alert — هشدارهای آستانه‌ای (Phase 43).

قاعده روی یک متریک نام‌دار (risk:/market:/worldstate:/selfeval:) با عملگر
و آستانه تعریف می‌شود؛ نقض → رکورد Alert. تحویل خارجی (webhook/email)
در v1 نیست و به‌صورت وضعیت pending ثبت می‌شود (فازهای ops آینده).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin


class AlertRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    metric: Mapped[str] = mapped_column(String(256), nullable=False)
    operator: Mapped[str] = mapped_column(String(8), nullable=False)  # gt|lt
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(16))  # info/warning/critical
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Alert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metric: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False
    )  # active/acknowledged/resolved

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rule: Mapped[AlertRule] = relationship()

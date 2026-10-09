"""Audit record — رد حسابرسی اقدامات (Phase 38).

لاگ افزودنی «چه کسی، چه کاری، با چه پارامتری، با چه نتیجه‌ای»؛ هرگز حذف/ویرایش.
بازپخش (replay) در `domains/audit/replay.py` است.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class AuditRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_records"

    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)  # api/cli/system
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[str | None] = mapped_column(Text)  # JSON
    result: Mapped[str | None] = mapped_column(Text)  # JSON خلاصه
    status: Mapped[str] = mapped_column(String(16), default="ok", nullable=False)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

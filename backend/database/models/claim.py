"""Claim و Evidence (بند 24 و 25).

Claim یک ادعای ساختاریافته (subject-predicate-object) است.
Evidence شواهد موافق/مخالف برای یک Claim است.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin
from backend.database.enums import VerificationStatus


class Claim(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "claims"

    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True
    )
    subject: Mapped[str | None] = mapped_column(String(512), index=True)
    predicate: Mapped[str | None] = mapped_column(String(255))
    object: Mapped[str | None] = mapped_column(String(512))
    claim_type: Mapped[str | None] = mapped_column(String(64), index=True)

    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sources: Mapped[str | None] = mapped_column(Text)  # JSON list

    confidence: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(
        String(32), default=VerificationStatus.unverified.value, nullable=False
    )
    evidence_extracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Phase 14: Source Independence ---
    # تعداد کل منابعی که Claim را mention کرده‌اند (mention count)
    supporting_source_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    # تعداد منابع *مستقل* (بعد از فروکاست وابستگی‌ها)
    independent_source_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    # نسبت استقلال 0..1 = independent / supporting (0 اگر بدون منبع)
    source_independence: Mapped[float | None] = mapped_column(Float)

    event: Mapped[Event | None] = relationship(back_populates="claims")  # noqa: F821
    evidence: Mapped[list[Evidence]] = relationship(  # noqa: F821
        back_populates="claim", cascade="all, delete-orphan"
    )


class Evidence(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evidence"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True, nullable=False
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # supports|contradicts
    summary: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    weight: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    claim: Mapped[Claim] = relationship(back_populates="evidence")

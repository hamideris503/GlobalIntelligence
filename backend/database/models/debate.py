"""Debate runs & messages (Step 3 / Phase 53).

هر debate افزودنی است؛ هیچ رکوردی حذف/ویرایش نمی‌شود (Ledger-style).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin


class DebateRun(UUIDMixin, TimestampMixin, Base):
    """یک اجرای debate روی یک target."""

    __tablename__ = "debate_runs"

    target: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    horizon_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32), default="done", nullable=False, server_default="done"
    )  # done/insufficient_evidence/failed/budget_stopped/void
    void_reason: Mapped[str | None] = mapped_column(Text)  # Step 8: باطل به‌جای حذف
    context_hash: Mapped[str | None] = mapped_column(String(64))  # data_version
    reference_price: Mapped[float | None] = mapped_column(Float)
    consensus_probability: Mapped[float | None] = mapped_column(Float)
    disagreement: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    context_pack: Mapped[str | None] = mapped_column(Text)  # JSON بسته‌ی زمینه (E/C refs)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    total_cost_estimate: Mapped[float | None] = mapped_column(Float)

    messages: Mapped[list[DebateMessage]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class DebateMessage(UUIDMixin, TimestampMixin, Base):
    """یک پیام agent در یک دور (prompt hash + پاسخ + مصرف)."""

    __tablename__ = "debate_messages"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("debate_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    agent: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    response_text: Mapped[str | None] = mapped_column(Text)
    probability_up: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)  # کسر ارجاع جعلی و...
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)  # متن کوتاه، بدون secret

    run: Mapped[DebateRun] = relationship(back_populates="messages")

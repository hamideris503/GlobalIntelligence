"""AI token ledger — حسابداری روزانه‌ی مصرف توکن (Phase 1D).

هر تلاش واقعی provider یک ردیف idempotent دارد (request_key یکتا) تا retry
نه جا بیفتد نه دوبار شمرده شود. رزرو و تسویه جدا ثبت می‌شوند تا تخمین
محافظه‌کارانه با usage واقعی پاسخ قابل تطبیق باشد.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin


class AITokenLedger(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_token_ledger"
    __table_args__ = (
        UniqueConstraint("request_key", name="uq_ai_ledger_request_key"),
    )

    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    task: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actual_tokens: Mapped[int | None] = mapped_column(Integer)
    # ردیابی تخمین (nullable؛ ردیف‌های قدیمی بدون آن هم معتبرند)
    estimated_input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_cap_tokens: Mapped[int | None] = mapped_column(Integer)
    # reserved | settled | failed | unknown | released
    status: Mapped[str] = mapped_column(String(16), default="reserved", nullable=False)

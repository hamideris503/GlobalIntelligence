"""HumanReview — تصمیم/تأیید انسانی، جدا از خروجی ماشین (مرحله ۵).

append-only: هر تصمیم یک ردیف است و هرگز `classification_meta` یا نتیجهٔ ماشین
را بازنویسی نمی‌کند. `entity_type` فعلاً `article` است (قابل گسترش).
"""
from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin

# اقدام‌های مجاز
REVIEW_ACTIONS = ("approve", "reject", "request_evidence", "ack")


class HumanReview(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "human_reviews"
    __table_args__ = (
        Index("ix_human_reviews_entity", "entity_type", "entity_id"),
        Index("ix_human_reviews_action", "action"),
    )

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # actor_user_id در صورت وجود کاربر نشست؛ وگرنه actor متنی (مثلاً api_key)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    note: Mapped[str | None] = mapped_column(Text)

"""ArticleDispatch — ردیابیِِ ارسال مقاله به وظایفِ تحلیلِ downstream (Phase 89).

یک مقاله پس از screening با موفقیت (relevant=True یا P0/P1 safeguard) باید از این مراحل بگذر:
1. classification  →  topics, entities, importance, events extracted
2. event_extraction  →  ایجاد/لینک Event (Endpoint: /api/events/extract)
3. claim_extraction  →  ایجاد Claim از Event (Endpoint: /api/claims/extract)
4. evidence_collection  →  جمع‌آوری شواهد (Endpoint: /api/claims/evidence)
5. domain_analysis  →  تحلیل‌های macro/geopolitics/risk/society (Endpoint: /api/*/analyze)

این جدول idempotency key دارد تا اجرای مجدد هر مرحله تکرار نشود.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin


class ArticleDispatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "article_dispatches"
    __table_args__ = (
        # یک مقاله برای هر وظیفه downstream فقط یک بار dispatch می‌شود
        UniqueConstraint("article_id", "task_name", name="uq_article_dispatch_task"),
        Index("ix_article_dispatch_article_status", "article_id", "status"),
        Index("ix_article_dispatch_task_status", "task_name", "status"),
        Index("ix_article_dispatch_next_retry", "next_retry_at"),
    )

    # دسترسی‌ها از طریق ایندکس‌های ترکیبی زیر انجام می‌شود (بدون ایندکس تکراری).
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )

    # نام وظیفه downstream: classification | event_extraction | claim_extraction | evidence_collection | domain_analysis
    task_name: Mapped[str] = mapped_column(String(32), nullable=False)

    # وضعیت: pending | running | completed | retryable | terminal
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    # تعداد تلاش‌ها
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # زمان تلاش بعدی (برای backoff)
    next_retry_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # آخرین خطا (sanitized)
    last_error: Mapped[str | None] = mapped_column(Text)

    # متادیتا: idempotency key، screening route، screening decision، ...
    meta: Mapped[str | None] = mapped_column(Text)  # JSON stringified

    #_lock_version برای optimistic locking در صورت نیاز
    lock_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    article: Mapped[Article] = relationship(lazy="selectin")  # noqa: F821
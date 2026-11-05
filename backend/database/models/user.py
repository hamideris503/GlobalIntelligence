"""User identity, server-side sessions and login attempts (مرحله ۱ احراز هویت).

- `User`: هویت واقعی با Argon2id؛ نقش‌ها viewer|analyst|admin.
- `UserSession`: توکن نشست فقط به‌صورت hash sha256 ذخیره می‌شود.
- `LoginAttempt`: شمارش تلاش‌های ناموفق ورود برای rate limit پایدار (چند worker).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, TimestampMixin, UUIDMixin

ROLES: tuple[str, ...] = ("viewer", "analyst", "admin")


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(UUIDMixin, Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_ip_username", "ip", "username", "created_at"),)

    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

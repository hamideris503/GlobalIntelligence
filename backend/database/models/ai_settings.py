"""Settings tables — Providers/Models/Agent assignments/App settings (Step 8).

کلیدها فقط رمزشده (Fernet) ذخیره می‌شوند؛ هیچ‌وقت متن ساده نه.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin

# kindهای مجاز Provider (قرارداد v1)
PROVIDER_KINDS = ("gemini", "openrouter", "groq", "cloudflare", "openai_compatible", "mock")


class AIProviderRow(UUIDMixin, TimestampMixin, Base):
    """اعتبارنامه‌ی یک شرکت AI (کلید رمزشده)."""

    __tablename__ = "ai_providers"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    base_url: Mapped[str | None] = mapped_column(String(512))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    key_hint: Mapped[str | None] = mapped_column(String(16))  # ••••xxxx (غیرمحرمانه)
    extra_encrypted: Mapped[str | None] = mapped_column(Text)  # JSON رمزشده (Account ID و...)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_test_status: Mapped[str | None] = mapped_column(String(16))  # ok/fail
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    models: Mapped[list[AIModelRow]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class AIModelRow(UUIDMixin, TimestampMixin, Base):
    """یک مدل + قیمت هر میلیون توکن (کاربر از صفحه‌ی مدل می‌خواند)."""

    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider_id", "model_name", name="uq_model_provider_name"),)

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    price_in_per_mtok: Mapped[float | None] = mapped_column(Float)
    price_out_per_mtok: Mapped[float | None] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Free-Only verification (stored status; REVIEW_REQUIRED is computed).
    free_status: Mapped[str | None] = mapped_column(String(16))  # UNVERIFIED/FREE_VERIFIED/BLOCKED
    free_source_url: Mapped[str | None] = mapped_column(String(512))
    free_verified_on: Mapped[date | None] = mapped_column(Date)
    free_review_days: Mapped[int | None] = mapped_column(Integer)
    free_limits: Mapped[str | None] = mapped_column(Text)
    free_account_prereqs: Mapped[str | None] = mapped_column(Text)
    free_privacy_notes: Mapped[str | None] = mapped_column(Text)
    free_verified_by: Mapped[str | None] = mapped_column(String(64))
    free_blocked_reason: Mapped[str | None] = mapped_column(Text)

    provider: Mapped[AIProviderRow] = relationship(back_populates="models")


class AgentAssignment(UUIDMixin, TimestampMixin, Base):
    """نگاشت agent -> (provider, model)."""

    __tablename__ = "agent_assignments"

    agent: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_providers.id", ondelete="SET NULL")
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AppSetting(Base):
    """تنظیمات غیرمحرمانه‌ی برنامه (key/value). کلید محرمانه ممنوع."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

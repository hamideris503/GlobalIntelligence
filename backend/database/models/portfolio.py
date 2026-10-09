"""Portfolio و PortfolioSnapshot — هوشمندی پورتفوی (Phase 35).

پورتفوی مجموعه‌ی وزن‌دار اهداف (همان targetهای forecast) است؛
snapshot ماهانه، بازده موردانتظار و عدم‌قطعیت و تمرکز آن را ثبت می‌کند.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, UUIDMixin


class Portfolio(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "portfolios"

    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    positions: Mapped[str | None] = mapped_column(Text)  # JSON {target: weight}
    notes: Mapped[str | None] = mapped_column(Text)

    snapshots: Mapped[list[PortfolioSnapshot]] = relationship(  # noqa: F821
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class PortfolioSnapshot(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "period", name="uq_portfolio_snap"),
    )

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    expected_return: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float | None] = mapped_column(Float)  # میانگین وزنی گستردگی
    concentration: Mapped[float | None] = mapped_column(Float)  # هرفیندال
    diversification: Mapped[float | None] = mapped_column(Float)  # ‎1 − تمرکز
    coverage: Mapped[float | None] = mapped_column(Float)  # سهم وزن دارای سناریو

    detail: Mapped[str | None] = mapped_column(Text)  # JSON جزئیات هر موقعیت
    method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    portfolio: Mapped[Portfolio] = relationship(back_populates="snapshots")

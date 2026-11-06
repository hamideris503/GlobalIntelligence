"""JobRun — ثبت اجرای jobهای orchestration (n8n / workers).

برای Phase 4: n8n یک trigger می‌زند، backend این رکورد را در DB ذخیره می‌کند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, UUIDMixin


class JobRun(UUIDMixin, Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        # F-14: at most one active (pending/running) ingest job per job_name.
        # Partial unique index keeps completed/failed rows free to repeat.
        Index(
            "uq_job_runs_active",
            "job_name",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
            sqlite_where=text("status IN ('pending', 'running')"),
        ),
    )

    job_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))  # n8n | worker | manual | api
    status: Mapped[str] = mapped_column(String(32), default="received", nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)  # JSON stringified
    message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

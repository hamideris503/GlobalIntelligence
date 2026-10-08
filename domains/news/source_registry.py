"""Source Registry service — دسترسی و مدیریت منابع (بند 17, 56-58).

این سرویس منطق دامنه را از لایه‌ی API جدا می‌کند.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.source import Source


class SourceRegistry:
    """عملیات روی رجیستری منابع."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        active: bool | None = None,
        country: str | None = None,
        source_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Source]:
        stmt = select(Source)
        if active is not None:
            stmt = stmt.where(Source.active == active)
        if country:
            stmt = stmt.where(Source.country == country)
        if source_type:
            stmt = stmt.where(Source.type == source_type)
        stmt = stmt.order_by(Source.name).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def get(self, source_id: uuid.UUID) -> Source | None:
        return self.db.get(Source, source_id)

    def get_by_name(self, name: str) -> Source | None:
        return self.db.execute(
            select(Source).where(Source.name == name)
        ).scalar_one_or_none()

    def create(self, **fields: object) -> Source:
        source = Source(**fields)  # type: ignore[arg-type]
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def update(self, source: Source, **fields: object) -> Source:
        """به‌روزرسانی فیلدها. مقادیر None نیز اعمال می‌شوند (برای خالی‌کردن)."""
        for key, value in fields.items():
            if hasattr(source, key):
                setattr(source, key, value)
        self.db.commit()
        self.db.refresh(source)
        return source

    def set_active(self, source: Source, active: bool) -> Source:
        source.active = active
        self.db.commit()
        self.db.refresh(source)
        return source

    # --- health tracking (بند 17: last_success / last_error) ---
    def record_success(self, source: Source) -> Source:
        source.last_success = datetime.now(UTC)
        source.last_error = None
        self.db.commit()
        self.db.refresh(source)
        return source

    def record_error(self, source: Source, error: str) -> Source:
        source.last_error = error[:2000]
        self.db.commit()
        self.db.refresh(source)
        return source

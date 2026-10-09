"""Ledger — عملیات دفتر پیش‌بینی (Phase 26).

قواعد (مستند و ثابت):
- هرگز حذف نمی‌شود؛ تغییر وضعیت فقط active → superseded/expired/resolved.
- ثبت جدید برای همان (target, horizon, model, scenario) به‌صورت خودکار
  ردیف‌های active قدیمی‌تر را superseded می‌کند (جانشینی صریح).
- active as-of T: وضعیت active و valid_from <= T <= target_date.
- expired به‌صورت خودکار محاسبه نمی‌شود (Phase 27 Outcome)؛ فقط query.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast

logger = get_logger(__name__)

ACTIVE = "active"
SUPERSEDED = "superseded"


def supersede_older(
    db: Session,
    *,
    target: str,
    horizon: str | None,
    model: str | None,
    scenario: str | None,
    keep_id: object,
) -> int:
    """ردیف‌های active قدیمی هم‌خانواده را superseded می‌کند؛ تعداد را برمی‌گرداند."""
    stmt = select(Forecast).where(
        Forecast.target == target,
        Forecast.horizon == horizon,
        Forecast.model == model,
        Forecast.scenario == scenario,
        Forecast.status == ACTIVE,
        Forecast.id != keep_id,
    )
    count = 0
    for fc in db.execute(stmt).scalars().all():
        fc.status = SUPERSEDED
        count += 1
    if count:
        db.flush()
        logger.info(
            "ledger supersede | target=%s model=%s count=%d", target, model, count
        )
    return count


def mark_superseded(db: Session, forecast_id: object) -> Forecast | None:
    """ابطال دستی یک پیش‌بینی فعال؛ None اگر ناموجود."""
    fc = db.get(Forecast, forecast_id)
    if fc is None:
        return None
    if fc.status == ACTIVE:
        fc.status = SUPERSEDED
        db.commit()
    return fc


def active_as_of(
    db: Session, *, as_of: datetime, limit: int = 500
) -> list[Forecast]:
    """پیش‌بینی‌های فعال در زمان as_of (نیازمند aware)."""
    stmt = (
        select(Forecast)
        .where(
            Forecast.status == ACTIVE,
            Forecast.valid_from.is_not(None),
            Forecast.valid_from <= as_of,
            Forecast.target_date.is_not(None),
            Forecast.target_date >= as_of,
        )
        .order_by(Forecast.target, Forecast.model)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


__all__ = ["ACTIVE", "SUPERSEDED", "active_as_of", "mark_superseded", "supersede_older"]

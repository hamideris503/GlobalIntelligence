"""Metrics — گرداننده‌های متریک هشدار (Phase 43).

متریک‌های پشتیبانی‌شده‌ی v1 (مستند و ثابت):
- `risk:{category}` — آخرین امتیاز دسته.
- `market:{symbol}` — آخرین مقدار نماد.
- `market_change:{symbol}` — تغییر٪ دو مشاهده‌ی آخر (نیازمند ≥۲ نقطه).
- `worldstate:{signal}` — سیگنال معتبر آخرین snapshot (غیر-no_data).
- `selfeval:score` — آخرین نمره‌ی خودارزیابی.

نامشخص/ناموجود → None (قاعده ارزیابی نمی‌شود، نه خطا). بدون AI.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.market import MarketObservation
from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.self_evaluation import SelfEvaluation
from backend.database.models.world_state import WorldState


def resolve_metric(db: Session, metric: str) -> float | None:
    """مقدار جاری یک متریک نام‌دار؛ ناموجود → None."""
    if not metric or ":" not in metric:
        return None
    kind, _, key = metric.partition(":")
    kind, key = kind.strip(), key.strip()
    if not key:
        return None
    try:
        if kind == "risk":
            return db.execute(
                select(RiskAssessment.score)
                .where(RiskAssessment.category == key)
                .order_by(RiskAssessment.period.desc())
                .limit(1)
            ).scalars().first()
        if kind == "market":
            return db.execute(
                select(MarketObservation.value)
                .where(
                    MarketObservation.symbol == key,
                    MarketObservation.value.is_not(None),
                )
                .order_by(MarketObservation.observed_at.desc())
                .limit(1)
            ).scalars().first()
        if kind == "market_change":
            rows = list(
                db.execute(
                    select(MarketObservation.value)
                    .where(
                        MarketObservation.symbol == key,
                        MarketObservation.value.is_not(None),
                    )
                    .order_by(MarketObservation.observed_at.desc())
                    .limit(2)
                )
                .scalars()
                .all()
            )
            if len(rows) < 2 or not rows[1]:
                return None
            return round((rows[0] - rows[1]) / abs(rows[1]) * 100.0, 4)
        if kind == "worldstate":
            snap = db.execute(
                select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
            ).scalars().first()
            if snap is None or not hasattr(snap, key):
                return None
            try:
                meta = json.loads(snap.value_metadata or "{}")
            except Exception:  # noqa: BLE001
                return None
            entry = meta.get(key)
            if not isinstance(entry, dict) or entry.get("method") == "no_data":
                return None
            value = getattr(snap, key)
            return float(value) if value is not None else None
        if kind == "selfeval" and key == "score":
            return db.execute(
                select(SelfEvaluation.score)
                .order_by(SelfEvaluation.created_at.desc())
                .limit(1)
            ).scalars().first()
    except Exception:  # noqa: BLE001
        return None
    return None


def breached(value: float | None, operator: str, threshold: float) -> bool:
    """آیا آستانه نقض شد؟ مقدار تهی هرگز نقض نیست."""
    if value is None:
        return False
    if operator == "gt":
        return value > threshold
    if operator == "lt":
        return value < threshold
    return False


__all__ = ["breached", "resolve_metric"]

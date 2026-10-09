"""Outcome Engine — تطبیق نتیجه‌ی واقعی به پیش‌بینی‌های سررسیده (Phase 27).

قواعد تطبیق (مستند و ثابت، v1):
- فقط پیش‌بینی‌های با target_date گذشته و بدون outcome.
- macro:{ind}:{cty}: اولین مشاهده با شروع دوره ≥ target_date.
  دوره‌ها: سال (2024)، فصل (2026-Q1)، ماه (2026-07)؛ غیرقابل‌پارس → skip.
- market:{sym}: اولین مشاهده با observed_at ≥ target_date.
- actual_bool در Phase 27 پر نمی‌شود (مخصوص پیش‌بینی‌های احتمالاتی، فاز بعد).
- امتیازها (brier/log_loss/...) در Phase 28 محاسبه می‌شود، نه اینجا.
- وضعیت پیش‌بینیِ حل‌شده → resolved. بدون AI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.market import MacroObservation, MarketObservation
from domains.forecast.engine import parse_target

logger = get_logger(__name__)


@dataclass
class ResolveOutcome:
    resolved: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "resolved": self.resolved,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def period_start(period: str | None) -> datetime | None:
    """شروع دوره از رشته‌های سال/فصل/ماه؛ نامعتبر → None."""
    if not period:
        return None
    p = period.strip()
    try:
        if re.fullmatch(r"\d{4}", p):
            return datetime(int(p), 1, 1, tzinfo=UTC)
        m = re.fullmatch(r"(\d{4})-Q([1-4])", p)
        if m:
            return datetime(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1, tzinfo=UTC)
        m = re.fullmatch(r"(\d{4})-(\d{2})", p)
        if m and 1 <= int(m.group(2)) <= 12:
            return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=UTC)
    except ValueError:
        return None
    return None


def _aware(dt: datetime | None) -> datetime | None:
    """بک‌اندهایی مثل SQLite زمان را naive برمی‌گردانند؛ UTC فرض می‌شود."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class OutcomeEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _macro_actual(
        self, indicator: str, country: str, target_date: datetime
    ) -> float | None:
        stmt = (
            select(MacroObservation)
            .where(
                MacroObservation.indicator == indicator,
                MacroObservation.country == country,
                MacroObservation.value.is_not(None),
            )
            .order_by(MacroObservation.period.asc())
        )
        for row in self.db.execute(stmt).scalars().all():
            start = period_start(row.period)
            if start is not None and start >= target_date and row.value is not None:
                return row.value
        return None
    def _market_actual(self, symbol: str, target_date: datetime) -> float | None:
        # فیلتر زمانی در پایتون (بک‌اندهای naive مثل SQLite مقایسه‌ی DB را خراب می‌کنند)
        stmt = (
            select(MarketObservation)
            .where(
                MarketObservation.symbol == symbol,
                MarketObservation.value.is_not(None),
                MarketObservation.observed_at.is_not(None),
            )
            .order_by(MarketObservation.observed_at.asc())
        )
        cands = []
        for row in self.db.execute(stmt).scalars().all():
            obs = _aware(row.observed_at)
            if obs is not None and obs >= target_date and row.value is not None:
                cands.append((obs, row.value))
        if not cands:
            return None
        cands.sort(key=lambda t: t[0])
        return cands[0][1]

    def pending(self, *, now: datetime | None = None) -> list[Forecast]:
        """پیش‌بینی‌های سررسیده‌ی بدون outcome."""
        now = _aware(now) or datetime.now(UTC)
        stmt = (
            select(Forecast)
            .where(
                Forecast.target_date.is_not(None),
                Forecast.status.in_(["active", "expired"]),
            )
            .order_by(Forecast.target_date.asc())
        )
        out = []
        for fc in self.db.execute(stmt).scalars().all():
            td = _aware(fc.target_date)
            if td is None or td > now:
                continue
            exists = self.db.execute(
                select(ForecastOutcome.id).where(ForecastOutcome.forecast_id == fc.id)
            ).scalars().first()
            if exists is None:
                out.append(fc)
        return out

    def resolve_all(self, *, target: str | None = None) -> ResolveOutcome:
        outcome = ResolveOutcome()
        for fc in self.pending():
            if target and fc.target != target:
                continue
            try:
                td = _aware(fc.target_date)
                if td is None:
                    outcome.skipped += 1
                    continue
                kind, key, country = parse_target(fc.target or "")
                if kind == "macro":
                    assert country is not None
                    actual = self._macro_actual(key, country, td)
                else:
                    actual = self._market_actual(key, td)
                if actual is None:
                    outcome.skipped += 1
                    continue
                self.db.add(
                    ForecastOutcome(
                        forecast_id=fc.id,
                        actual_value=actual,
                        resolved_at=datetime.now(UTC),
                        notes="outcome_v1: first observation at/after target_date",
                    )
                )
                fc.status = "resolved"
                self.db.flush()
                outcome.resolved += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("outcome resolve failed | fc=%s err=%s", fc.id, exc)
        self.db.commit()
        logger.info("outcome resolve done | %s", outcome.as_dict())
        return outcome

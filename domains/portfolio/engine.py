"""Portfolio Engine — snapshot تحلیلی پورتفوی (Phase 35).

مسیر هر پورتفوی: positions (target→weight) + آخرین مجموعه‌ی سناریوی active
      هر هدف → آمار قطعی → upsert ماهانه در `portfolio_snapshots`.

- idempotent بر اساس UniqueConstraint (portfolio_id, period).
- هدف بدون مجموعه‌ی سناریوی کامل، پوشش‌نیافته می‌ماند (نه حدس).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast
from backend.database.models.portfolio import Portfolio, PortfolioSnapshot
from domains.portfolio.analytics import analyze_positions

logger = get_logger(__name__)


@dataclass
class SnapshotOutcome:
    portfolio_id: str = ""
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def _parse_positions(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


class PortfolioEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _scenario_sets(self) -> dict[str, dict]:
        """آخرین سناریوی active هر هدف: {target: {base, bull, bear}}."""
        stmt = (
            select(Forecast)
            .where(Forecast.scenario.is_not(None), Forecast.status == "active")
            .order_by(Forecast.target, Forecast.scenario, Forecast.created_at.desc())
        )
        out: dict[str, dict] = {}
        for fc in self.db.execute(stmt).scalars().all():
            if fc.target is None or fc.expected_value is None:
                continue
            bucket = out.setdefault(fc.target, {})
            if fc.scenario in ("base", "bull", "bear") and fc.scenario not in bucket:
                bucket[fc.scenario] = fc.expected_value
        return out

    def snapshot(
        self, *, portfolio_id: str, period: str | None = None
    ) -> SnapshotOutcome:
        outcome = SnapshotOutcome(portfolio_id=portfolio_id)
        period = period or datetime.now(UTC).strftime("%Y-%m")
        try:
            portfolio = self.db.get(Portfolio, UUID(portfolio_id))
        except ValueError:
            portfolio = None
        if portfolio is None:
            outcome.failed += 1
            outcome.errors.append("portfolio not found")
            return outcome

        try:
            positions = _parse_positions(portfolio.positions)
            stats = analyze_positions(positions, self._scenario_sets())
            if stats is None:
                outcome.skipped += 1
                return outcome
            existing = self.db.execute(
                select(PortfolioSnapshot).where(
                    PortfolioSnapshot.portfolio_id == portfolio.id,
                    PortfolioSnapshot.period == period,
                )
            ).scalar_one_or_none()
            payload = {
                "expected_return": stats.expected_return,
                "uncertainty": stats.uncertainty,
                "concentration": stats.concentration,
                "diversification": stats.diversification,
                "coverage": stats.coverage,
                "detail": json.dumps(stats.detail, ensure_ascii=False),
                "method": stats.method,
                "confidence": stats.confidence,
                "observed_at": datetime.now(UTC),
            }
            if existing is not None:
                for k, v in payload.items():
                    setattr(existing, k, v)
                outcome.duplicates += 1
            else:
                self.db.add(
                    PortfolioSnapshot(
                        portfolio_id=portfolio.id, period=period, **payload
                    )
                )
                self.db.flush()
                outcome.stored += 1
        except ValueError as exc:
            outcome.failed += 1
            outcome.errors.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            outcome.failed += 1
            outcome.errors.append(f"{type(exc).__name__}: {exc}")
            logger.warning("portfolio snapshot failed | %s err=%s", portfolio_id, exc)
        self.db.commit()
        return outcome

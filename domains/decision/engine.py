"""Decision Engine — تصمیم قانون‌مند برای هر هدف (Phase 32).

مسیر هر هدف: آخرین مجموعه‌ی سناریوی active (base/bull/bear[+tail]) +
      سقف ریسک‌های جاری → decision قطعی → ردیف `Recommendation`.

- Ledger تصمیم افزودنی است (تاریخچه‌ی تصمیم‌ها می‌ماند)؛ rank بر اساس score.
- بدون مجموعه‌ی سناریوی کامل → skip صادقانه (نه تصمیم حدسی).
- بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast
from backend.database.models.recommendation import Recommendation
from backend.database.models.risk_assessment import RiskAssessment
from domains.decision.analytics import decide

logger = get_logger(__name__)


@dataclass
class DecideOutcome:
    decided: int = 0
    skipped: int = 0
    failed: int = 0
    decision_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "decided": self.decided,
            "skipped": self.skipped,
            "failed": self.failed,
            "decision_ids": self.decision_ids,
            "errors": self.errors,
        }


class DecisionEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _latest_scenarios(self, target: str) -> dict[str, Forecast]:
        """آخرین Forecast فعال هر سناریو برای هدف."""
        stmt = (
            select(Forecast)
            .where(
                Forecast.target == target,
                Forecast.scenario.is_not(None),
                Forecast.status == "active",
            )
            .order_by(Forecast.scenario, Forecast.created_at.desc())
        )
        out: dict[str, Forecast] = {}
        for fc in self.db.execute(stmt).scalars().all():
            if fc.scenario not in out:
                out[fc.scenario] = fc
        return out

    def _current_risks(self) -> list[tuple[str, float]]:
        """آخرین ریسک هر دسته (نام، امتیاز)."""
        stmt = select(RiskAssessment).order_by(
            RiskAssessment.category, RiskAssessment.period.desc()
        )
        seen: set[str] = set()
        out: list[tuple[str, float]] = []
        for r in self.db.execute(stmt).scalars().all():
            if r.category in seen or r.score is None:
                continue
            seen.add(r.category)
            out.append((r.category, r.score))
        return out

    def _targets_with_scenarios(self) -> list[str]:
        stmt = (
            select(Forecast.target)
            .where(Forecast.scenario.is_not(None), Forecast.status == "active")
            .group_by(Forecast.target)
            .order_by(Forecast.target)
        )
        return [t for t in self.db.execute(stmt).scalars().all() if t]

    def run(
        self, *, targets: list[str] | None = None, horizon: str = "short"
    ) -> DecideOutcome:
        outcome = DecideOutcome()
        risks = self._current_risks()
        for target in targets or self._targets_with_scenarios():
            try:
                bucket = self._latest_scenarios(target)
                if not {"base", "bull", "bear"} <= set(bucket):
                    outcome.skipped += 1
                    continue
                base = bucket["base"].expected_value
                bull = bucket["bull"].expected_value
                bear = bucket["bear"].expected_value
                if base is None or bull is None or bear is None:
                    outcome.skipped += 1
                    continue
                tail = bucket["tail"].expected_value if "tail" in bucket else None
                scores = decide(
                    base=base, bull=bull, bear=bear, risks=risks, tail=tail
                )
                top_risks = sorted(risks, key=lambda t: t[1], reverse=True)[:3]
                rec = Recommendation(
                    asset=target,
                    direction=scores.direction,
                    horizon=horizon,
                    decision=scores.decision,
                    score=scores.score,
                    confidence=scores.confidence,
                    expected_return=base,
                    downside=bear,
                    probability_up=None,
                    probability_down=None,
                    base_scenario=str(base),
                    bull_scenario=str(bull),
                    bear_scenario=str(bear),
                    tail_risk=str(tail) if tail is not None else None,
                    evidence_for="; ".join(scores.reasons),
                    evidence_against=(
                        f"bear scenario at {bear} contradicts accumulate"
                        if scores.decision == "accumulate"
                        else None
                    ),
                    main_drivers="; ".join(scores.reasons[:2]),
                    main_risks="; ".join(
                        f"{n}={v:.2f}" for n, v in top_risks
                    ) or None,
                    invalidation=(
                        f"decision invalid if price breaks below bear {bear}"
                        if scores.decision in ("accumulate", "hold")
                        else f"decision invalid if price breaks above bull {bull}"
                    ),
                    model="decision_v1",
                    data_version=f"risks={len(risks)}",
                    rank=None,
                )
                self.db.add(rec)
                self.db.flush()
                outcome.decided += 1
                outcome.decision_ids.append(str(rec.id))
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("decide failed | target=%s err=%s", target, exc)
        # rank بر اساس score نزولی در همین اجرا
        self.db.commit()
        self._rerank()
        logger.info("decide done | %s", outcome.as_dict())
        return outcome

    def _rerank(self) -> None:
        """رتبه‌بندی همه‌ی تصمیم‌ها بر اساس score (۱ = بهترین)."""
        stmt = select(Recommendation).order_by(
            Recommendation.score.desc().nullslast(),
            Recommendation.created_at.desc(),
        )
        for i, rec in enumerate(self.db.execute(stmt).scalars().all(), start=1):
            rec.rank = i
        self.db.commit()


__all__ = ["DecideOutcome", "DecisionEngine"]

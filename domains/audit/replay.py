"""Replay — بازپخش قطعی موتورها با fingerprint قبل/بعد (Phase 38).

ایده: برای موتورهای idempotent، هش کانونیکال ردیف‌های کسب‌وکاری قبل و بعد
از اجرای دوباره باید یکسان باشد (تکرارپذیری قابل اثبات).
فیلدهای ناپایدار (زمان‌ها، id) در fingerprint نیستند.

موتورهای پشتیبانی‌شده: macro، risk، geopolitics، society، performance.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.macro_assessment import MacroAssessment
from backend.database.models.model_performance import ModelPerformance
from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.social_assessment import SocialAssessment

logger = get_logger(__name__)

SUPPORTED_ENGINES = ("macro", "risk", "geopolitics", "society", "performance")


@dataclass
class ReplayOutcome:
    engine: str
    match: bool = False
    digest_before: str = ""
    digest_after: str = ""
    rows: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "engine": self.engine,
            "match": self.match,
            "digest_before": self.digest_before,
            "digest_after": self.digest_after,
            "rows": self.rows,
            "errors": self.errors,
        }


def _digest(records: list[dict]) -> str:
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def fingerprint(db: Session, engine: str) -> tuple[str, int]:
    """هش کانونیکال + تعداد ردیف‌های کسب‌وکاری یک موتور."""
    if engine == "macro":
        rows = db.execute(select(MacroAssessment)).scalars().all()
        recs = [
            {
                "indicator": r.indicator, "country": r.country, "period": r.period,
                "latest_value": r.latest_value, "yoy_change": r.yoy_change,
                "acceleration": r.acceleration, "z_score": r.z_score,
                "momentum": r.momentum, "momentum_label": r.momentum_label,
            }
            for r in rows
        ]
    elif engine == "risk":
        rows = db.execute(select(RiskAssessment)).scalars().all()
        recs = [
            {
                "category": r.category, "period": r.period, "score": r.score,
                "level": r.level, "drivers": r.drivers,
            }
            for r in rows
        ]
    elif engine == "geopolitics":
        rows = db.execute(select(GeopoliticalAssessment)).scalars().all()
        recs = [
            {
                "actor": r.actor, "period": r.period, "tension": r.tension,
                "conflict_share": r.conflict_share, "event_count": r.event_count,
                "sanction_links": r.sanction_links,
            }
            for r in rows
        ]
    elif engine == "society":
        rows = db.execute(select(SocialAssessment)).scalars().all()
        recs = [
            {
                "scope_type": r.scope_type, "scope": r.scope, "period": r.period,
                "avg_sentiment": r.avg_sentiment, "article_count": r.article_count,
                "unrest_share": r.unrest_share, "stance_mix": r.stance_mix,
            }
            for r in rows
        ]
    elif engine == "performance":
        rows = db.execute(select(ModelPerformance)).scalars().all()
        recs = [
            {
                "model": r.model, "period": r.period, "n_scored": r.n_scored,
                "mae": r.mae, "rmse": r.rmse, "mean_brier": r.mean_brier,
                "mean_log_loss": r.mean_log_loss,
            }
            for r in rows
        ]
    else:
        raise ValueError(f"unsupported engine for replay: {engine}")
    recs.sort(key=lambda d: json.dumps(d, sort_keys=True))
    return _digest(recs), len(recs)


def rerun(db: Session, engine: str) -> None:
    """اجرای دوباره‌ی موتور (همان ورودی، همان کد)."""
    if engine == "macro":
        from domains.macro.analysis import MacroEngine

        MacroEngine(db).analyze_all()
    elif engine == "risk":
        from domains.risk.analysis import RiskEngine

        RiskEngine(db).analyze_all()
    elif engine == "geopolitics":
        from domains.geopolitics.analysis import GeopoliticalEngine

        GeopoliticalEngine(db).analyze_all()
    elif engine == "society":
        from domains.society.analysis import SocialEngine

        SocialEngine(db).analyze_all()
    elif engine == "performance":
        from domains.forecast.performance import PerformanceEngine

        PerformanceEngine(db).record()
    else:
        raise ValueError(f"unsupported engine for replay: {engine}")


def replay(db: Session, engine: str) -> ReplayOutcome:
    """بازپخش: fingerprint قبل/بعد + تطابق."""
    outcome = ReplayOutcome(engine=engine)
    try:
        before, n_before = fingerprint(db, engine)
        rerun(db, engine)
        after, n_after = fingerprint(db, engine)
        outcome.digest_before = before
        outcome.digest_after = after
        outcome.rows = n_after
        outcome.match = before == after and n_before == n_after
        logger.info(
            "replay | engine=%s match=%s rows=%d", engine, outcome.match, n_after
        )
    except Exception as exc:  # noqa: BLE001
        outcome.errors.append(f"{type(exc).__name__}: {exc}")
    return outcome


__all__ = ["SUPPORTED_ENGINES", "ReplayOutcome", "fingerprint", "replay", "rerun"]

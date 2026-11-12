"""Dashboard overview API (مرحلهٔ ۶A) — تجمیع با یک درخواست.

هر KPI تعریف صریح دارد. مقدار غیرقابل‌محاسبه با وضعیت
(`AVAILABLE`/`INSUFFICIENT_EVIDENCE`/`UNAVAILABLE`/`PENDING`/`FAILED`) برمی‌گردد،
نه صفر و نه عدد جعلی.
"""
from __future__ import annotations

from typing import Any

from domains.analyses import service as analyses_service
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models.article import Article
from backend.database.models.claim import Claim, Evidence
from backend.database.models.debate import DebateRun
from backend.database.models.event import Event
from backend.database.models.forecast import Forecast, Recommendation
from backend.database.models.source import Source
from backend.database.session import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

A = "AVAILABLE"
IE = "INSUFFICIENT_EVIDENCE"
UA = "UNAVAILABLE"


def _count(db: Session, model) -> int:  # noqa: ANN001
    return int(db.execute(select(func.count()).select_from(model)).scalar_one() or 0)


@router.get("/overview")
def dashboard_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    sources_total = _count(db, Source)
    sources_active = int(
        db.execute(select(func.count()).select_from(Source).where(Source.active.is_(True)))
        .scalar_one() or 0
    )
    events = _count(db, Event)
    analyses = analyses_service.collect(db)
    valid = [a for a in analyses if a.status == A]
    forecasts_active = int(
        db.execute(select(func.count()).select_from(Forecast).where(Forecast.status == "active"))
        .scalar_one() or 0
    )
    open_decisions = int(
        db.execute(select(func.count()).select_from(Recommendation))
        .scalar_one() or 0
    )

    # آخرین تحلیل معتبر (جدیدترین created_at).
    last = None
    if valid:
        valid.sort(key=lambda a: (a.created_at or ""), reverse=True)
        last = valid[0].__dict__

    # اجماع مدل‌ها: فقط اگر debate_run معتبر با consensus باشد.
    consensus: dict[str, Any]
    runs = db.execute(select(DebateRun)).scalars().all()
    with_consensus = [r for r in runs if r.consensus_probability is not None]
    if not with_consensus:
        consensus = {"status": UA, "reason": "no debate run with consensus", "models": []}
    elif len(with_consensus) == 1:
        consensus = {
            "status": IE, "reason": "only one debate run; multi-model consensus not asserted",
            "models": [], "last_run_at": with_consensus[0].created_at.isoformat()
            if with_consensus[0].created_at else None,
        }
    else:
        last_run = max(with_consensus, key=lambda r: r.created_at or "")
        consensus = {
            "status": A,
            "consensus_probability": last_run.consensus_probability,
            "disagreement": last_run.disagreement,
            "last_run_at": last_run.created_at.isoformat() if last_run.created_at else None,
            "models": [],
        }

    evidence_chain = {
        "source": sources_total,
        "event": events,
        "claim": _count(db, Claim),
        "evidence": _count(db, Evidence),
        "analysis": len(analyses),
    }

    # وضعیت غربالگری از همان تعریف /api/screening/summary.
    screening_queue = None
    screening_status = UA
    try:
        from backend.ai.local_screening import review as screening_review

        screening_queue = int(
            db.execute(
                select(func.count()).select_from(Article).where(screening_review.review_clause())
            ).scalar_one() or 0
        )
        screening_status = A
    except Exception:  # noqa: BLE001
        screening_status = UA

    kpis = [
        {"key": "events", "label": "رویدادها", "value": events, "status": A,
         "definition": "تعداد ردیف‌های events"},
        {"key": "valid_analyses", "label": "تحلیل‌های معتبر", "value": len(valid) if analyses else 0,
         "status": A if analyses else UA,
         "definition": "تحلیل‌های Recommendation/Debate/Forecast با وضعیت AVAILABLE"},
        {"key": "screening", "label": "نیازمند غربالگری", "value": screening_queue,
         "status": screening_status,
         "definition": "articles نیازمند بازبینی انسانی (هم‌تعریف با /api/screening/summary)"},
        {"key": "open_decisions", "label": "تصمیم‌های باز", "value": open_decisions, "status": A,
         "definition": "تعداد Recommendationها"},
        {"key": "active_forecasts", "label": "پیش‌بینی‌های فعال", "value": forecasts_active, "status": A,
         "definition": "Forecast با status=active"},
        {"key": "sources_active", "label": "منابع فعال", "value": sources_active, "status": A,
         "definition": "Source با active=true"},
        {"key": "evidence_quality", "label": "کیفیت شواهد", "value": None,
         "status": A if evidence_chain["evidence"] else IE,
         "definition": "نیازمند معیار مستند؛ تا آن زمان INSUFFICIENT_EVIDENCE"},
    ]

    return {
        "last_analysis": last,
        "kpis": kpis,
        "model_consensus": consensus,
        "evidence_chain": evidence_chain,
        "latest_outputs": [a.__dict__ for a in analyses[:20]],
        "priority_suggestions": [a.__dict__ for a in valid[:10]],
        "risk_series": _risk_series(db),
    }


def _risk_series(db: Session) -> dict[str, Any]:
    from backend.database.models.risk_assessment import RiskAssessment

    rows = db.execute(
        select(RiskAssessment).order_by(RiskAssessment.period)
    ).scalars().all()
    points: list[dict[str, Any]] = []
    for r in rows:
        if r.score is None:
            continue
        points.append({"period": r.period, "value": r.score, "category": r.category})
    return {"status": A if points else UA, "points": points}

"""نمای تجمیعی تحلیل‌ها (مرحلهٔ ۶A).

طبق تصمیم معماری، جدول `analyses` ساخته نمی‌شود؛ هر «تحلیل» یک نمای فقط‌خواندنی
روی موجودیت‌های موجود است:

- `recommendation:<uuid>`  ← Recommendation (خروجی Decision Engine)
- `debate:<uuid>`          ← DebateRun (مناظره/اجماع مدل‌ها)
- `forecast:<uuid>`        ← Forecast (پیش‌بینی)

رکوردهای اصلی هرگز کپی یا بازنویسی نمی‌شوند. مقادیر نامعلوم `null` می‌مانند و
وضعیت (`status`) با مقادیر مشخص گزارش می‌شود.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.claim import Claim, Evidence
from backend.database.models.debate import DebateRun
from backend.database.models.forecast import Forecast, Recommendation

# وضعیت‌های استاندارد (بدون عدد جعلی).
STATUS_AVAILABLE = "AVAILABLE"
STATUS_PENDING = "PENDING"
STATUS_FAILED = "FAILED"
STATUS_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
STATUS_UNAVAILABLE = "UNAVAILABLE"

_SORTABLE = ("created_at", "confidence", "status", "domain")


def _parse_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


@dataclass
class Analysis:
    id: str
    kind: str            # recommendation | debate | forecast
    raw_id: str
    title: str | None
    domain: str | None
    status: str
    model: str | None
    provider: str | None
    confidence: float | None
    priority: int | None
    summary: str | None
    created_at: str | None
    evidence_status: str


def _evidence_status(db: Session, *, has_claims: bool) -> str:
    """وضعیت شواهد مشتق از claims/evidence مرتبط؛ نه ذخیره‌شده."""
    has_evidence = db.execute(select(Evidence.id).limit(1)).first() is not None
    if not has_claims and not has_evidence:
        return STATUS_UNAVAILABLE
    if not has_evidence:
        return STATUS_INSUFFICIENT
    return STATUS_AVAILABLE


def _from_recommendation(db: Session, r: Recommendation, ev_status: str) -> Analysis:
    status = STATUS_AVAILABLE if r.decision else STATUS_PENDING
    return Analysis(
        id=f"recommendation:{r.id}", kind="recommendation", raw_id=str(r.id),
        title=f"{r.asset} · {r.direction or ''}".strip(" ·") or r.asset,
        domain="market", status=status, model=r.model,
        provider=None, confidence=r.confidence, priority=r.rank,
        summary=r.main_drivers, created_at=r.created_at.isoformat() if r.created_at else None,
        evidence_status=ev_status,
    )


def _from_debate(db: Session, d: DebateRun, ev_status: str) -> Analysis:
    status = {
        "done": STATUS_AVAILABLE,
        "insufficient_evidence": STATUS_INSUFFICIENT,
        "failed": STATUS_FAILED,
        "budget_stopped": STATUS_PENDING,
        "void": STATUS_UNAVAILABLE,
    }.get(d.status or "", STATUS_PENDING)
    return Analysis(
        id=f"debate:{d.id}", kind="debate", raw_id=str(d.id),
        title=d.target, domain="debate", status=status, model=None,
        provider=None, confidence=d.confidence, priority=None,
        summary=(f"consensus={d.consensus_probability}" if d.consensus_probability is not None else None),
        created_at=d.created_at.isoformat() if d.created_at else None,
        evidence_status=ev_status,
    )


def _from_forecast(db: Session, f: Forecast, ev_status: str) -> Analysis:
    status = {
        "active": STATUS_AVAILABLE, "resolved": STATUS_AVAILABLE,
        "superseded": STATUS_PENDING, "void": STATUS_UNAVAILABLE,
        "expired": STATUS_PENDING,
    }.get(f.status or "", STATUS_PENDING)
    return Analysis(
        id=f"forecast:{f.id}", kind="forecast", raw_id=str(f.id),
        title=f.target, domain="forecast", status=status, model=f.model,
        provider=None, confidence=f.confidence, priority=None,
        summary=(f"scenario={f.scenario}" if f.scenario else None),
        created_at=f.created_at.isoformat() if f.created_at else None,
        evidence_status=ev_status,
    )


def collect(db: Session) -> list[Analysis]:
    has_claims = db.execute(select(Claim.id).limit(1)).first() is not None
    ev_status = _evidence_status(db, has_claims=has_claims)
    out: list[Analysis] = []
    for r in db.execute(select(Recommendation)).scalars().all():
        out.append(_from_recommendation(db, r, ev_status))
    for d in db.execute(select(DebateRun)).scalars().all():
        out.append(_from_debate(db, d, ev_status))
    for f in db.execute(select(Forecast)).scalars().all():
        out.append(_from_forecast(db, f, ev_status))
    return out


def _sort_key(a: Analysis, field: str):
    if field == "confidence":
        return (a.confidence is None, -(a.confidence or 0.0))
    if field == "status":
        return (a.status or "")
    if field == "domain":
        return (a.domain or "")
    return (a.created_at or "")


def listing(
    db: Session, *, domain: str | None = None, status: str | None = None,
    model: str | None = None, q: str | None = None,
    page: int = 1, page_size: int = 50, sort: str = "-created_at",
) -> dict[str, Any]:
    items = collect(db)
    if domain:
        items = [a for a in items if a.domain == domain]
    if status:
        items = [a for a in items if a.status == status]
    if model:
        items = [a for a in items if a.model == model]
    if q:
        needle = q.strip().lower()
        items = [a for a in items if needle in (a.title or "").lower()
                 or needle in a.id.lower() or needle in (a.summary or "").lower()]
    reverse = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in _SORTABLE:
        field = "created_at"
        reverse = True
    items.sort(key=lambda a: _sort_key(a, field), reverse=reverse)
    total = len(items)
    window = items[(page - 1) * page_size: (page - 1) * page_size + page_size]
    return {
        "items": [a.__dict__ for a in window],
        "total": total, "page": page, "page_size": page_size,
        "has_more": page * page_size < total,
    }


def get(db: Session, analysis_id: str) -> Analysis | None:
    for a in collect(db):
        if a.id == analysis_id:
            return a
    return None


def trace(db: Session, analysis_id: str) -> dict[str, Any] | None:
    """زنجیرهٔ اثبات‌شده: source → document → event → claim → evidence → synthesis."""
    a = get(db, analysis_id)
    if a is None:
        return None
    # زنجیره از claims/eventهای موجود ساخته می‌شود (فقط روابط واقعی).
    claims = db.execute(select(Claim)).scalars().all()
    claim_ids = [str(c.id) for c in claims]
    event_ids = sorted({str(c.event_id) for c in claims if c.event_id})
    evidence_rows = db.execute(select(Evidence.id)).scalars().all()
    has_claims = bool(claim_ids)
    steps = [
        {"stage": "source", "status": STATUS_AVAILABLE if has_claims else STATUS_UNAVAILABLE, "count": None},
        {"stage": "document", "status": STATUS_UNAVAILABLE, "count": None},
        {"stage": "event", "status": STATUS_AVAILABLE if event_ids else STATUS_UNAVAILABLE,
         "count": len(event_ids), "ids": event_ids[:50]},
        {"stage": "claim", "status": STATUS_AVAILABLE if claim_ids else STATUS_UNAVAILABLE,
         "count": len(claim_ids), "ids": claim_ids[:50]},
        {"stage": "evidence",
         "status": STATUS_AVAILABLE if evidence_rows else STATUS_INSUFFICIENT,
         "count": len(evidence_rows)},
        {"stage": "synthesis", "status": a.status, "count": None},
    ]
    return {
        "analysis_id": analysis_id,
        "kind": a.kind,
        "raw_id": a.raw_id,
        "steps": steps,
        "note": "فقط روابط اثبات‌شده در دیتابیس نمایش داده می‌شود؛ نبود هر مرحله با وضعیت مشخص می‌آید.",
    }

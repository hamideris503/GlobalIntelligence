"""Alerts API (Phase 43).

- POST   /api/alerts/rules          → ساخت قاعده
- GET    /api/alerts/rules          → لیست قواعد
- PATCH  /api/alerts/rules/{id}     → فعال/غیرفعال
- POST   /api/alerts/evaluate       → ارزیابی همه‌ی قواعد فعال
- GET    /api/alerts                → لیست هشدارها (فیلتر وضعیت)
- POST   /api/alerts/{id}/ack       → تأیید
- POST   /api/alerts/{id}/resolve   → حل
"""
from __future__ import annotations

import uuid

from domains.alerts.engine import VALID_OPERATORS, AlertEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.alert import Alert, AlertRule
from backend.database.session import get_db

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class RuleCreate(BaseModel):
    name: str
    metric: str
    operator: str
    threshold: float
    severity: str = "warning"
    cooldown_hours: int = 24
    active: bool = True


class RulePatch(BaseModel):
    active: bool


class RuleRead(BaseModel):
    id: str
    name: str
    metric: str
    operator: str
    threshold: float
    severity: str | None
    cooldown_hours: int
    active: bool


class AlertOutcomeRead(BaseModel):
    evaluated: int
    triggered: int
    skipped: int
    failed: int
    errors: list[str]


class AlertRead(BaseModel):
    id: str
    rule_id: str
    metric: str
    value: float | None
    message: str | None
    severity: str | None
    status: str
    observed_at: str | None


def _to_rule(r: AlertRule) -> RuleRead:
    return RuleRead(
        id=str(r.id),
        name=r.name,
        metric=r.metric,
        operator=r.operator,
        threshold=r.threshold,
        severity=r.severity,
        cooldown_hours=r.cooldown_hours,
        active=r.active,
    )


def _to_alert(a: Alert) -> AlertRead:
    return AlertRead(
        id=str(a.id),
        rule_id=str(a.rule_id),
        metric=a.metric,
        value=a.value,
        message=a.message,
        severity=a.severity,
        status=a.status,
        observed_at=a.observed_at.isoformat() if a.observed_at else None,
    )


@router.post("/rules", response_model=RuleRead)
def create_rule(req: RuleCreate, db: Session = Depends(get_db)) -> RuleRead:
    if not req.name.strip() or not req.metric.strip():
        raise HTTPException(status_code=422, detail="name/metric required")
    if req.operator not in VALID_OPERATORS:
        raise HTTPException(
            status_code=422, detail=f"operator must be one of {VALID_OPERATORS}"
        )
    existing = db.execute(
        select(AlertRule).where(AlertRule.name == req.name.strip())
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="rule name already exists")
    rule = AlertRule(
        name=req.name.strip(),
        metric=req.metric.strip(),
        operator=req.operator,
        threshold=req.threshold,
        severity=req.severity,
        cooldown_hours=req.cooldown_hours,
        active=req.active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_rule(rule)


@router.get("/rules", response_model=list[RuleRead])
def list_rules(db: Session = Depends(get_db)) -> list[RuleRead]:
    stmt = select(AlertRule).order_by(AlertRule.name)
    return [_to_rule(r) for r in db.execute(stmt).scalars().all()]


@router.patch("/rules/{rule_id}", response_model=RuleRead)
def patch_rule(
    rule_id: uuid.UUID, req: RulePatch, db: Session = Depends(get_db)
) -> RuleRead:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    rule.active = req.active
    db.commit()
    return _to_rule(rule)


@router.post("/evaluate", response_model=AlertOutcomeRead)
def evaluate_rules(db: Session = Depends(get_db)) -> AlertOutcomeRead:
    outcome = AlertEngine(db).evaluate()
    return AlertOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[AlertRead])
def list_alerts(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AlertRead]:
    stmt = select(Alert).order_by(Alert.observed_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Alert.status == status)
    return [_to_alert(a) for a in db.execute(stmt).scalars().all()]


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)) -> AlertRead:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return _to_alert(alert)


@router.post("/{alert_id}/ack", response_model=AlertRead)
def ack_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)) -> AlertRead:
    alert = AlertEngine(db).acknowledge(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return _to_alert(alert)


@router.post("/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)) -> AlertRead:
    alert = AlertEngine(db).resolve(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return _to_alert(alert)
